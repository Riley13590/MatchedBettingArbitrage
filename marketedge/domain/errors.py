"""Domain-level exceptions. Vendor-neutral — connectors translate vendor
errors into these before they cross into `marketedge.domain`/`ingestion`."""

from __future__ import annotations


class MarketEdgeError(Exception):
    """Base class for all MarketEdge domain errors."""


class VenueCapabilityError(MarketEdgeError):
    """Raised when an operation is attempted against a venue that has not
    been granted the required capability (data or execution) at runtime."""


class ExecutionDisabledError(VenueCapabilityError):
    """Raised by an ExecutionConnector when execution_allowed is False.

    See docs/adr/003-execution-isolation.md — this is the enforcement point
    referenced there.
    """


class StaleQuoteError(MarketEdgeError):
    """Raised when a strategy attempts to act on a quote older than its
    configured freshness threshold (spec section 10.2)."""


class SettlementMismatchError(MarketEdgeError):
    """Raised when code attempts to compare or hedge two selections whose
    markets do not share an equivalent settlement scope (spec section 11.4)."""


class ConnectorAuthError(MarketEdgeError):
    """Raised when a connector fails to authenticate with a venue."""
