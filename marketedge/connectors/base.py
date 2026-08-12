"""Connector protocols (spec section 9).

Every venue implements `MarketDataConnector`. Execution is a separate,
optional protocol (`ExecutionConnector`) — a venue can provide data without
providing execution, but never the reverse. Strategy code and the API
gateway must depend only on these protocols, never on a concrete connector
class (spec section 29 rule 8: "No strategy may call a venue API
directly.").
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from marketedge.domain.enums import Side

if TYPE_CHECKING:
    from marketedge.connectors.drafts import EventDraft, MarketDraft, QuoteDraft


@dataclass(frozen=True)
class TimeWindow:
    start_utc: datetime
    end_utc: datetime


class MarketDataConnector(Protocol):
    """Spec section 9. `list_markets` takes the already-mapped `EventDraft`
    (not just a vendor event ID) because assigning consistent HOME/AWAY/DRAW
    outcome keys — required for cross-venue selection matching, spec section
    11 — needs the event's participant names. Ingestion code depends only
    on this Protocol, never on a concrete connector class."""

    venue: str

    async def list_events(self, window: TimeWindow) -> list[EventDraft]: ...

    async def list_markets(self, event: EventDraft) -> list[MarketDraft]: ...

    async def get_quotes(self, vendor_market_ids: list[str]) -> list[QuoteDraft]: ...

    def stream_quotes(self, subscriptions: list[str]) -> AsyncIterator[QuoteDraft]: ...

    async def healthcheck(self) -> bool: ...


@dataclass(frozen=True)
class OrderCommand:
    client_order_id: str
    venue: str
    selection_id: str
    side: Side
    limit_price: Decimal
    size: Decimal
    time_in_force: str
    opportunity_id: str
    max_slippage_bps: int


@dataclass(frozen=True)
class ReplaceCommand:
    client_order_id: str
    vendor_order_id: str
    new_price: Decimal


@dataclass(frozen=True)
class OrderAck:
    client_order_id: str
    vendor_order_id: str | None
    accepted: bool
    reason: str | None


@dataclass(frozen=True)
class VendorOrder:
    vendor_order_id: str
    client_order_id: str
    state: str
    matched_size: Decimal
    average_matched_price: Decimal | None


@dataclass(frozen=True)
class VendorFill:
    vendor_fill_id: str
    vendor_order_id: str
    price: Decimal
    size: Decimal
    filled_at: datetime


class ExecutionConnector(Protocol):
    venue: str

    async def get_balance(self) -> Decimal: ...

    async def place_order(self, command: OrderCommand) -> OrderAck: ...

    async def cancel_order(self, vendor_order_id: str) -> None: ...

    async def replace_order(self, command: ReplaceCommand) -> OrderAck: ...

    async def get_open_orders(self) -> list[VendorOrder]: ...

    async def get_fills(self, since: datetime) -> list[VendorFill]: ...
