"""API-credit budget accounting (spec section 41.2/41.6).

Wraps `ApiUsageRepository` with the monthly hard/soft cap policy: discovery
scans consult `status()` before every metered call and degrade gracefully
(fewer sports polled, slower buckets skipped) as the soft cap approaches,
stopping entirely at the hard cap — never a hard crash on budget exhaustion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.connectors.odds_provider.client import RequestUsage
from marketedge.storage.repositories.api_usage import ApiUsageRepository


@dataclass(frozen=True)
class BudgetStatus:
    used_this_month: int
    soft_budget: int
    hard_budget: int

    @property
    def over_soft(self) -> bool:
        return self.used_this_month >= self.soft_budget

    @property
    def over_hard(self) -> bool:
        return self.used_this_month >= self.hard_budget


def current_month_start(now: datetime | None = None) -> datetime:
    reference = now or datetime.now(UTC)
    return reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class ApiCreditLedger:
    def __init__(self, provider: str, soft_budget: int, hard_budget: int) -> None:
        self.provider = provider
        self.soft_budget = soft_budget
        self.hard_budget = hard_budget

    async def status(self, session: AsyncSession) -> BudgetStatus:
        used = await ApiUsageRepository(session).credits_used_since(
            self.provider, current_month_start()
        )
        return BudgetStatus(used, self.soft_budget, self.hard_budget)

    async def record(
        self,
        session: AsyncSession,
        usage: RequestUsage,
        sport_key: str | None = None,
        market_keys: str | None = None,
        regions: str | None = None,
    ) -> None:
        await ApiUsageRepository(session).record(
            provider=self.provider,
            endpoint=usage.endpoint,
            requested_at=datetime.now(UTC),
            sport_key=sport_key,
            market_keys=market_keys,
            regions=regions,
            credits_used=usage.credits_used,
            remaining_credits_reported=usage.remaining_credits_reported,
            response_status=usage.response_status,
            response_latency_ms=usage.response_latency_ms,
        )
