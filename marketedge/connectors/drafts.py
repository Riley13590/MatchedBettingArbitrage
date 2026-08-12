"""Vendor-adapter draft DTOs shared by every connector's mapper.

Every connector's `mapper.py` translates its vendor payloads into these
same shapes (spec section 9's "Vendor adapters are responsible for
converting raw payloads to canonical DTOs"). Sharing one definition means
the ingestion/matching layer only ever has to know one draft shape,
regardless of how many venues exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from marketedge.domain.enums import Side


@dataclass(frozen=True)
class EventDraft:
    vendor_event_id: str
    sport: str
    competition: str
    start_time_utc: datetime
    home_participant: str | None
    away_participant: str | None
    raw_name: str


@dataclass(frozen=True)
class RunnerDraft:
    vendor_selection_id: str
    outcome_key: str
    display_name: str


@dataclass(frozen=True)
class MarketDraft:
    vendor_market_id: str
    vendor_event_id: str
    market_type: str
    period: str
    line: Decimal | None
    settlement_scope: str
    runners: tuple[RunnerDraft, ...]


@dataclass(frozen=True)
class QuoteDraft:
    vendor_market_id: str
    vendor_selection_id: str
    side: Side
    price: Decimal
    available_size: Decimal | None
    is_live: bool
    source_timestamp_utc: datetime | None
