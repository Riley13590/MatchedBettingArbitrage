"""Arbitrage opportunity domain objects (spec section 13.3).

Vendor-neutral — a `TradeLeg` references a venue *code* and a canonical
`selection_id`, never a vendor-specific market/runner ID (spec section 29
rule 8: strategy code never touches vendor types).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from marketedge.domain.enums import Side


@dataclass(frozen=True)
class TradeLeg:
    venue: str
    selection_id: uuid.UUID
    side: Side
    price: Decimal
    stake: Decimal
    available_size: Decimal
    quote_received_at: datetime
    quote_source_timestamp: datetime | None


@dataclass(frozen=True)
class ArbitrageOpportunity:
    opportunity_id: uuid.UUID
    event_id: uuid.UUID
    market_id: uuid.UUID
    legs: tuple[TradeLeg, ...]
    gross_roi: Decimal
    net_roi: Decimal
    worst_case_profit: Decimal
    capital_required: Decimal
    max_executable_size: Decimal
    detected_at: datetime
    expires_at: datetime
    data_age_ms: int

    @property
    def executable_edge_gbp(self) -> Decimal:
        """spec section 40.4: `net_worst_case_roi * maximum_executable_total_stake`
        — the primary ranking metric for commercial usefulness, distinct
        from the raw `worst_case_profit` (which is capped by whichever leg
        has the least liquidity, not by `capital_required`)."""
        return self.net_roi * self.max_executable_size
