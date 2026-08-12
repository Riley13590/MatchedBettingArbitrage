"""Odds-provider (bookmaker) discovery + ingestion loop.

Separate from `orchestrator.py`'s Betfair-shaped discover/stream/poll
functions because this connector's API returns an entire sport's events,
bookmakers, markets and prices in one call — see
`connectors.odds_provider.mapper` for why that means a different ingestion
shape rather than forcing it through the same list_events -> list_markets
-> get_quotes waterfall.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import redis.asyncio as redis_asyncio

from marketedge.config.settings import Settings, get_settings
from marketedge.connectors.odds_provider import OddsProviderConnector, SportRef
from marketedge.ingestion.budget import ApiCreditLedger
from marketedge.ingestion.discovery_scheduler import DiscoveryScheduler
from marketedge.ingestion.heartbeat import heartbeat_loop
from marketedge.ingestion.quote_processor import QuoteProcessor, ResolvedQuote
from marketedge.observability.logging import log_event
from marketedge.storage.db import session_scope
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.venues import VenueRepository

logger = logging.getLogger(__name__)

_SCHEDULER_TICK_SECONDS = 15.0
_URGENT_BUCKETS = {"lt_1h", "1h_6h"}


async def discover_and_ingest_sport(
    connector: OddsProviderConnector,
    ledger: ApiCreditLedger,
    processor: QuoteProcessor,
    odds_provider_venue_id: int,
    sport: SportRef,
) -> datetime | None:
    """Fetches, maps and persists one sport's full snapshot. Returns the
    earliest event start time seen (for the discovery scheduler's next-poll
    bucketing), or None if the sport currently has no events."""
    snapshots, usage = await connector.get_sport_snapshot(sport)

    earliest_start: datetime | None = None
    quote_count = 0

    async with session_scope() as session:
        await ledger.record(
            session,
            usage,
            sport_key=sport.key,
            market_keys=connector.markets,
            regions=connector.regions,
        )

        event_repo = EventRepository(session)
        market_repo = MarketRepository(session)
        venue_repo = VenueRepository(session)

        for event_draft, batches in snapshots:
            if earliest_start is None or event_draft.start_time_utc < earliest_start:
                earliest_start = event_draft.start_time_utc

            event = await event_repo.upsert_from_vendor(
                venue_id=odds_provider_venue_id,
                vendor_event_id=event_draft.vendor_event_id,
                sport=event_draft.sport,
                competition=event_draft.competition,
                start_time=event_draft.start_time_utc,
                home_participant=event_draft.home_participant,
                away_participant=event_draft.away_participant,
                raw_name=event_draft.raw_name,
            )

            for batch in batches:
                bookmaker_venue = await venue_repo.upsert_bookmaker(
                    code=f"oddsapi:{batch.bookmaker_key}",
                    name=batch.bookmaker_title,
                    evidence_url=None,
                )
                market = await market_repo.upsert(
                    event_id=event.id,
                    market_type=batch.market.market_type,
                    period=batch.market.period,
                    line=batch.market.line,
                    settlement_scope=batch.market.settlement_scope,
                )
                selection_by_vendor_id = {}
                for runner in batch.market.runners:
                    selection = await market_repo.upsert_selection(
                        market_id=market.id,
                        outcome_key=runner.outcome_key,
                        display_name=runner.display_name,
                    )
                    selection_by_vendor_id[runner.vendor_selection_id] = selection.id

                for quote in batch.quotes:
                    selection_id = selection_by_vendor_id.get(quote.vendor_selection_id)
                    if selection_id is None:
                        continue
                    await processor.process(
                        session,
                        ResolvedQuote(
                            venue_id=bookmaker_venue.id,
                            venue_code=bookmaker_venue.code,
                            sport=event_draft.sport,
                            selection_id=selection_id,
                            side=quote.side,
                            price=quote.price,
                            available_size=quote.available_size,
                            is_live=quote.is_live,
                            source_timestamp_utc=quote.source_timestamp_utc,
                        ),
                    )
                    quote_count += 1

    log_event(
        logger,
        "odds_provider_sport_ingested",
        sport=sport.key,
        events=len(snapshots),
        quotes=quote_count,
        credits_used=usage.credits_used,
        remaining_credits=usage.remaining_credits_reported,
    )
    return earliest_start


async def run(settings: Settings | None = None) -> None:
    """Entrypoint driven by adaptive per-sport polling (spec section 41.3)
    with graceful budget degradation (spec section 41.6): as the soft cap
    approaches, only sports whose last-known nearest event is in an urgent
    bucket keep polling; at the hard cap, discovery stops until next month
    rather than erroring."""
    settings = settings or get_settings()
    connector = OddsProviderConnector(settings)
    redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    processor = QuoteProcessor(redis_client)
    ledger = ApiCreditLedger(
        provider="the_odds_api",
        soft_budget=settings.odds_provider_soft_monthly_budget,
        hard_budget=settings.odds_provider_hard_monthly_budget,
    )
    scheduler = DiscoveryScheduler(settings)

    heartbeat_task = asyncio.create_task(heartbeat_loop(connector))

    if not connector.is_configured:
        log_event(
            logger,
            "odds_provider_not_configured",
            level=logging.WARNING,
            hint="Set ODDS_PROVIDER_API_KEY to begin bookmaker-odds ingestion",
        )
        await heartbeat_task
        return

    async with session_scope() as session:
        venue = await VenueRepository(session).get_by_code("odds_provider")
    if venue is None:
        log_event(logger, "venue_not_seeded", level=logging.ERROR, venue="odds_provider")
        heartbeat_task.cancel()
        return

    last_known_bucket: dict[str, str] = {}

    try:
        while True:
            now = datetime.now(UTC)
            sports, sports_usage = await connector.list_sports()
            async with session_scope() as session:
                await ledger.record(session, sports_usage)
                budget = await ledger.status(session)

            if budget.over_hard:
                log_event(logger, "odds_provider_hard_budget_reached", level=logging.WARNING)
                await asyncio.sleep(_SCHEDULER_TICK_SECONDS * 20)
                continue

            for sport in sports:
                if not scheduler.is_due(sport.key, now):
                    continue
                if budget.over_soft and last_known_bucket.get(sport.key) not in _URGENT_BUCKETS:
                    continue  # degrade: defer non-urgent sports until budget recovers

                try:
                    earliest_start = await discover_and_ingest_sport(
                        connector, ledger, processor, venue.id, sport
                    )
                except Exception:  # noqa: BLE001 — one sport's failure must not kill the loop
                    log_event(
                        logger,
                        "odds_provider_sport_ingest_failed",
                        level=logging.WARNING,
                        sport=sport.key,
                    )
                    continue

                time_to_start = earliest_start - now if earliest_start else None
                scheduler.mark_polled(sport.key, now, time_to_start)
                bucket = scheduler.bucket_label(sport.key)
                if bucket is not None:
                    last_known_bucket[sport.key] = bucket

            await asyncio.sleep(_SCHEDULER_TICK_SECONDS)
    finally:
        heartbeat_task.cancel()
        await connector.aclose()
        await redis_client.aclose()
