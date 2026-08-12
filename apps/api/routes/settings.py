"""Kill switch / resume (Milestone 4, risk engine) — not implemented yet.

See docs/runbooks/kill-switch.md for the intended behaviour once the risk
engine exists.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1/system", tags=["system"])


@router.post("/kill-switch")
async def activate_kill_switch() -> None:
    raise HTTPException(status_code=501, detail="kill switch: implemented in Milestone 4")


@router.post("/resume")
async def resume() -> None:
    raise HTTPException(status_code=501, detail="kill switch: implemented in Milestone 4")
