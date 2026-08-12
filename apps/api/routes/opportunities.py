"""Milestone 3: real GET routes for arbitrage opportunities detected in
paper mode. Confirm/execute-hedge stay stubs — those are Milestone 6
(manual bookmaker confirmation + automatic exchange hedge); nothing in
this build can act on an opportunity yet."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import DbSession
from marketedge.storage.orm import Opportunity
from marketedge.storage.repositories.opportunities import OpportunityRepository

router = APIRouter(prefix="/v1/opportunities", tags=["opportunities"])


class OpportunityOut(BaseModel):
    id: uuid.UUID
    strategy: str
    status: str
    event_id: uuid.UUID | None
    market_id: uuid.UUID | None
    detected_at: datetime
    expires_at: datetime | None
    sport: str | None
    competition: str | None
    market_family: str | None
    venues: str | None
    time_to_start_bucket: str | None
    expected_profit: Decimal | None
    expected_roi: Decimal | None
    worst_case_profit: Decimal | None
    quote_age_ms_at_detection: Decimal | None
    executable_stake_gbp: Decimal | None
    executable_edge_gbp: Decimal | None
    lifetime_ms: Decimal | None
    verification_outcome: str | None


class OpportunityDetailOut(OpportunityOut):
    snapshot: dict[str, Any]


def _to_out(row: Opportunity) -> OpportunityOut:
    return OpportunityOut(
        id=row.id,
        strategy=row.strategy,
        status=row.status,
        event_id=row.event_id,
        market_id=row.market_id,
        detected_at=row.detected_at,
        expires_at=row.expires_at,
        sport=row.sport,
        competition=row.competition,
        market_family=row.market_family,
        venues=row.venues,
        time_to_start_bucket=row.time_to_start_bucket,
        expected_profit=row.expected_profit,
        expected_roi=row.expected_roi,
        worst_case_profit=row.worst_case_profit,
        quote_age_ms_at_detection=row.quote_age_ms_at_detection,
        executable_stake_gbp=row.executable_stake_gbp,
        executable_edge_gbp=row.executable_edge_gbp,
        lifetime_ms=row.lifetime_ms,
        verification_outcome=row.verification_outcome,
    )


class SegmentOut(BaseModel):
    sport: str | None
    market_family: str | None
    sample_count: int
    median_net_roi: Decimal | None
    total_executable_edge_gbp: Decimal | None
    median_quote_age_ms: Decimal | None


@router.get("", response_model=list[OpportunityOut])
async def list_opportunities(
    session: DbSession, strategy: str | None = None, limit: int = 100
) -> list[OpportunityOut]:
    rows = await OpportunityRepository(session).list_recent(strategy=strategy, limit=limit)
    return [_to_out(row) for row in rows]


@router.get("/segments", response_model=list[SegmentOut])
async def segment_report(
    session: DbSession, strategy: str | None = None, hours: int = 24
) -> list[SegmentOut]:
    """Spec section 40.5 — ranks sport x market-family segments by total
    executable £ edge over the trailing window, not raw count/ROI."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    stats = await OpportunityRepository(session).segment_report(since, strategy=strategy)
    return [
        SegmentOut(
            sport=s.sport,
            market_family=s.market_family,
            sample_count=s.sample_count,
            median_net_roi=s.median_net_roi,
            total_executable_edge_gbp=s.total_executable_edge_gbp,
            median_quote_age_ms=s.median_quote_age_ms,
        )
        for s in stats
    ]


@router.get("/{opportunity_id}", response_model=OpportunityDetailOut)
async def get_opportunity(opportunity_id: uuid.UUID, session: DbSession) -> OpportunityDetailOut:
    row = await OpportunityRepository(session).get_by_id(opportunity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return OpportunityDetailOut(**_to_out(row).model_dump(), snapshot=row.snapshot)


@router.post("/{opportunity_id}/confirm-bookmaker-leg")
async def confirm_bookmaker_leg(opportunity_id: str) -> None:
    raise HTTPException(
        status_code=501, detail="manual bookmaker workflow: implemented in Milestone 6"
    )


@router.post("/{opportunity_id}/execute-hedge")
async def execute_hedge(opportunity_id: str) -> None:
    raise HTTPException(status_code=501, detail="hedge execution: implemented in Milestone 6")
