from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.dependencies import DbSession
from marketedge.storage.repositories.venues import VenueRepository

router = APIRouter(prefix="/v1/venues", tags=["venues"])


class VenueOut(BaseModel):
    code: str
    name: str
    data_allowed: bool
    execution_allowed: bool
    geo_status: str
    terms_status: str
    checked_at: datetime
    evidence_url: str | None


@router.get("", response_model=list[VenueOut])
async def list_venues(session: DbSession) -> list[VenueOut]:
    venues = await VenueRepository(session).list_all()
    return [
        VenueOut(
            code=v.code,
            name=v.name,
            data_allowed=v.data_allowed,
            execution_allowed=v.execution_allowed,
            geo_status=v.geo_status,
            terms_status=v.terms_status,
            checked_at=v.checked_at,
            evidence_url=v.evidence_url,
        )
        for v in venues
    ]
