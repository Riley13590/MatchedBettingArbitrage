"""Arbitrage strategy runner (Milestone 3).

Periodically scans known markets, builds a latest-quote snapshot per
market from Postgres, runs the detector, and persists opportunities —
tracking each one's observed lifetime by closing it out the moment it
stops being detected (spec section 42's arb-lifetime / survival-curve
requirement) rather than only ever recording a single point-in-time
snapshot.

Bookmaker venues (`oddsapi:*`) only ever quote the BACK side — see
`connectors.odds_provider.mapper` — so "the best LAY quote for a
selection" is always an exchange price without needing an explicit venue
filter; only the back-lay detector's *bookmaker* leg needs an explicit
`oddsapi:` prefix check.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from marketedge.config.settings import Settings, get_settings
from marketedge.domain.enums import Side
from marketedge.observability.logging import configure_logging, log_event
from marketedge.storage.db import session_scope
from marketedge.storage.orm import Event, Market
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.opportunities import OpportunityRepository
from marketedge.storage.repositories.quotes import QuoteRepository
from marketedge.storage.repositories.venues import VenueRepository
from marketedge.strategies.arbitrage.detector import (
    ArbitrageFilters,
    QuoteView,
    SelectionQuotes,
    detect_back_lay_for_selection,
    detect_dutching,
    time_to_start_bucket,
)
from marketedge.strategies.arbitrage.models import ArbitrageOpportunity

logger = logging.getLogger(__name__)

_SCAN_INTERVAL_SECONDS = 5.0
_QUOTE_LOOKBACK = timedelta(minutes=30)
_EVENT_SCAN_LIMIT = 200


def filters_from_settings(settings: Settings) -> ArbitrageFilters:
    return ArbitrageFilters(
        min_net_roi=settings.arbitrage_min_net_roi,
        min_profit_gbp=settings.arbitrage_min_profit_gbp,
        max_quote_age_ms=settings.arbitrage_max_quote_age_ms,
        min_seconds_to_start=settings.arbitrage_min_seconds_to_start,
        in_play=settings.arbitrage_in_play,
        default_bankroll_gbp=settings.arbitrage_default_bankroll_gbp,
    )


@dataclass(frozen=True)
class _OpenKey:
    market_id: uuid.UUID
    kind: str  # "DUTCH" or f"BACKLAY:{selection_id}"


def _best(
    rows: list[tuple[int, str, Decimal, Decimal | None, datetime, datetime | None]],
    side: str,
    venue_code_by_id: dict[int, str],
    venue_prefix: str | None = None,
) -> QuoteView | None:
    """`rows` are (venue_id, side, price, available_size, received_at,
    source_timestamp) tuples. Picks the best executable quote — highest
    price for BACK, lowest for LAY — optionally restricted to venues whose
    code starts with `venue_prefix`."""
    best: QuoteView | None = None
    for venue_id, row_side, price, available_size, received_at, source_timestamp in rows:
        if row_side != side:
            continue
        code = venue_code_by_id.get(venue_id)
        if code is None:
            continue
        if venue_prefix is not None and not code.startswith(venue_prefix):
            continue
        candidate = QuoteView(
            venue=code,
            price=price,
            available_size=available_size or Decimal(0),
            received_at=received_at,
            source_timestamp=source_timestamp,
        )
        if (
            best is None
            or side == Side.BACK.value
            and candidate.price > best.price
            or side == Side.LAY.value
            and candidate.price < best.price
        ):
            best = candidate
    return best


class ArbitrageRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._filters = filters_from_settings(settings)
        # market/selection key -> (opportunity_id, detected_at) for
        # opportunities this process currently believes are still live.
        self._open: dict[_OpenKey, tuple[uuid.UUID, datetime]] = {}

    async def scan_once(self) -> int:
        if not self._settings.arbitrage_enabled:
            return 0

        now = datetime.now(UTC)
        detected_this_cycle: set[_OpenKey] = set()
        scanned_market_ids: set[uuid.UUID] = set()
        persisted = 0

        async with session_scope() as session:
            venue_code_by_id = {v.id: v.code for v in await VenueRepository(session).list_all()}
            event_repo = EventRepository(session)
            market_repo = MarketRepository(session)
            quote_repo = QuoteRepository(session)
            opp_repo = OpportunityRepository(session)

            for event in await event_repo.list_upcoming(limit=_EVENT_SCAN_LIMIT):
                seconds_to_start = (event.start_time - now).total_seconds()
                if seconds_to_start < 0 and not self._filters.in_play:
                    continue
                if 0 <= seconds_to_start < self._filters.min_seconds_to_start:
                    continue

                for market_stub in await market_repo.list_for_event(event.id):
                    market = await market_repo.get_by_id(market_stub.id)
                    if market is None or len(market.selections) < 2:
                        continue
                    scanned_market_ids.add(market.id)

                    selections_quotes: list[SelectionQuotes] = []
                    bookmaker_back_by_selection: dict[uuid.UUID, QuoteView | None] = {}
                    exchange_lay_by_selection: dict[uuid.UUID, QuoteView | None] = {}

                    for selection in market.selections:
                        rows = [
                            (
                                q.venue_id,
                                q.side,
                                q.price,
                                q.available_size,
                                q.received_at,
                                q.source_timestamp,
                            )
                            for q in await quote_repo.latest_by_venue_and_side(
                                selection.id, since=now - _QUOTE_LOOKBACK
                            )
                        ]
                        best_back = _best(rows, Side.BACK.value, venue_code_by_id)
                        best_lay = _best(rows, Side.LAY.value, venue_code_by_id)
                        selections_quotes.append(
                            SelectionQuotes(
                                selection.id, selection.outcome_key, best_back, best_lay
                            )
                        )
                        bookmaker_back_by_selection[selection.id] = _best(
                            rows, Side.BACK.value, venue_code_by_id, venue_prefix="oddsapi:"
                        )
                        exchange_lay_by_selection[selection.id] = best_lay

                    persisted += await self._handle_dutching(
                        opp_repo, event, market, selections_quotes, now, detected_this_cycle
                    )
                    for selection in market.selections:
                        persisted += await self._handle_back_lay(
                            opp_repo,
                            event,
                            market,
                            selection.id,
                            bookmaker_back_by_selection[selection.id],
                            exchange_lay_by_selection[selection.id],
                            now,
                            detected_this_cycle,
                        )

            await self._close_stale(opp_repo, detected_this_cycle, scanned_market_ids, now)

        log_event(
            logger, "arbitrage_scan_complete", persisted=persisted, open_count=len(self._open)
        )
        return persisted

    async def _handle_dutching(
        self,
        opp_repo: OpportunityRepository,
        event: Event,
        market: Market,
        selections_quotes: list[SelectionQuotes],
        now: datetime,
        detected_this_cycle: set[_OpenKey],
    ) -> int:
        opp = detect_dutching(event.id, market.id, selections_quotes, self._filters, now=now)
        if opp is None:
            return 0
        key = _OpenKey(market.id, "DUTCH")
        detected_this_cycle.add(key)
        if key in self._open:
            return 0
        persisted_id = await self._persist(opp_repo, opp, event, market, "arbitrage_dutch")
        self._open[key] = (persisted_id, opp.detected_at)
        return 1

    async def _handle_back_lay(
        self,
        opp_repo: OpportunityRepository,
        event: Event,
        market: Market,
        selection_id: uuid.UUID,
        bookmaker_back: QuoteView | None,
        exchange_lay: QuoteView | None,
        now: datetime,
        detected_this_cycle: set[_OpenKey],
    ) -> int:
        if bookmaker_back is None or exchange_lay is None:
            return 0
        selection_quotes = SelectionQuotes(selection_id, "", None, None)
        opp = detect_back_lay_for_selection(
            event.id,
            market.id,
            selection_quotes,
            bookmaker_back,
            exchange_lay,
            self._filters,
            now=now,
        )
        if opp is None:
            return 0
        key = _OpenKey(market.id, f"BACKLAY:{selection_id}")
        detected_this_cycle.add(key)
        if key in self._open:
            return 0
        persisted_id = await self._persist(opp_repo, opp, event, market, "arbitrage_back_lay")
        self._open[key] = (persisted_id, opp.detected_at)
        return 1

    async def _persist(
        self,
        opp_repo: OpportunityRepository,
        opp: ArbitrageOpportunity,
        event: Event,
        market: Market,
        strategy: str,
    ) -> uuid.UUID:
        seconds_to_start = max(0.0, (event.start_time - opp.detected_at).total_seconds())
        venues = ",".join(sorted({leg.venue for leg in opp.legs}))
        snapshot = {
            "legs": [
                {
                    "venue": leg.venue,
                    "selection_id": str(leg.selection_id),
                    "side": leg.side.value,
                    "price": str(leg.price),
                    "stake": str(leg.stake),
                    "available_size": str(leg.available_size),
                    "quote_received_at": leg.quote_received_at.isoformat(),
                }
                for leg in opp.legs
            ],
            "gross_roi": str(opp.gross_roi),
        }
        row = await opp_repo.create(
            strategy=strategy,
            event_id=event.id,
            market_id=market.id,
            detected_at=opp.detected_at,
            expires_at=opp.expires_at,
            expected_profit=opp.worst_case_profit,
            expected_roi=opp.net_roi,
            worst_case_profit=opp.worst_case_profit,
            confidence=Decimal("1.0"),
            status="ACTIVE",
            snapshot=snapshot,
            sport=event.sport,
            competition=event.competition,
            market_family=market.market_type,
            venues=venues,
            time_to_start_bucket=time_to_start_bucket(seconds_to_start),
            quote_age_ms_at_detection=Decimal(opp.data_age_ms),
            executable_stake_gbp=opp.capital_required,
            executable_edge_gbp=opp.executable_edge_gbp,
        )
        # `opp.opportunity_id` (generated in the detector) is never used as
        # a lookup key — the DB row's own primary key (`row.id`) is what
        # close_expired/record_verification address later, since those are
        # separate UUIDs by construction.
        log_event(
            logger,
            "arbitrage_opportunity_detected",
            strategy=strategy,
            market_id=str(market.id),
            net_roi=str(opp.net_roi),
            worst_case_profit=str(opp.worst_case_profit),
        )
        return row.id

    async def _close_stale(
        self,
        opp_repo: OpportunityRepository,
        detected_this_cycle: set[_OpenKey],
        scanned_market_ids: set[uuid.UUID],
        now: datetime,
    ) -> None:
        """Closes any opportunity this process previously opened that
        didn't re-detect this cycle, recording its observed lifetime (spec
        section 42) and a best-effort feed-validity classification (spec
        section 41.5) based on evidence actually available: if we still
        scanned that market this cycle and simply found no arb, the prices
        genuinely moved; if the market fell out of the scan entirely (event
        started, dropped past the horizon, DB hiccup), we can't tell price
        movement from a suspended/stale feed, so it's honestly `UNKNOWN`
        rather than a guess."""
        stale_keys = [key for key in self._open if key not in detected_this_cycle]
        for key in stale_keys:
            opportunity_id, detected_at = self._open.pop(key)
            lifetime_ms = Decimal(str((now - detected_at).total_seconds() * 1000))
            outcome = "PRICE_MOVED" if key.market_id in scanned_market_ids else "UNKNOWN"
            await opp_repo.close_expired(opportunity_id, now, lifetime_ms)
            await opp_repo.record_verification(
                opportunity_id,
                outcome=outcome,
                verified_at=now,
                bookmaker_price=None,
                exchange_price=None,
            )


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings.log_level, service="strategy-arbitrage")
    runner = ArbitrageRunner(settings)

    if not settings.arbitrage_enabled:
        log_event(logger, "arbitrage_disabled", level=logging.INFO)
        return

    while True:
        try:
            await runner.scan_once()
        except Exception:  # noqa: BLE001 — one bad cycle must not kill the loop
            log_event(logger, "arbitrage_scan_failed", level=logging.WARNING)
        await asyncio.sleep(_SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
