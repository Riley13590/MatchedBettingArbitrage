"""Milestone 5 (Betfair execution) — not implemented yet.

See docs/adr/003-execution-isolation.md: the API gateway will never call a
vendor execution API directly even once this lands.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1/orders", tags=["orders"])


@router.post("/{order_id}/cancel")
async def cancel_order(order_id: str) -> None:
    raise HTTPException(status_code=501, detail="order execution: implemented in Milestone 5")


@router.get("/open")
async def list_open_orders() -> None:
    raise HTTPException(status_code=501, detail="order execution: implemented in Milestone 5")
