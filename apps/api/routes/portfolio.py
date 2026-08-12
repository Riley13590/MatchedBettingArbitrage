"""Milestones 6-7 (ledger/CLV analytics) — not implemented yet."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
