from __future__ import annotations

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
