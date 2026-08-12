from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.storage.orm import ParticipantAlias


class ParticipantAliasRepository:
    """Spec section 11.2 — controlled overrides consulted before falling
    back to fuzzy normalisation (marketedge.matching.aliases.normalize)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lookup(self, sport: str, raw_name: str) -> str | None:
        result = await self._session.execute(
            select(ParticipantAlias.canonical_key).where(
                ParticipantAlias.sport == sport, ParticipantAlias.raw_name == raw_name
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, sport: str, raw_name: str, canonical_key: str) -> ParticipantAlias:
        result = await self._session.execute(
            select(ParticipantAlias).where(
                ParticipantAlias.sport == sport, ParticipantAlias.raw_name == raw_name
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.canonical_key = canonical_key
            return row
        row = ParticipantAlias(sport=sport, raw_name=raw_name, canonical_key=canonical_key)
        self._session.add(row)
        await self._session.flush()
        return row
