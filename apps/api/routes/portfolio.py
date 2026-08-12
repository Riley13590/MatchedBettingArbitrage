"""Milestones 6-7 (ledger/CLV analytics) — mostly not implemented yet.
`/v1/analytics/api-usage` is a Milestone 2 deliverable (spec section 41.2
dashboard requirements) and is implemented for real."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import DbSession
from marketedge.config.settings import get_settings
from marketedge.ingestion.budget import current_month_start
from marketedge.storage.repositories.api_usage import ApiUsageRepository

router = APIRouter(prefix="/v1", tags=["portfolio"])


@router.get("/portfolio/exposure")
async def get_exposure() -> None:
    raise HTTPException(status_code=501, detail="portfolio: implemented in Milestone 6/7")


@router.get("/portfolio/pnl")
async def get_pnl() -> None:
    raise HTTPException(status_code=501, detail="portfolio: implemented in Milestone 6/7")


@router.get("/analytics/clv")
async def get_clv() -> None:
    raise HTTPException(status_code=501, detail="CLV analytics: implemented in Milestone 7")


@router.get("/analytics/strategy-performance")
async def get_strategy_performance() -> None:
    raise HTTPException(status_code=501, detail="strategy performance: implemented in Milestone 7")


class ApiUsageOut(BaseModel):
    provider: str
    credits_used_this_month: int
    credits_by_sport: dict[str, int]
    remaining_credits_reported: int | None
    soft_monthly_budget: int
    hard_monthly_budget: int
    over_soft_budget: bool
    over_hard_budget: bool


@router.get("/analytics/api-usage", response_model=ApiUsageOut)
async def get_api_usage(session: DbSession, provider: str = "the_odds_api") -> ApiUsageOut:
    settings = get_settings()
    repo = ApiUsageRepository(session)
    since = current_month_start(datetime.now(UTC))

    used = await repo.credits_used_since(provider, since)
    by_sport = await repo.credits_used_by_sport_since(provider, since)
    remaining = await repo.latest_remaining_credits(provider)

    return ApiUsageOut(
        provider=provider,
        credits_used_this_month=used,
        credits_by_sport=by_sport,
        remaining_credits_reported=remaining,
        soft_monthly_budget=settings.odds_provider_soft_monthly_budget,
        hard_monthly_budget=settings.odds_provider_hard_monthly_budget,
        over_soft_budget=used >= settings.odds_provider_soft_monthly_budget,
        over_hard_budget=used >= settings.odds_provider_hard_monthly_budget,
    )
