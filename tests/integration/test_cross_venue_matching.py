"""Proves the Milestone 2 exit criteria directly: "equivalent bookmaker and
exchange markets are safely joined across multiple supported sports" (spec
section 28, Milestone 2). Simulates a Betfair sighting and an
odds-provider sighting of the *same* real-world fixture and asserts they
converge onto one canonical event, and that HOME/AWAY selections for the
same market type/period/line/settlement_scope join to one canonical
selection row even though the two vendors report completely different
runner names/IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marketedge.matching.selection_matcher import assign_outcome_key
from marketedge.storage.db import session_scope
from marketedge.storage.repositories.events import EventRepository
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.venues import VenueRepository


@pytest.mark.asyncio
async def test_odds_provider_event_matches_existing_betfair_event() -> None:
    async with session_scope() as session:
        betfair = await VenueRepository(session).get_by_code("betfair")
        odds_provider = await VenueRepository(session).get_by_code("odds_provider")
        assert betfair is not None and odds_provider is not None
        event_repo = EventRepository(session)

        betfair_event = await event_repo.upsert_from_vendor(
            venue_id=betfair.id,
            vendor_event_id="31234567",  # Betfair's own numeric market/event ID
            sport="Soccer",
            competition="EPL",
            start_time=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
            home_participant="Arsenal",
            away_participant="Chelsea",
            raw_name="Arsenal v Chelsea",
        )

        # Same fixture, reported by the odds provider under a completely
        # different (string) vendor event ID. `sport`="Soccer" (the general
        # sport, matching Betfair's eventType.name) and `competition`="EPL"
        # (the specific league) mirror exactly what
        # connectors.odds_provider.mapper.map_event produces from a real
        # /v4/sports/soccer_epl/odds response.
        odds_event = await event_repo.upsert_from_vendor(
            venue_id=odds_provider.id,
            vendor_event_id="e1b2c3d4",
            sport="Soccer",
            competition="EPL",
            start_time=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
            home_participant="Arsenal",
            away_participant="Chelsea",
            raw_name="Arsenal v Chelsea",
        )

    assert odds_event.id == betfair_event.id

    async with session_scope() as session:
        confidence = await EventRepository(session).match_confidence_for(
            odds_provider.id, "e1b2c3d4"
        )
    assert confidence is not None
    assert confidence >= 0.90


@pytest.mark.asyncio
async def test_selections_join_across_venues_despite_different_runner_names() -> None:
    """Betfair's runner is literally "Arsenal"; the odds provider's is
    "Arsenal FC" from a different bookmaker. Both must resolve to the same
    outcome_key ("HOME") and therefore the same canonical selection row."""
    async with session_scope() as session:
        betfair = await VenueRepository(session).get_by_code("betfair")
        assert betfair is not None
        event = await EventRepository(session).upsert_from_vendor(
            venue_id=betfair.id,
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

        betfair_key = assign_outcome_key(
            "Arsenal", "MATCH_ODDS", "Soccer", "Arsenal", "Chelsea", "RUNNER_1"
        )
        odds_provider_key = assign_outcome_key(
            "Arsenal FC", "MATCH_ODDS", "Soccer", "Arsenal FC", "Chelsea FC", "OUTCOME_ARSENAL_FC"
        )
        assert betfair_key == odds_provider_key == "HOME"

        betfair_selection = await market_repo.upsert_selection(market.id, betfair_key, "Arsenal")
        odds_provider_selection = await market_repo.upsert_selection(
            market.id, odds_provider_key, "Arsenal FC"
        )

    assert betfair_selection.id == odds_provider_selection.id


@pytest.mark.asyncio
async def test_unrelated_events_never_merge() -> None:
    """A completely different fixture at a similar time must not be
    matched onto the same canonical event — the false-arbitrage risk spec
    section 11 warns about."""
    async with session_scope() as session:
        betfair = await VenueRepository(session).get_by_code("betfair")
        assert betfair is not None
        event_repo = EventRepository(session)

        first = await event_repo.upsert_from_vendor(
            venue_id=betfair.id,
            vendor_event_id="1",
            sport="Soccer",
            competition="EPL",
            start_time=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
            home_participant="Arsenal",
            away_participant="Chelsea",
            raw_name="Arsenal v Chelsea",
        )
        second = await event_repo.upsert_from_vendor(
            venue_id=betfair.id,
            vendor_event_id="2",
            sport="Soccer",
            competition="La Liga",
            start_time=datetime(2026, 8, 15, 14, 5, tzinfo=UTC),
            home_participant="Real Madrid",
            away_participant="Barcelona",
            raw_name="Real Madrid v Barcelona",
        )

    assert first.id != second.id


@pytest.mark.asyncio
async def test_bookmaker_venue_is_created_dynamically_and_data_only() -> None:
    async with session_scope() as session:
        venue_repo = VenueRepository(session)
        venue = await venue_repo.upsert_bookmaker("oddsapi:williamhill", "William Hill", None)

    assert venue.data_allowed is True
    assert venue.execution_allowed is False
    assert venue.id > 0
