"""The Odds API client (api.the-odds-api.com/v4) — spec section 41.1 names
this provider explicitly as the reference for the paid discovery
experiment; its free tier is enough to validate the pipeline (spec section
41.1 "development vs economic validation").

Every response's rate-limit headers (`x-requests-remaining`,
`x-requests-used`, `x-requests-last`) are surfaced as `RequestUsage` so the
caller can record them to the `api_usage` ledger (spec section 41.2) —
this client never persists anything itself, it only reports what a call
cost.

Sports are discovered from `/v4/sports`, never hard-coded (spec section
40.1/43): the connector must not assume a permanent sport list.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from marketedge.config.settings import Settings
from marketedge.domain.errors import ConnectorAuthError


@dataclass(frozen=True)
class RequestUsage:
    endpoint: str
    credits_used: int | None
    remaining_credits_reported: int | None
    response_status: int
    response_latency_ms: int


class OddsProviderClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http_client or httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def is_configured(self) -> bool:
        return self._settings.odds_provider_configured

    async def _get(self, path: str, params: dict[str, str]) -> tuple[Any, RequestUsage]:
        if not self.is_configured:
            raise ConnectorAuthError("Odds provider API key is not configured")

        url = f"{self._settings.odds_provider_base_url}{path}"
        started = time.monotonic()
        response = await self._http.get(
            url, params={**params, "apiKey": self._settings.odds_provider_api_key}
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        response.raise_for_status()

        usage = RequestUsage(
            endpoint=path,
            credits_used=_parse_int_header(response.headers.get("x-requests-last")),
            remaining_credits_reported=_parse_int_header(
                response.headers.get("x-requests-remaining")
            ),
            response_status=response.status_code,
            response_latency_ms=latency_ms,
        )
        return response.json(), usage

    async def list_sports(self) -> tuple[list[dict[str, Any]], RequestUsage]:
        data, usage = await self._get("/sports", {})
        sports: list[dict[str, Any]] = data
        return sports, usage

    async def get_odds(
        self, sport_key: str, regions: str | None = None, markets: str | None = None
    ) -> tuple[list[dict[str, Any]], RequestUsage]:
        data, usage = await self._get(
            f"/sports/{sport_key}/odds",
            {
                "regions": regions or self._settings.odds_provider_regions,
                "markets": markets or self._settings.odds_provider_markets,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        events: list[dict[str, Any]] = data
        return events, usage

    async def healthcheck(self) -> bool:
        if not self.is_configured:
            return False
        try:
            await self.list_sports()
            return True
        except Exception:  # noqa: BLE001 — health check must never raise
            return False


def _parse_int_header(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
