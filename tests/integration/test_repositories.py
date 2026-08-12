"""Integration tests against a real Postgres (DATABASE_URL) — spec section
27.2/33: repositories are exercised end-to-end, not mocked. Requires the
`0001_initial_schema` migration to already be applied (CI runs `alembic
upgrade head` before `pytest`; see Makefile `migrate` target locally)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from marketedge.domain.enums import Side
from marketedge.storage.db import session_scope
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.quotes import QuoteRepository
from marketedge.storage.repositories.venues import VenueRepository


@pytest.mark.asyncio
async def test_venue_seed_data_present() -> None:
    async with session_scope() as session:
        betfair = await VenueRepository(session).get_by_code("betfair")
    assert betfair is not None
    assert betfair.data_allowed is True
    assert betfair.execution_allowed is False


@pytest.mark.asyncio
async def test_event_upsert_from_vendor_is_idempotent() -> None:
    async with session_scope() as session:
        venue = await VenueRepository(session).get_by_code("betfair")
        assert venue is not None
        repo = EventRepository(session)
        first = await repo.upsert_from_vendor(
            venue_id=venue.id,
            vendor_event_id="31234567",
            sport="Soccer",
            competition="EPL",
            start_time=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
            home_participant="Arsenal",
            away_participant="Chelsea",
            raw_name="Arsenal v Chelsea",
        )
        second = await repo.upsert_from_vendor(
            venue_id=venue.id,
            vendor_event_id="31234567",
            sport="Soccer",
            competition="EPL",
            start_time=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
            home_participant="Arsenal",
            away_participant="Chelsea",
            raw_name="Arsenal v Chelsea",
        )
    assert first.id == second.id


@pytest.mark.asyncio
async def test_market_and_quote_round_trip() -> None:
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

        quote_repo = QuoteRepository(session)
        await quote_repo.append(
            venue_id=venue.id,
            selection_id=selection.id,
            side=Side.BACK.value,
            price=Decimal("2.04"),
            available_size=Decimal("120.50"),
            source_timestamp=None,
            received_at=datetime.now(UTC),
            is_live=False,
            raw_payload=None,
        )

    async with session_scope() as session:
        latest = await QuoteRepository(session).latest_for_selection(selection.id)
    assert len(latest) == 1
    assert latest[0].price == Decimal("2.04000")
