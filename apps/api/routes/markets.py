from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import DbSession
from marketedge.storage.repositories.markets import MarketRepository
from marketedge.storage.repositories.quotes import QuoteRepository

router = APIRouter(prefix="/v1/markets", tags=["markets"])


class SelectionQuoteOut(BaseModel):
    selection_id: uuid.UUID
    outcome_key: str
    display_name: str
    best_back: Decimal | None
    best_lay: Decimal | None


class MarketOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    market_type: str
    period: str
    line: Decimal | None
    settlement_scope: str
    selections: list[SelectionQuoteOut]


@router.get("/{market_id}", response_model=MarketOut)
async def get_market(market_id: uuid.UUID, session: DbSession) -> MarketOut:
    market_repo = MarketRepository(session)
    market = await market_repo.get_by_id(market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="market not found")

    quote_repo = QuoteRepository(session)
    selections_out: list[SelectionQuoteOut] = []
    for selection in market.selections:
        recent = await quote_repo.latest_for_selection(selection.id, limit=20)
        best_back = max((q.price for q in recent if q.side == "BACK"), default=None)
        best_lay = min((q.price for q in recent if q.side == "LAY"), default=None)
        selections_out.append(
            SelectionQuoteOut(
                selection_id=selection.id,
                outcome_key=selection.outcome_key,
                display_name=selection.display_name,
                best_back=best_back,
                best_lay=best_lay,
            )
        )

    return MarketOut(
        id=market.id,
        event_id=market.event_id,
        market_type=market.market_type,
        period=market.period,
        line=market.line,
        settlement_scope=market.settlement_scope,
        selections=selections_out,
    )
