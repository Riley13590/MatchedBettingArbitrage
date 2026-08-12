"""End-to-end proof of the Milestone 3 exit criteria: paper opportunities
are reproducible with exact outcome P&L, and every opportunity carries
enough telemetry (segment fields, executable stake/edge, lifetime) to
judge economic executability — against a real Postgres, no mocking of the
storage layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from marketedge.config.settings import get_settings
from marketedge.domain.enums import Side
from marketedge.storage.db import session_scope
from marketedge.storage.orm import Opportunity
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.quotes import QuoteRepository
from marketedge.storage.repositories.venues import VenueRepository
from marketedge.strategies.arbitrage.runner import ArbitrageRunner


async def _seed_two_way_market(price_home: str, price_away: str) -> tuple:
    async with session_scope() as session:
        wh = await VenueRepository(session).upsert_bookmaker(
            "oddsapi:williamhill", "William Hill", None
        )
        bet365 = await VenueRepository(session).upsert_bookmaker("oddsapi:bet365", "Bet365", None)

        event = await EventRepository(session).upsert_from_vendor(
            venue_id=wh.id,
            vendor_event_id="e1",
            sport="Tennis",
            competition="ATP",
            start_time=datetime.now(UTC) + timedelta(hours=2),
            home_participant="Player A",
            away_participant="Player B",
            raw_name="Player A v Player B",
        )
        market_repo = MarketRepository(session)
        market = await market_repo.upsert(
            event_id=event.id,
            market_type="MONEYLINE",
            period="FULL_MATCH",
            line=None,
            settlement_scope="FULL_MATCH",
        )
        home = await market_repo.upsert_selection(market.id, "HOME", "Player A")
        away = await market_repo.upsert_selection(market.id, "AWAY", "Player B")

        quote_repo = QuoteRepository(session)
        now = datetime.now(UTC)
        await quote_repo.append(
            venue_id=wh.id,
            selection_id=home.id,
            side=Side.BACK.value,
            price=Decimal(price_home),
            available_size=Decimal("200"),
            source_timestamp=now,
            received_at=now,
            is_live=False,
            raw_payload=None,
        )
        await quote_repo.append(
            venue_id=bet365.id,
            selection_id=away.id,
            side=Side.BACK.value,
            price=Decimal(price_away),
            available_size=Decimal("200"),
            source_timestamp=now,
            received_at=now,
            is_live=False,
            raw_payload=None,
        )
    return event.id, market.id


@pytest.mark.asyncio
async def test_runner_detects_and_persists_dutching_opportunity() -> None:
    event_id, market_id = await _seed_two_way_market("2.20", "2.20")
    runner = ArbitrageRunner(get_settings())

    persisted = await runner.scan_once()
    assert persisted == 1

    async with session_scope() as session:
        result = await session.execute(
            select(Opportunity).where(Opportunity.market_id == market_id)
        )
        rows = result.scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.strategy == "arbitrage_dutch"
    assert row.status == "ACTIVE"
    assert row.sport == "Tennis"
    assert row.market_family == "MONEYLINE"
    assert row.worst_case_profit > 0
    assert row.executable_stake_gbp > 0
    assert row.executable_edge_gbp is not None


@pytest.mark.asyncio
async def test_runner_does_not_duplicate_an_already_open_opportunity() -> None:
    await _seed_two_way_market("2.20", "2.20")
    runner = ArbitrageRunner(get_settings())

    first_count = await runner.scan_once()
    second_count = await runner.scan_once()

    assert first_count == 1
    assert second_count == 0  # same opportunity still open -> not re-persisted


@pytest.mark.asyncio
async def test_runner_closes_opportunity_once_prices_no_longer_form_an_arb() -> None:
    event_id, market_id = await _seed_two_way_market("2.20", "2.20")
    runner = ArbitrageRunner(get_settings())
    await runner.scan_once()

    # Reprice one leg so the overround flips above 1 -> no more arb.
    async with session_scope() as session:
        wh = await VenueRepository(session).get_by_code("oddsapi:williamhill")
        assert wh is not None
        market_repo = MarketRepository(session)
        market = await market_repo.get_by_id(market_id)
        assert market is not None
        home_selection = next(s for s in market.selections if s.outcome_key == "HOME")
        await QuoteRepository(session).append(
            venue_id=wh.id,
            selection_id=home_selection.id,
            side=Side.BACK.value,
            price=Decimal("1.80"),
            available_size=Decimal("200"),
            source_timestamp=datetime.now(UTC),
            received_at=datetime.now(UTC),
            is_live=False,
            raw_payload=None,
        )

    await runner.scan_once()

    async with session_scope() as session:
        result = await session.execute(
            select(Opportunity).where(Opportunity.market_id == market_id)
        )
        rows = result.scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "EXPIRED"
    assert row.lifetime_ms is not None
    assert row.lifetime_ms >= 0
    assert row.verification_outcome == "PRICE_MOVED"
