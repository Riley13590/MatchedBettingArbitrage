"""Betfair connector package — public entry point is `BetfairConnector`,
which assembles `client.py` (REST), `stream.py` (Exchange Stream API) and
`mapper.py` (vendor -> canonical translation) behind the
`marketedge.connectors.base.MarketDataConnector` protocol. Nothing outside
this package should import `client`, `stream`, or `mapper` directly.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from marketedge.config.settings import Settings
from marketedge.connectors.base import TimeWindow
from marketedge.connectors.betfair.client import BetfairClient
from marketedge.connectors.betfair.mapper import (
    map_event,
    map_market,
    map_market_book,
    map_stream_change_message,
)
from marketedge.connectors.betfair.stream import BetfairStreamClient
from marketedge.connectors.drafts import EventDraft, MarketDraft, QuoteDraft
from marketedge.observability.logging import log_event

logger = logging.getLogger(__name__)


class BetfairConnector:
    venue = "betfair"

    def __init__(self, settings: Settings, client: BetfairClient | None = None) -> None:
        self._settings = settings
        self._client = client or BetfairClient(settings)
        self._stream: BetfairStreamClient | None = None

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    async def aclose(self) -> None:
        if self._stream is not None:
            await self._stream.aclose()
        await self._client.aclose()

    async def list_events(self, window: TimeWindow) -> list[EventDraft]:
        """Enumerates Betfair's own event-type catalogue at runtime and
        filters to the sports enabled in config, rather than hard-coding
        event-type IDs (Milestone 1 exit criteria)."""
        event_types = await self._client.list_event_types()
        wanted = {s.lower() for s in self._settings.sports_enabled}

        drafts: list[EventDraft] = []
        for entry in event_types:
            event_type = entry["eventType"]
            sport_name = str(event_type["name"])
            if sport_name.lower() not in wanted:
                continue
            raw_events = await self._client.list_events(
                {
                    "eventTypeIds": [event_type["id"]],
                    "marketStartTime": {
                        "from": window.start_utc.isoformat(),
                        "to": window.end_utc.isoformat(),
                    },
                }
            )
            drafts.extend(map_event(sport_name, item) for item in raw_events)
        return drafts

    async def list_markets(self, event: EventDraft) -> list[MarketDraft]:
        raw_markets = await self._client.list_market_catalogue(
            {"eventIds": [event.vendor_event_id]}
        )
        return [
            map_market(
                item,
                sport=event.sport,
                home_participant=event.home_participant,
                away_participant=event.away_participant,
            )
            for item in raw_markets
        ]

    async def get_quotes(self, vendor_market_ids: list[str]) -> list[QuoteDraft]:
        if not vendor_market_ids:
            return []
        raw_books = await self._client.list_market_book(vendor_market_ids)
        drafts: list[QuoteDraft] = []
        for book in raw_books:
            drafts.extend(map_market_book(book))
        return drafts

    async def stream_quotes(self, subscriptions: list[str]) -> AsyncIterator[QuoteDraft]:
        if not subscriptions:
            return
        self._stream = BetfairStreamClient(self._settings, self._client.get_session_token)
        log_event(logger, "betfair_stream_subscribe", market_count=len(subscriptions))
        async for message in self._stream.stream_market_changes(subscriptions):
            for draft in map_stream_change_message(message):
                yield draft

    async def healthcheck(self) -> bool:
        return await self._client.healthcheck()


__all__ = ["BetfairConnector"]
