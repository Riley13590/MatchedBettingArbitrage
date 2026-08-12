from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from marketedge.storage.orm import Market, Selection


class MarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, market_id: uuid.UUID) -> Market | None:
        result = await self._session.execute(
            select(Market).where(Market.id == market_id).options(selectinload(Market.selections))
        )
        return result.scalar_one_or_none()

    async def list_for_event(self, event_id: uuid.UUID) -> list[Market]:
        result = await self._session.execute(select(Market).where(Market.event_id == event_id))
        return list(result.scalars().all())

    async def upsert(
        self,
        event_id: uuid.UUID,
        market_type: str,
        period: str,
        line: Decimal | None,
        settlement_scope: str,
    ) -> Market:
        result = await self._session.execute(
            select(Market).where(
                Market.event_id == event_id,
                Market.market_type == market_type,
                Market.period == period,
                Market.line == line,
                Market.settlement_scope == settlement_scope,
            )
        )
        market = result.scalar_one_or_none()
        if market is not None:
            return market

        market = Market(
            id=uuid.uuid4(),
            event_id=event_id,
            market_type=market_type,
            period=period,
            line=line,
            settlement_scope=settlement_scope,
        )
        self._session.add(market)
        await self._session.flush()
        return market

    async def upsert_selection(
        self, market_id: uuid.UUID, outcome_key: str, display_name: str
    ) -> Selection:
        result = await self._session.execute(
            select(Selection).where(
                Selection.market_id == market_id,
                Selection.outcome_key == outcome_key,
            )
        )
        selection = result.scalar_one_or_none()
        if selection is not None:
            return selection

        selection = Selection(
            id=uuid.uuid4(),
            market_id=market_id,
            outcome_key=outcome_key,
            display_name=display_name,
        )
        self._session.add(selection)
        await self._session.flush()
        return selection
