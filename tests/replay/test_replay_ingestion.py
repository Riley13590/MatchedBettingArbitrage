"""Deterministic replay test (spec section 27.3): the same fixed quote
stream, run through `QuoteProcessor` twice, must produce identical
persisted rows. Uses a real Postgres (DATABASE_URL) and an in-memory fake
Redis so the test is hermetic w.r.t. the cache layer while still exercising
the real durable-storage path.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text

from marketedge.domain.enums import Side
from marketedge.ingestion.quote_processor import QuoteProcessor, ResolvedQuote
from marketedge.storage.db import get_engine, session_scope
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.quotes import QuoteRepository
from marketedge.storage.repositories.venues import VenueRepository


async def _seed_selection() -> tuple[uuid.UUID, int]:
    async with session_scope() as session:
        venue = await VenueRepository(session).get_by_code("betfair")
        assert venue is not None
        event = await EventRepository(session).upsert_from_vendor(
            venue_id=venue.id,
            vendor_event_id="31234567",
            sport="Soccer",
            competition="EPL",
            start_time=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
            home_participant="Arsenal",
            away_participant="Chelsea",
            raw_name="Arsenal v Chelsea",
        )
        market_repo = MarketRepository(session)
        market = await market_repo.upsert(
            event_id=event.id,
            market_type="MATCH_ODDS",
            period="FULL_TIME",
            line=None,
            settlement_scope="REGULATION_ONLY",
        )
        selection = await market_repo.upsert_selection(market.id, "HOME", "Arsenal")
        venue_id = venue.id
    return selection.id, venue_id


def _fixed_quote_sequence(venue_id: int, selection_id: uuid.UUID) -> list[ResolvedQuote]:
    base_ts = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    return [
        ResolvedQuote(
            venue_id=venue_id,
            venue_code="betfair",
            sport="Soccer",
            selection_id=selection_id,
            side=Side.BACK,
            price=Decimal("2.02"),
            available_size=Decimal("100"),
            is_live=False,
            source_timestamp_utc=base_ts,
        ),
        ResolvedQuote(
            venue_id=venue_id,
            venue_code="betfair",
            sport="Soccer",
            selection_id=selection_id,
            side=Side.LAY,
            price=Decimal("2.06"),
            available_size=Decimal("80"),
            is_live=False,
            source_timestamp_utc=base_ts,
        ),
        ResolvedQuote(
            venue_id=venue_id,
            venue_code="betfair",
            sport="Soccer",
            selection_id=selection_id,
            side=Side.BACK,
            price=Decimal("2.04"),
            available_size=Decimal("50"),
            is_live=False,
            source_timestamp_utc=base_ts,
        ),
    ]


@pytest.mark.asyncio
async def test_replaying_the_same_quote_stream_produces_the_same_rows() -> None:
    processor = QuoteProcessor(FakeRedis())

    selection_id, venue_id = await _seed_selection()
    sequence = _fixed_quote_sequence(venue_id, selection_id)
    async with session_scope() as session:
        for quote in sequence:
            await processor.process(session, quote)

    async with session_scope() as session:
        first_run = await QuoteRepository(session).latest_for_selection(selection_id, limit=10)
    first_snapshot = sorted(
        (row.side, str(row.price), str(row.available_size)) for row in first_run
    )

    # Truncate quotes only (keep the seeded event/market/selection) and replay.
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE quotes RESTART IDENTITY CASCADE"))

    async with session_scope() as session:
        for quote in sequence:
            await processor.process(session, quote)

    async with session_scope() as session:
        second_run = await QuoteRepository(session).latest_for_selection(selection_id, limit=10)
    second_snapshot = sorted(
        (row.side, str(row.price), str(row.available_size)) for row in second_run
    )

    assert first_snapshot == second_snapshot
    assert len(first_snapshot) == len(sequence)
