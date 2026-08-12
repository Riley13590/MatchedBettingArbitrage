from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.domain.enums import EventStatus
from marketedge.matching.confidence import MatchCandidate
from marketedge.matching.event_matcher import MatchDecision, find_best_match
from marketedge.storage.orm import Event, VendorEvent

_MATCH_CANDIDATE_WINDOW = timedelta(hours=6)
_MAX_MATCH_CANDIDATES = 25


class EventRepository:
    """Persists canonical events and the vendor-event mapping that produced
    them. When a vendor reports an event this repository hasn't seen from
    that venue before, it searches other venues' recent canonical events
    for a match (spec section 11) before creating a new one — this is what
    lets a Betfair event and the equivalent odds-provider event converge on
    one canonical row instead of duplicating it per venue.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, event_id: uuid.UUID) -> Event | None:
        return await self._session.get(Event, event_id)

    async def list_upcoming(self, limit: int = 100) -> list[Event]:
        result = await self._session.execute(
            select(Event)
            .where(Event.status.in_([EventStatus.SCHEDULED.value, EventStatus.IN_PLAY.value]))
            .order_by(Event.start_time)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def match_confidence_for(self, venue_id: int, vendor_event_id: str) -> float | None:
        result = await self._session.execute(
            select(VendorEvent.match_confidence).where(
                VendorEvent.venue_id == venue_id, VendorEvent.vendor_event_id == vendor_event_id
            )
        )
        confidence = result.scalar_one_or_none()
        return float(confidence) if confidence is not None else None

    async def min_match_confidence_by_event(
        self, event_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, float]:
        """Lowest cross-venue match confidence recorded for each event —
        drives the mapping-confidence UI (Milestone 2 deliverable). An
        event with no entries here was only ever seen from one venue, so
        there was nothing to confirm a match against."""
        if not event_ids:
            return {}
        result = await self._session.execute(
            select(VendorEvent.canonical_event_id, VendorEvent.match_confidence).where(
                VendorEvent.canonical_event_id.in_(event_ids),
                VendorEvent.match_confidence.is_not(None),
            )
        )
        lowest: dict[uuid.UUID, float] = {}
        for event_id, confidence in result.all():
            value = float(confidence)
            if event_id not in lowest or value < lowest[event_id]:
                lowest[event_id] = value
        return lowest

    async def _find_candidates(self, sport: str, start_time: datetime) -> list[Event]:
        result = await self._session.execute(
            select(Event)
            .where(
                Event.sport == sport,
                Event.start_time >= start_time - _MATCH_CANDIDATE_WINDOW,
                Event.start_time <= start_time + _MATCH_CANDIDATE_WINDOW,
            )
            .limit(_MAX_MATCH_CANDIDATES)
        )
        return list(result.scalars().all())

    async def upsert_from_vendor(
        self,
        venue_id: int,
        vendor_event_id: str,
        sport: str,
        competition: str,
        start_time: datetime,
        home_participant: str | None,
        away_participant: str | None,
        raw_name: str,
    ) -> Event:
        result = await self._session.execute(
            select(VendorEvent).where(
                VendorEvent.venue_id == venue_id,
                VendorEvent.vendor_event_id == vendor_event_id,
            )
        )
        vendor_event = result.scalar_one_or_none()

        if vendor_event is not None and vendor_event.canonical_event_id is not None:
            event = await self.get_by_id(vendor_event.canonical_event_id)
            if event is not None:
                # Only this venue's own repeated view of its own event — safe
                # to refresh from it. A cross-venue match (below) never
                # overwrites another venue's canonical fields.
                event.start_time = start_time
                event.home_participant = home_participant
                event.away_participant = away_participant
                return event

        matched_event, confidence = await self._match_against_existing(
            sport, competition, start_time, home_participant, away_participant
        )

        if matched_event is None:
            matched_event = Event(
                id=uuid.uuid4(),
                sport=sport,
                competition=competition,
                start_time=start_time,
                home_participant=home_participant,
                away_participant=away_participant,
                status=EventStatus.SCHEDULED.value,
                created_at=datetime.now(UTC),
            )
            self._session.add(matched_event)
            await self._session.flush()

        if vendor_event is None:
            vendor_event = VendorEvent(
                venue_id=venue_id,
                vendor_event_id=vendor_event_id,
                canonical_event_id=matched_event.id,
                raw_name=raw_name,
                start_time=start_time,
                match_confidence=confidence,
            )
            self._session.add(vendor_event)
        else:
            vendor_event.canonical_event_id = matched_event.id
            vendor_event.match_confidence = confidence

        return matched_event

    async def _match_against_existing(
        self,
        sport: str,
        competition: str,
        start_time: datetime,
        home_participant: str | None,
        away_participant: str | None,
    ) -> tuple[Event | None, Decimal | None]:
        candidates = await self._find_candidates(sport, start_time)
        if not candidates:
            return None, None

        new_candidate = MatchCandidate(
            sport=sport,
            competition=competition,
            start_time_utc=start_time,
            home_participant=home_participant,
            away_participant=away_participant,
        )
        existing_candidates = [
            MatchCandidate(
                sport=c.sport,
                competition=c.competition,
                start_time_utc=c.start_time,
                home_participant=c.home_participant,
                away_participant=c.away_participant,
            )
            for c in candidates
        ]
        result = find_best_match(new_candidate, existing_candidates)
        if result.decision == MatchDecision.NO_MATCH or result.matched_index is None:
            return None, None
        # Spec section 11.3: auto-match (>=0.98) and review (0.90-0.98) both
        # link the vendor event so data isn't duplicated; REVIEW is a signal
        # for the mapping-confidence UI to flag, not a reason to block.
        return candidates[result.matched_index], Decimal(str(round(result.score, 5)))
