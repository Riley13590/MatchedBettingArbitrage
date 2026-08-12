"""Vendor-neutral enums shared across the domain model.

Spec section 7.1. Keep this list additive-only in practice: strategies and
storage persist these as text, so renaming a member is a migration, not a
refactor.
"""

from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    BACK = "BACK"
    LAY = "LAY"


class MarketType(str, Enum):
    MATCH_ODDS = "MATCH_ODDS"
    MONEYLINE = "MONEYLINE"
    TOTAL = "TOTAL"
    HANDICAP = "HANDICAP"
    BOTH_TEAMS_TO_SCORE = "BTTS"


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PLAY = "IN_PLAY"
    SUSPENDED = "SUSPENDED"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"


class OrderState(str, Enum):
    """Spec section 17.2 execution state machine. Not reachable in M1 —
    there is no caller of ExecutionConnector yet — but persisted here so
    the `orders` table and Milestone 5 code share one definition."""

    CREATED = "CREATED"
    PRETRADE_APPROVED = "PRETRADE_APPROVED"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN_REQUIRES_RECONCILIATION = "UNKNOWN_REQUIRES_RECONCILIATION"
