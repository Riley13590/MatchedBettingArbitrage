"""Deterministic replay for the arbitrage detector (spec section 27.3): the
same fixed quote snapshot, run through the detector twice, must produce
identical P&L — no hidden state, no clock dependence beyond the `now`
passed in explicitly."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from marketedge.strategies.arbitrage.detector import (
    ArbitrageFilters,
    QuoteView,
    SelectionQuotes,
    detect_back_lay_for_selection,
    detect_dutching,
)

NOW = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
FILTERS = ArbitrageFilters(
    min_net_roi=Decimal("0.005"),
    min_profit_gbp=Decimal("1.00"),
    max_quote_age_ms=5000,
    min_seconds_to_start=0,
    in_play=False,
    default_bankroll_gbp=Decimal("1000"),
)


def _fixed_dutching_snapshot() -> tuple[uuid.UUID, uuid.UUID, list[SelectionQuotes]]:
    quote = QuoteView(
        venue="oddsapi:williamhill",
        price=Decimal("2.20"),
        available_size=Decimal("500"),
        received_at=NOW,
        source_timestamp=NOW,
    )
    other = QuoteView(
        venue="oddsapi:bet365",
        price=Decimal("2.20"),
        available_size=Decimal("500"),
        received_at=NOW,
        source_timestamp=NOW,
    )
    selections = [
        SelectionQuotes(uuid.uuid4(), "HOME", quote, None),
        SelectionQuotes(uuid.uuid4(), "AWAY", other, None),
    ]
    return uuid.uuid4(), uuid.uuid4(), selections


def _economic_fields(opp: object) -> tuple:
    return (
        opp.gross_roi,  # type: ignore[attr-defined]
        opp.net_roi,  # type: ignore[attr-defined]
        opp.worst_case_profit,  # type: ignore[attr-defined]
        opp.capital_required,  # type: ignore[attr-defined]
        opp.max_executable_size,  # type: ignore[attr-defined]
        opp.data_age_ms,  # type: ignore[attr-defined]
        tuple((leg.venue, leg.side, leg.price, leg.stake) for leg in opp.legs),  # type: ignore[attr-defined]
    )


def test_dutching_replay_is_deterministic() -> None:
    event_id, market_id, selections = _fixed_dutching_snapshot()

    first = detect_dutching(event_id, market_id, selections, FILTERS, now=NOW)
    second = detect_dutching(event_id, market_id, selections, FILTERS, now=NOW)

    assert first is not None
    assert second is not None
    assert _economic_fields(first) == _economic_fields(second)


def test_back_lay_replay_is_deterministic() -> None:
    selection = SelectionQuotes(uuid.uuid4(), "HOME", None, None)
    bookmaker = QuoteView(
        venue="oddsapi:williamhill",
        price=Decimal("2.30"),
        available_size=Decimal("500"),
        received_at=NOW,
        source_timestamp=NOW,
    )
    exchange = QuoteView(
        venue="betfair",
        price=Decimal("2.10"),
        available_size=Decimal("500"),
        received_at=NOW,
        source_timestamp=NOW,
    )
    event_id, market_id = uuid.uuid4(), uuid.uuid4()

    first = detect_back_lay_for_selection(
        event_id, market_id, selection, bookmaker, exchange, FILTERS, now=NOW
    )
    second = detect_back_lay_for_selection(
        event_id, market_id, selection, bookmaker, exchange, FILTERS, now=NOW
    )

    assert first is not None
    assert second is not None
    assert _economic_fields(first) == _economic_fields(second)
