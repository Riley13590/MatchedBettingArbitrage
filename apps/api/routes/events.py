from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.dependencies import DbSession
from marketedge.storage.repositories.events import EventRepository

router = APIRouter(prefix="/v1/events", tags=["events"])


class EventOut(BaseModel):
    id: uuid.UUID
    sport: str
    competition: str
    start_time: datetime
    home_participant: str | None
    away_participant: str | None
    status: str


@router.get("", response_model=list[EventOut])
async def list_events(session: DbSession, limit: int = 100) -> list[EventOut]:
    events = await EventRepository(session).list_upcoming(limit=limit)
    return [
        EventOut(
            id=e.id,
            sport=e.sport,
            competition=e.competition,
            start_time=e.start_time,
            home_participant=e.home_participant,
            away_participant=e.away_participant,
            status=e.status,
        )
        for e in events
    ]
