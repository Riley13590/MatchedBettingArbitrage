"""Ingestion worker entrypoint: `python -m marketedge.ingestion.orchestrator`.

Wires a connector's discovery + quote methods into the storage repositories
and `QuoteProcessor`. This module only depends on the
`MarketDataConnector` protocol plus `marketedge.storage`/`marketedge.domain`
— vendor-specific mapping already happened inside the connector.

Startup with no Betfair credentials configured is a supported, non-error
state (spec section 2.1 — "Run in observation/paper mode by default"): the
worker logs that the connector is unconfigured, reports `connector_up=0`,
and idles rather than crash-looping.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_asyncio

from marketedge.config.settings import get_settings
from marketedge.connectors.base import TimeWindow
from marketedge.connectors.betfair import BetfairConnector
from marketedge.connectors.betfair.mapper import QuoteDraft
from marketedge.ingestion.heartbeat import heartbeat_loop
from marketedge.ingestion.quote_processor import QuoteProcessor, ResolvedQuote
from marketedge.observability.logging import configure_logging, log_event
from marketedge.storage.db import session_scope
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.venues import VenueRepository

logger = logging.getLogger(__name__)

_DISCOVERY_WINDOW = timedelta(days=7)
_DISCOVERY_INTERVAL_SECONDS = 300.0
_POLL_FALLBACK_INTERVAL_SECONDS = 5.0


@dataclass
class SelectionIndex:
    """vendor_market_id -> {vendor_selection_id -> (canonical_selection_id, sport)}"""

    by_market: dict[str, dict[str, tuple[uuid.UUID, str]]]

    def vendor_market_ids(self) -> list[str]:
        return list(self.by_market.keys())

    def resolve(
        self, vendor_market_id: str, vendor_selection_id: str
    ) -> tuple[uuid.UUID, str] | None:
        return self.by_market.get(vendor_market_id, {}).get(vendor_selection_id)


async def discover(connector: BetfairConnector, venue_id: int) -> SelectionIndex:
    """Enumerates events/markets/selections for the configured sports and
    upserts them into the canonical schema, returning an index used to
    resolve incoming quotes to canonical selection IDs."""
    window = TimeWindow(
        start_utc=datetime.now(UTC),
        end_utc=datetime.now(UTC) + _DISCOVERY_WINDOW,
    )
    index: dict[str, dict[str, tuple[uuid.UUID, str]]] = {}

    async with session_scope() as session:
        event_repo = EventRepository(session)
        market_repo = MarketRepository(session)

        events = await connector.list_events(window)
        for event_draft in events:
            event = await event_repo.upsert_from_vendor(
                venue_id=venue_id,
                vendor_event_id=event_draft.vendor_event_id,
                sport=event_draft.sport,
                competition=event_draft.competition,
                start_time=event_draft.start_time_utc,
                home_participant=event_draft.home_participant,
                away_participant=event_draft.away_participant,
                raw_name=event_draft.raw_name,
            )

            markets = await connector.list_markets(event_draft.vendor_event_id)
            for market_draft in markets:
                market = await market_repo.upsert(
                    event_id=event.id,
                    market_type=market_draft.market_type,
                    period=market_draft.period,
                    line=market_draft.line,
                    settlement_scope=market_draft.settlement_scope,
                )
                selection_map: dict[str, tuple[uuid.UUID, str]] = {}
                for runner in market_draft.runners:
                    selection = await market_repo.upsert_selection(
                        market_id=market.id,
                        outcome_key=runner.outcome_key,
                        display_name=runner.display_name,
                    )
                    selection_map[runner.vendor_selection_id] = (selection.id, event_draft.sport)
                index[market_draft.vendor_market_id] = selection_map

    log_event(logger, "discovery_complete", market_count=len(index))
    return SelectionIndex(by_market=index)


async def _handle_quote_draft(
    processor: QuoteProcessor,
    venue_id: int,
    venue_code: str,
    index: SelectionIndex,
    draft: QuoteDraft,
) -> None:
    resolved = index.resolve(draft.vendor_market_id, draft.vendor_selection_id)
    if resolved is None:
        return  # quote for a market/selection outside the current discovery index
    selection_id, sport = resolved

    quote = ResolvedQuote(
        venue_id=venue_id,
        venue_code=venue_code,
        sport=sport,
        selection_id=selection_id,
        side=draft.side,
        price=draft.price,
        available_size=draft.available_size,
        is_live=draft.is_live,
        source_timestamp_utc=draft.source_timestamp_utc,
    )
    async with session_scope() as session:
        await processor.process(session, quote)


async def run_streaming(
    connector: BetfairConnector, processor: QuoteProcessor, venue_id: int, index: SelectionIndex
) -> None:
    async for draft in connector.stream_quotes(index.vendor_market_ids()):
        await _handle_quote_draft(processor, venue_id, connector.venue, index, draft)


async def run_polling(
    connector: BetfairConnector, processor: QuoteProcessor, venue_id: int, index: SelectionIndex
) -> None:
    while True:
        drafts = await connector.get_quotes(index.vendor_market_ids())
        for draft in drafts:
            await _handle_quote_draft(processor, venue_id, connector.venue, index, draft)
        await asyncio.sleep(_POLL_FALLBACK_INTERVAL_SECONDS)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, service="worker-ingest")

    connector = BetfairConnector(settings)
    redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    processor = QuoteProcessor(redis_client)

    async with session_scope() as session:
        venue = await VenueRepository(session).get_by_code(connector.venue)
    if venue is None:
        log_event(logger, "venue_not_seeded", level=logging.ERROR, venue=connector.venue)
        return

    heartbeat_task = asyncio.create_task(heartbeat_loop(connector))

    if not connector.is_configured:
        log_event(
            logger,
            "betfair_not_configured",
            level=logging.WARNING,
            hint="Set BETFAIR_APP_KEY/USERNAME/PASSWORD/CERT_PATH/KEY_PATH to begin ingestion",
        )
        await heartbeat_task
        return

    try:
        while True:
            index = await discover(connector, venue.id)
            if not index.vendor_market_ids():
                log_event(logger, "no_markets_discovered", level=logging.WARNING)
                await asyncio.sleep(_DISCOVERY_INTERVAL_SECONDS)
                continue

            try:
                await asyncio.wait_for(
                    run_streaming(connector, processor, venue.id, index),
                    timeout=_DISCOVERY_INTERVAL_SECONDS,
                )
            except TimeoutError:
                pass  # re-run discovery on the configured interval
            except Exception:  # noqa: BLE001 — fall back to polling on any stream failure
                log_event(logger, "stream_failed_falling_back_to_polling", level=logging.WARNING)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        run_polling(connector, processor, venue.id, index),
                        timeout=_DISCOVERY_INTERVAL_SECONDS,
                    )
    finally:
        heartbeat_task.cancel()
        await connector.aclose()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
