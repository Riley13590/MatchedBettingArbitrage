from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.storage.orm import Venue


class VenueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> Venue | None:
        result = await self._session.execute(select(Venue).where(Venue.code == code))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Venue]:
        result = await self._session.execute(select(Venue).order_by(Venue.code))
        return list(result.scalars().all())

    async def is_execution_allowed(self, code: str) -> bool:
        venue = await self.get_by_code(code)
        return bool(venue and venue.execution_allowed)

    async def upsert_bookmaker(self, code: str, name: str, evidence_url: str | None) -> Venue:
        """Get-or-create a per-bookmaker venue row discovered dynamically
        from the odds provider's catalogue (spec section 40.1/43 — coverage
        is discovered at runtime, never hard-coded). Bookmaker prices are
        always data-only: `execution_allowed=False` and `geo_status`/
        `terms_status` start `UNVERIFIED` until someone positively confirms
        that specific bookmaker's GB licensing/terms — see
        docs/venue-matrix.md."""
        venue = await self.get_by_code(code)
        if venue is not None:
            return venue

        venue = Venue(
            code=code,
            name=name,
            data_allowed=True,
            execution_allowed=False,
            geo_status="UNVERIFIED",
            terms_status="UNVERIFIED",
            checked_at=datetime.now(UTC),
            evidence_url=evidence_url,
        )
        self._session.add(venue)
        await self._session.flush()
        return venue
