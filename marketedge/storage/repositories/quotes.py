from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.storage.orm import Quote as QuoteRow


class QuoteRepository:
    """Append-only store for the `quotes` table (spec section 8.1 — "Prices
    are append-heavy"). Latest-price lookups for the API/dashboard go
    through Redis (marketedge.ingestion.quote_processor); this repository
    is the durable audit trail."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        venue_id: int,
        selection_id: uuid.UUID,
        side: str,
        price: Decimal,
        available_size: Decimal | None,
        source_timestamp: datetime | None,
        received_at: datetime,
        is_live: bool,
        raw_payload: dict[str, Any] | None,
    ) -> QuoteRow:
        row = QuoteRow(
            venue_id=venue_id,
            selection_id=selection_id,
            side=side,
            price=price,
            available_size=available_size,
            source_timestamp=source_timestamp,
            received_at=received_at,
            is_live=is_live,
            raw_payload=raw_payload,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def latest_for_selection(
        self, selection_id: uuid.UUID, limit: int = 20
    ) -> list[QuoteRow]:
        result = await self._session.execute(
            select(QuoteRow)
            .where(QuoteRow.selection_id == selection_id)
            .order_by(QuoteRow.received_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def latest_by_venue_and_side(
        self, selection_id: uuid.UUID, since: datetime
    ) -> list[QuoteRow]:
        """One row per (venue, side) for this selection — the most recent
        quote each venue has offered on each side, within `since`. This is
        what the arbitrage detector needs: the best currently-executable
        price per venue, not the full price history."""
        result = await self._session.execute(
            select(QuoteRow)
            .distinct(QuoteRow.venue_id, QuoteRow.side)
            .where(QuoteRow.selection_id == selection_id, QuoteRow.received_at >= since)
            .order_by(QuoteRow.venue_id, QuoteRow.side, QuoteRow.received_at.desc())
        )
        return list(result.scalars().all())
