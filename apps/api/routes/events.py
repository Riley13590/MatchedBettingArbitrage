from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.dependencies import DbSession
from marketedge.matching.event_matcher import AUTO_MATCH_THRESHOLD
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
    match_confidence: float | None
    needs_review: bool


@router.get("", response_model=list[EventOut])
async def list_events(session: DbSession, limit: int = 100) -> list[EventOut]:
    repo = EventRepository(session)
    events = await repo.list_upcoming(limit=limit)
    confidences = await repo.min_match_confidence_by_event([e.id for e in events])

    def _needs_review(confidence: float | None) -> bool:
        return confidence is not None and confidence < AUTO_MATCH_THRESHOLD

    return [
        EventOut(
            id=e.id,
            sport=e.sport,
            competition=e.competition,
            start_time=e.start_time,
            home_participant=e.home_participant,
            away_participant=e.away_participant,
            status=e.status,
            match_confidence=confidences.get(e.id),
            needs_review=_needs_review(confidences.get(e.id)),
        )
        for e in events
    ]
