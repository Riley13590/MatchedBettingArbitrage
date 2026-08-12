"""Canonical domain model.

Spec section 7. These types are the contract every connector maps into and
every strategy/risk/pricing module consumes. See
docs/adr/001-canonical-market-model.md for the rationale. Nothing in this
module may import a vendor SDK or reference a vendor field name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from marketedge.domain.enums import Side


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    sport: str
    competition: str
    start_time_utc: datetime
    home_participant: str | None
    away_participant: str | None
    participants: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CanonicalMarket:
    market_id: str
    event_id: str
    market_type: str  # marketedge.domain.enums.MarketType value, or a
    # provider-specific extension not yet in the enum — kept as str so a
    # new market family from a provider's catalogue doesn't require a code
    # change to ingest (spec section 40.2: "obtain available sports from
    # each provider at runtime").
    period: str  # FULL_TIME, SET_1, etc.
    line: Decimal | None  # 2.5 goals, -1.5 games, etc.
    settlement_scope: str  # REGULATION_ONLY, INCL_OT, TO_QUALIFY, ...

    def is_settlement_compatible(self, other: CanonicalMarket) -> bool:
        """Spec section 11.4: never compare/hedge markets unless market
        type, period, line and settlement scope all match."""
        return (
            self.market_type == other.market_type
            and self.period == other.period
            and self.line == other.line
            and self.settlement_scope == other.settlement_scope
        )


@dataclass(frozen=True)
class CanonicalSelection:
    selection_id: str
    market_id: str
    outcome_key: str  # HOME, DRAW, AWAY, OVER, UNDER, PLAYER_ID, ...


@dataclass(frozen=True)
class Quote:
    venue: str
    vendor_event_id: str
    vendor_market_id: str
    vendor_selection_id: str
    canonical_selection_id: str
    side: Side
    price: Decimal
    available_size: Decimal | None
    currency: str
    received_at_utc: datetime
    source_timestamp_utc: datetime | None
    is_live: bool

    @property
    def age_ms(self) -> float | None:
        """Milliseconds between the venue's own timestamp and when we
        received it — used for latency measurement (spec section 10.2)."""
        if self.source_timestamp_utc is None:
            return None
        delta = self.received_at_utc - self.source_timestamp_utc
        return delta.total_seconds() * 1000


@dataclass(frozen=True)
class VenueCapability:
    venue: str
    data_allowed: bool
    execution_allowed: bool
    supports_streaming: bool
    supports_back: bool
    supports_lay: bool
    geo_status: str
    terms_status: str
    checked_at_utc: datetime
    evidence_url: str
