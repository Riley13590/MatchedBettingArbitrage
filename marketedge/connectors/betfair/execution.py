"""Betfair execution connector — disabled by default.

Implements the `ExecutionConnector` protocol shape so it type-checks and so
Milestone 5 can fill in real order placement without changing the
interface, but every method refuses to run unless *both* gates are green:

1. The live `venues` row for `betfair` has `execution_allowed = true`.
2. `BETFAIR_EXECUTION_ALLOWED=true` in this process's environment.

Neither is true by default, and nothing in this repository can flip either
at runtime — see docs/adr/003-execution-isolation.md. There is no caller of
this class anywhere in M0/M1.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from marketedge.config.settings import Settings
from marketedge.connectors.base import (
    OrderAck,
    OrderCommand,
    ReplaceCommand,
    VendorFill,
    VendorOrder,
)
from marketedge.domain.errors import ExecutionDisabledError


class BetfairExecutionConnector:
    venue = "betfair"

    def __init__(self, settings: Settings, venue_execution_allowed: bool) -> None:
        self._settings = settings
        self._venue_execution_allowed = venue_execution_allowed

    def _check_enabled(self) -> None:
        if not (self._venue_execution_allowed and self._settings.betfair_execution_allowed):
            raise ExecutionDisabledError(
                "Betfair execution is disabled: requires venues.execution_allowed=true "
                "AND BETFAIR_EXECUTION_ALLOWED=true (see docs/adr/003-execution-isolation.md)"
            )

    async def get_balance(self) -> Decimal:
        self._check_enabled()
        raise NotImplementedError("Betfair execution is implemented in Milestone 5")

    async def place_order(self, command: OrderCommand) -> OrderAck:
        self._check_enabled()
        raise NotImplementedError("Betfair execution is implemented in Milestone 5")

    async def cancel_order(self, vendor_order_id: str) -> None:
        self._check_enabled()
        raise NotImplementedError("Betfair execution is implemented in Milestone 5")

    async def replace_order(self, command: ReplaceCommand) -> OrderAck:
        self._check_enabled()
        raise NotImplementedError("Betfair execution is implemented in Milestone 5")

    async def get_open_orders(self) -> list[VendorOrder]:
        self._check_enabled()
        raise NotImplementedError("Betfair execution is implemented in Milestone 5")

    async def get_fills(self, since: datetime) -> list[VendorFill]:
        self._check_enabled()
        raise NotImplementedError("Betfair execution is implemented in Milestone 5")
