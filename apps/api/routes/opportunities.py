"""Milestone 3 (arbitrage engine) — not implemented yet.

Route shape reserved now per spec section 25 so the frontend/API contract
doesn't change when the arb detector lands.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1/opportunities", tags=["opportunities"])


@router.get("")
async def list_opportunities(strategy: str | None = None) -> None:
    raise HTTPException(status_code=501, detail="opportunities: implemented in Milestone 3")


@router.get("/{opportunity_id}")
async def get_opportunity(opportunity_id: str) -> None:
    raise HTTPException(status_code=501, detail="opportunities: implemented in Milestone 3")


@router.post("/{opportunity_id}/confirm-bookmaker-leg")
async def confirm_bookmaker_leg(opportunity_id: str) -> None:
    raise HTTPException(
        status_code=501, detail="manual bookmaker workflow: implemented in Milestone 6"
    )


@router.post("/{opportunity_id}/execute-hedge")
async def execute_hedge(opportunity_id: str) -> None:
    raise HTTPException(status_code=501, detail="hedge execution: implemented in Milestone 6")
