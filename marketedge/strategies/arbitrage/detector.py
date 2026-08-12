"""Arbitrage detector (spec sections 13 and 31's pseudocode).

Pure with respect to I/O: takes an already-fetched snapshot of the latest
quote per (venue, side) for every selection in one canonical market and
returns whatever `ArbitrageOpportunity` objects survive the configured
filters. The caller (`runner.py`) is responsible for fetching that
snapshot and persisting the result — this keeps the detection math
independently testable and deterministic (spec section 27.3).

Two arb families, per spec section 13:

1. Multi-way dutching across the best BACK price for each outcome,
   possibly sourced from different venues.
2. Back-lay: for a single outcome, backing a bookmaker's price and laying
   the same outcome on an exchange.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from marketedge.domain.enums import Side
from marketedge.domain.odds import overround
from marketedge.strategies.arbitrage.back_lay import (
    lay_stake_for_equal_profit,
    profit_if_selection_loses,
    profit_if_selection_wins,
)
from marketedge.strategies.arbitrage.dutching import dutch_stakes
from marketedge.strategies.arbitrage.dutching import worst_case_profit as dutch_worst_case
from marketedge.strategies.arbitrage.fees import fee_model_for, net_winnings
from marketedge.strategies.arbitrage.models import ArbitrageOpportunity, TradeLeg


@dataclass(frozen=True)
class QuoteView:
    venue: str
    price: Decimal
    available_size: Decimal
    received_at: datetime
    source_timestamp: datetime | None

    def age_ms(self, now: datetime) -> float:
        basis = self.source_timestamp or self.received_at
        return (now - basis).total_seconds() * 1000


@dataclass(frozen=True)
class SelectionQuotes:
    selection_id: uuid.UUID
    outcome_key: str
    best_back: QuoteView | None
    best_lay: QuoteView | None


@dataclass(frozen=True)
class ArbitrageFilters:
    min_net_roi: Decimal
    min_profit_gbp: Decimal
    max_quote_age_ms: int
    min_seconds_to_start: int
    in_play: bool
    default_bankroll_gbp: Decimal


def max_executable_bankroll(odds: list[Decimal], available_sizes: list[Decimal]) -> Decimal:
    """The capital solver referenced in spec section 31's pseudocode
    (`capital_solver.apply_limits`): the largest bankroll for which every
    leg's dutched stake still fits within that leg's available size."""
    inv_sum = overround(odds)
    weights = [(Decimal(1) / o) / inv_sum for o in odds]
    return min(size / weight for size, weight in zip(available_sizes, weights, strict=True))


def time_to_start_bucket(seconds_to_start: float) -> str:
    if seconds_to_start < 15 * 60:
        return "<15m"
    if seconds_to_start < 60 * 60:
        return "15-60m"
    if seconds_to_start < 6 * 3600:
        return "1-6h"
    if seconds_to_start < 24 * 3600:
        return "6-24h"
    if seconds_to_start < 48 * 3600:
        return "24-48h"
    return ">48h"


def detect_dutching(
    event_id: uuid.UUID,
    market_id: uuid.UUID,
    selections: list[SelectionQuotes],
    filters: ArbitrageFilters,
    now: datetime | None = None,
) -> ArbitrageOpportunity | None:
    now = now or datetime.now(UTC)
    priced: list[tuple[SelectionQuotes, QuoteView]] = [
        (s, s.best_back) for s in selections if s.best_back is not None
    ]
    if len(priced) < 2 or len(priced) != len(selections):
        return None  # every outcome needs a price, or it isn't a complete market

    odds = [quote.price for _, quote in priced]
    if overround(odds) >= 1:
        return None

    sizes = [quote.available_size for _, quote in priced]
    executable_bankroll = min(filters.default_bankroll_gbp, max_executable_bankroll(odds, sizes))
    stakes = dutch_stakes(executable_bankroll, odds)
    if stakes is None:
        return None

    legs = tuple(
        TradeLeg(
            venue=quote.venue,
            selection_id=selection.selection_id,
            side=Side.BACK,
            price=quote.price,
            stake=stake,
            available_size=quote.available_size,
            quote_received_at=quote.received_at,
            quote_source_timestamp=quote.source_timestamp,
        )
        for (selection, quote), stake in zip(priced, stakes, strict=True)
    )

    gross_worst_case = dutch_worst_case(stakes, odds)
    # Net worst case: for each outcome that "wins", every other stake is
    # lost outright (no commission on a loss) and the winning leg's gross
    # profit is taxed at that leg's own venue's commission rate.
    net_profits = [
        net_winnings(stakes[i] * odds[i] - sum(stakes, Decimal(0)), fee_model_for(legs[i].venue))
        for i in range(len(legs))
    ]
    net_worst_case = min(net_profits)

    capital_required = sum(stakes, Decimal(0))
    if capital_required <= 0:
        return None
    net_roi = net_worst_case / capital_required

    if net_worst_case < filters.min_profit_gbp or net_roi < filters.min_net_roi:
        return None

    data_age_ms = int(max(quote.age_ms(now) for _, quote in priced))
    if data_age_ms > filters.max_quote_age_ms:
        return None

    return ArbitrageOpportunity(
        opportunity_id=uuid.uuid4(),
        event_id=event_id,
        market_id=market_id,
        legs=legs,
        gross_roi=(gross_worst_case / capital_required) if capital_required else Decimal(0),
        net_roi=net_roi,
        worst_case_profit=net_worst_case,
        capital_required=capital_required,
        max_executable_size=max_executable_bankroll(odds, sizes),
        detected_at=now,
        expires_at=now + timedelta(milliseconds=filters.max_quote_age_ms),
        data_age_ms=data_age_ms,
    )


def detect_back_lay_for_selection(
    event_id: uuid.UUID,
    market_id: uuid.UUID,
    selection: SelectionQuotes,
    bookmaker_back: QuoteView,
    exchange_lay: QuoteView,
    filters: ArbitrageFilters,
    now: datetime | None = None,
) -> ArbitrageOpportunity | None:
    now = now or datetime.now(UTC)
    fee_model = fee_model_for(exchange_lay.venue)

    if exchange_lay.price - fee_model.commission_rate <= 0:
        return None
    if bookmaker_back.price <= exchange_lay.price:
        return None  # no plausible edge before even computing stakes

    max_back_from_exchange_liquidity = (
        exchange_lay.available_size
        * (exchange_lay.price - fee_model.commission_rate)
        / bookmaker_back.price
    )
    back_stake = min(
        filters.default_bankroll_gbp,
        bookmaker_back.available_size,
        max_back_from_exchange_liquidity,
    )
    if back_stake <= 0:
        return None

    lay_stake = lay_stake_for_equal_profit(
        back_stake, bookmaker_back.price, exchange_lay.price, fee_model.commission_rate
    )

    worst_case = min(
        profit_if_selection_wins(back_stake, bookmaker_back.price, lay_stake, exchange_lay.price),
        profit_if_selection_loses(back_stake, lay_stake, fee_model),
    )
    capital_required = back_stake + lay_stake * (exchange_lay.price - 1)
    if capital_required <= 0:
        return None
    net_roi = worst_case / capital_required

    if worst_case < filters.min_profit_gbp or net_roi < filters.min_net_roi:
        return None

    data_age_ms = int(max(bookmaker_back.age_ms(now), exchange_lay.age_ms(now)))
    if data_age_ms > filters.max_quote_age_ms:
        return None

    legs = (
        TradeLeg(
            venue=bookmaker_back.venue,
            selection_id=selection.selection_id,
            side=Side.BACK,
            price=bookmaker_back.price,
            stake=back_stake,
            available_size=bookmaker_back.available_size,
            quote_received_at=bookmaker_back.received_at,
            quote_source_timestamp=bookmaker_back.source_timestamp,
        ),
        TradeLeg(
            venue=exchange_lay.venue,
            selection_id=selection.selection_id,
            side=Side.LAY,
            price=exchange_lay.price,
            stake=lay_stake,
            available_size=exchange_lay.available_size,
            quote_received_at=exchange_lay.received_at,
            quote_source_timestamp=exchange_lay.source_timestamp,
        ),
    )

    max_executable = max(back_stake, max_back_from_exchange_liquidity)
    return ArbitrageOpportunity(
        opportunity_id=uuid.uuid4(),
        event_id=event_id,
        market_id=market_id,
        legs=legs,
        gross_roi=(
            profit_if_selection_wins(
                back_stake, bookmaker_back.price, lay_stake, exchange_lay.price
            )
            / capital_required
        ),
        net_roi=net_roi,
        worst_case_profit=worst_case,
        capital_required=capital_required,
        max_executable_size=max_executable,
        detected_at=now,
        expires_at=now + timedelta(milliseconds=filters.max_quote_age_ms),
        data_age_ms=data_age_ms,
    )
