from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.storage.orm import ApiUsage


class ApiUsageRepository:
    """Spec section 41.2 — durable ledger of every metered provider
    request, so budget dashboards/forecasts never have to reconstruct
    usage from logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        provider: str,
        endpoint: str,
        requested_at: datetime,
        sport_key: str | None = None,
        market_keys: str | None = None,
        regions: str | None = None,
        credits_used: int | None = None,
        remaining_credits_reported: int | None = None,
        response_status: int | None = None,
        response_latency_ms: int | None = None,
    ) -> ApiUsage:
        row = ApiUsage(
            provider=provider,
            endpoint=endpoint,
            sport_key=sport_key,
            market_keys=market_keys,
            regions=regions,
            requested_at=requested_at,
            credits_used=credits_used,
            remaining_credits_reported=remaining_credits_reported,
            response_status=response_status,
            response_latency_ms=response_latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def credits_used_since(self, provider: str, since: datetime) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(ApiUsage.credits_used), 0)).where(
                ApiUsage.provider == provider, ApiUsage.requested_at >= since
            )
        )
        return int(result.scalar_one() or 0)

    async def credits_used_by_sport_since(self, provider: str, since: datetime) -> dict[str, int]:
        result = await self._session.execute(
            select(ApiUsage.sport_key, func.coalesce(func.sum(ApiUsage.credits_used), 0))
            .where(ApiUsage.provider == provider, ApiUsage.requested_at >= since)
            .group_by(ApiUsage.sport_key)
        )
        return {(sport or "unknown"): int(total) for sport, total in result.all()}

    async def latest_remaining_credits(self, provider: str) -> int | None:
        result = await self._session.execute(
            select(ApiUsage.remaining_credits_reported)
            .where(ApiUsage.provider == provider, ApiUsage.remaining_credits_reported.is_not(None))
            .order_by(ApiUsage.requested_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
