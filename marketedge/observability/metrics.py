"""Prometheus metrics (spec section 23.2).

M1 exposes the ingestion-relevant subset only; execution/risk metrics are
added when those subsystems exist (Milestones 4-5).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

connector_up = Gauge("connector_up", "1 if the venue connector is healthy", ["venue"])

quote_age_ms = Histogram(
    "quote_age_ms",
    "Age of a quote (source_timestamp -> received_at) in milliseconds",
    ["venue", "sport"],
)

quotes_received_total = Counter("quotes_received_total", "Quotes received", ["venue"])

market_matches_total = Counter("market_matches_total", "Market matching attempts", ["status"])
