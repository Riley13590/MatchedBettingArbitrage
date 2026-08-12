"""Odds-provider connector package — public entry point is
`OddsProviderConnector`. Deliberately does **not** implement the generic
`marketedge.connectors.base.MarketDataConnector` protocol shaped around
Betfair's list_events/list_markets/get_quotes waterfall — see
`mapper.py`'s module docstring for why forcing this provider's bundled
per-sport response through that shape would multiply metered API costs.
Its own interface below is what `marketedge.ingestion.odds_provider_ingestion`
drives instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from marketedge.config.settings import Settings
from marketedge.connectors.drafts import EventDraft
from marketedge.connectors.odds_provider.client import OddsProviderClient, RequestUsage
from marketedge.connectors.odds_provider.mapper import BookmakerQuoteBatch, map_event_snapshot


@dataclass(frozen=True)
class SportRef:
    key: str  # provider sport key, e.g. "soccer_epl" — used in API calls
    group: str  # general sport, e.g. "Soccer" — matches Betfair's eventType.name
    title: str  # specific league/competition, e.g. "EPL"


class OddsProviderConnector:
    venue = "odds_provider"

    def __init__(self, settings: Settings, client: OddsProviderClient | None = None) -> None:
        self._settings = settings
        self._client = client or OddsProviderClient(settings)

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    @property
    def regions(self) -> str:
        return self._settings.odds_provider_regions

    @property
    def markets(self) -> str:
        return self._settings.odds_provider_markets

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_sports(self) -> tuple[list[SportRef], RequestUsage]:
        """Filtered to the sports enabled in config, discovered from the
        provider's own catalogue rather than a hard-coded list (spec
        section 40.1/43)."""
        raw_sports, usage = await self._client.list_sports()
        wanted = {s.lower() for s in self._settings.sports_enabled}
        sports = [
            SportRef(
                key=str(s["key"]), group=str(s.get("group", "")), title=str(s.get("title", ""))
            )
            for s in raw_sports
            if str(s.get("group", "")).lower() in wanted
            or str(s.get("title", "")).lower() in wanted
        ]
        return sports, usage

    async def get_sport_snapshot(
        self, sport: SportRef
    ) -> tuple[list[tuple[EventDraft, list[BookmakerQuoteBatch]]], RequestUsage]:
        raw_events, usage = await self._client.get_odds(sport.key)
        snapshots = [
            map_event_snapshot(sport.key, sport.group, sport.title, event) for event in raw_events
        ]
        return snapshots, usage

    async def healthcheck(self) -> bool:
        return await self._client.healthcheck()


__all__ = ["OddsProviderConnector", "SportRef"]
