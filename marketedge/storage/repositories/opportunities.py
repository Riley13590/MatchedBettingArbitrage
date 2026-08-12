from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.storage.orm import Opportunity


@dataclass(frozen=True)
class SegmentStat:
    """One row of the spec section 40.5 segment ranking: sport x market
    family, aggregated over the reporting window."""

    sport: str | None
    market_family: str | None
    sample_count: int
    median_net_roi: Decimal | None
    total_executable_edge_gbp: Decimal | None
    median_quote_age_ms: Decimal | None


class OpportunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        strategy: str,
        event_id: uuid.UUID,
        market_id: uuid.UUID,
        detected_at: datetime,
        expires_at: datetime | None,
        expected_profit: Decimal,
        expected_roi: Decimal,
        worst_case_profit: Decimal,
        confidence: Decimal,
        status: str,
        snapshot: dict[str, Any],
        sport: str,
        competition: str,
        market_family: str,
        venues: str,
        time_to_start_bucket: str,
        quote_age_ms_at_detection: Decimal,
        executable_stake_gbp: Decimal,
        executable_edge_gbp: Decimal,
    ) -> Opportunity:
        row = Opportunity(
            id=uuid.uuid4(),
            strategy=strategy,
            event_id=event_id,
            market_id=market_id,
            detected_at=detected_at,
            expires_at=expires_at,
            expected_profit=expected_profit,
            expected_roi=expected_roi,
            worst_case_profit=worst_case_profit,
            confidence=confidence,
            status=status,
            snapshot=snapshot,
            sport=sport,
            competition=competition,
            market_family=market_family,
            venues=venues,
            time_to_start_bucket=time_to_start_bucket,
            quote_age_ms_at_detection=quote_age_ms_at_detection,
            executable_stake_gbp=executable_stake_gbp,
            executable_edge_gbp=executable_edge_gbp,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, opportunity_id: uuid.UUID) -> Opportunity | None:
        return await self._session.get(Opportunity, opportunity_id)

    async def list_recent(self, strategy: str | None = None, limit: int = 100) -> list[Opportunity]:
        stmt = select(Opportunity).order_by(Opportunity.detected_at.desc()).limit(limit)
        if strategy is not None:
            stmt = stmt.where(Opportunity.strategy == strategy)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def close_expired(
        self, opportunity_id: uuid.UUID, expires_at: datetime, lifetime_ms: Decimal
    ) -> None:
        opportunity = await self.get_by_id(opportunity_id)
        if opportunity is None:
            return
        opportunity.status = "EXPIRED"
        opportunity.expires_at = expires_at
        opportunity.lifetime_ms = lifetime_ms

    async def record_verification(
        self,
        opportunity_id: uuid.UUID,
        outcome: str,
        verified_at: datetime,
        bookmaker_price: Decimal | None,
        exchange_price: Decimal | None,
    ) -> None:
        opportunity = await self.get_by_id(opportunity_id)
        if opportunity is None:
            return
        opportunity.verification_outcome = outcome
        opportunity.verified_at = verified_at
        opportunity.verified_bookmaker_price = bookmaker_price
        opportunity.verified_exchange_price = exchange_price

    async def segment_report(
        self, since: datetime, strategy: str | None = None
    ) -> list[SegmentStat]:
        """Spec section 40.5 — ranked by `total_executable_edge_gbp`, the
        primary commercial-usefulness metric (section 40.4), not raw count
        or raw ROI."""
        stmt = (
            select(
                Opportunity.sport,
                Opportunity.market_family,
                func.count().label("sample_count"),
                func.percentile_cont(0.5)
                .within_group(Opportunity.expected_roi)
                .label("median_net_roi"),
                func.coalesce(func.sum(Opportunity.executable_edge_gbp), 0).label(
                    "total_executable_edge_gbp"
                ),
                func.percentile_cont(0.5)
                .within_group(Opportunity.quote_age_ms_at_detection)
                .label("median_quote_age_ms"),
            )
            .where(Opportunity.detected_at >= since)
            .group_by(Opportunity.sport, Opportunity.market_family)
            .order_by(func.sum(Opportunity.executable_edge_gbp).desc())
        )
        if strategy is not None:
            stmt = stmt.where(Opportunity.strategy == strategy)

        result = await self._session.execute(stmt)
        return [
            SegmentStat(
                sport=row.sport,
                market_family=row.market_family,
                sample_count=row.sample_count,
                median_net_roi=row.median_net_roi,
                total_executable_edge_gbp=row.total_executable_edge_gbp,
                median_quote_age_ms=row.median_quote_age_ms,
            )
            for row in result.all()
        ]
