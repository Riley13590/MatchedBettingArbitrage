from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.domain.enums import EventStatus
from marketedge.storage.orm import Event, VendorEvent


class EventRepository:
    """Persists canonical events and the vendor-event mapping that produced
    them. Milestone 1 has exactly one vendor (Betfair), so every vendor
    event is matched 1:1 to a new or existing canonical event by vendor ID
    — cross-venue alias matching (spec section 11) starts in Milestone 2.
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
                event.start_time = start_time
                event.home_participant = home_participant
                event.away_participant = away_participant
                return event

        event = Event(
            id=uuid.uuid4(),
            sport=sport,
            competition=competition,
            start_time=start_time,
            home_participant=home_participant,
            away_participant=away_participant,
            status=EventStatus.SCHEDULED.value,
            created_at=datetime.now(UTC),
        )
        self._session.add(event)
        await self._session.flush()

        if vendor_event is None:
            vendor_event = VendorEvent(
                venue_id=venue_id,
                vendor_event_id=vendor_event_id,
                canonical_event_id=event.id,
                raw_name=raw_name,
                start_time=start_time,
                match_confidence=None,
            )
            self._session.add(vendor_event)
        else:
            vendor_event.canonical_event_id = event.id

        return event
