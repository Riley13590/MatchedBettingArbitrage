import uuid
from datetime import UTC, datetime
from decimal import Decimal

from marketedge.strategies.arbitrage.detector import (
    ArbitrageFilters,
    QuoteView,
    SelectionQuotes,
    detect_back_lay_for_selection,
    detect_dutching,
    max_executable_bankroll,
)

NOW = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)


def _filters(**overrides: object) -> ArbitrageFilters:
    base = dict(
        min_net_roi=Decimal("0.005"),
        min_profit_gbp=Decimal("1.00"),
        max_quote_age_ms=5000,
        min_seconds_to_start=0,
        in_play=False,
        default_bankroll_gbp=Decimal("1000"),
    )
    base.update(overrides)
    return ArbitrageFilters(**base)  # type: ignore[arg-type]


def _quote(venue: str, price: str, size: str = "500", age_seconds: float = 0) -> QuoteView:
    return QuoteView(
        venue=venue,
        price=Decimal(price),
        available_size=Decimal(size),
        received_at=NOW,
        source_timestamp=NOW,
    )


def test_max_executable_bankroll_respects_tightest_leg() -> None:
    # Two-way, equal odds -> equal weights -> bankroll capped by smaller size.
    odds = [Decimal("2.0"), Decimal("2.0")]
    sizes = [Decimal("100"), Decimal("40")]
    assert max_executable_bankroll(odds, sizes) == Decimal("80")


def test_detect_dutching_finds_two_way_arb() -> None:
    selections = [
        SelectionQuotes(uuid.uuid4(), "HOME", _quote("oddsapi:williamhill", "2.20"), None),
        SelectionQuotes(uuid.uuid4(), "AWAY", _quote("oddsapi:bet365", "2.20"), None),
    ]
    opp = detect_dutching(uuid.uuid4(), uuid.uuid4(), selections, _filters(), now=NOW)
    assert opp is not None
    assert opp.worst_case_profit > 0
    assert opp.net_roi >= Decimal("0.005")
    assert len(opp.legs) == 2


def test_detect_dutching_no_arb_returns_none() -> None:
    selections = [
        SelectionQuotes(uuid.uuid4(), "HOME", _quote("oddsapi:williamhill", "1.90"), None),
        SelectionQuotes(uuid.uuid4(), "AWAY", _quote("oddsapi:bet365", "1.90"), None),
    ]
    assert detect_dutching(uuid.uuid4(), uuid.uuid4(), selections, _filters(), now=NOW) is None


def test_detect_dutching_missing_price_returns_none() -> None:
    selections = [
        SelectionQuotes(uuid.uuid4(), "HOME", _quote("oddsapi:williamhill", "2.20"), None),
        SelectionQuotes(uuid.uuid4(), "AWAY", None, None),
    ]
    assert detect_dutching(uuid.uuid4(), uuid.uuid4(), selections, _filters(), now=NOW) is None


def test_detect_dutching_rejects_below_min_profit() -> None:
    selections = [
        SelectionQuotes(uuid.uuid4(), "HOME", _quote("oddsapi:williamhill", "2.02"), None),
        SelectionQuotes(uuid.uuid4(), "AWAY", _quote("oddsapi:bet365", "2.02"), None),
    ]
    # Tiny arb, tiny bankroll -> profit well under a high min_profit_gbp bar.
    filters = _filters(default_bankroll_gbp=Decimal("10"), min_profit_gbp=Decimal("1000"))
    assert detect_dutching(uuid.uuid4(), uuid.uuid4(), selections, filters, now=NOW) is None


def test_detect_dutching_rejects_stale_quotes() -> None:
    stale = QuoteView(
        venue="oddsapi:williamhill",
        price=Decimal("2.20"),
        available_size=Decimal("500"),
        received_at=NOW,
        source_timestamp=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),  # 1 hour old
    )
    selections = [
        SelectionQuotes(uuid.uuid4(), "HOME", stale, None),
        SelectionQuotes(uuid.uuid4(), "AWAY", _quote("oddsapi:bet365", "2.20"), None),
    ]
    assert detect_dutching(uuid.uuid4(), uuid.uuid4(), selections, _filters(), now=NOW) is None


def test_detect_dutching_bankroll_capped_by_liquidity() -> None:
    selections = [
        SelectionQuotes(
            uuid.uuid4(), "HOME", _quote("oddsapi:williamhill", "2.20", size="10"), None
        ),
        SelectionQuotes(uuid.uuid4(), "AWAY", _quote("oddsapi:bet365", "2.20", size="10"), None),
    ]
    opp = detect_dutching(uuid.uuid4(), uuid.uuid4(), selections, _filters(), now=NOW)
    assert opp is not None
    assert opp.capital_required <= Decimal("20.10")  # roughly bounded by the tight legs


def test_detect_back_lay_finds_edge() -> None:
    selection = SelectionQuotes(uuid.uuid4(), "HOME", None, None)
    bookmaker = _quote("oddsapi:williamhill", "2.30")
    exchange = _quote("betfair", "2.10")
    opp = detect_back_lay_for_selection(
        uuid.uuid4(), uuid.uuid4(), selection, bookmaker, exchange, _filters(), now=NOW
    )
    assert opp is not None
    assert opp.worst_case_profit > 0
    assert {leg.venue for leg in opp.legs} == {"oddsapi:williamhill", "betfair"}


def test_detect_back_lay_no_edge_returns_none() -> None:
    selection = SelectionQuotes(uuid.uuid4(), "HOME", None, None)
    bookmaker = _quote("oddsapi:williamhill", "2.00")
    exchange = _quote("betfair", "2.10")  # lay price higher than back -> no edge
    assert (
        detect_back_lay_for_selection(
            uuid.uuid4(), uuid.uuid4(), selection, bookmaker, exchange, _filters(), now=NOW
        )
        is None
    )
