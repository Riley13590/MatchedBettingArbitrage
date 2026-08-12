"""Connector health heartbeat.

Periodically runs `connector.healthcheck()` and exports the result as the
`connector_up` gauge (spec section 23.2). Kept separate from the discovery/
ingestion loop so a slow or hanging discovery call doesn't also freeze the
health signal the API's `/v1/venues` and future alerting depend on.
"""

from __future__ import annotations

import asyncio
import logging

from marketedge.connectors.base import MarketDataConnector
from marketedge.observability.logging import log_event
from marketedge.observability.metrics import connector_up

logger = logging.getLogger(__name__)


async def heartbeat_loop(connector: MarketDataConnector, interval_seconds: float = 30.0) -> None:
    while True:
        try:
            healthy = await connector.healthcheck()
        except Exception:  # noqa: BLE001 — heartbeat must never crash the worker
            healthy = False
        connector_up.labels(venue=connector.venue).set(1 if healthy else 0)
        log_event(logger, "connector_heartbeat", venue=connector.venue, healthy=healthy)
        await asyncio.sleep(interval_seconds)
