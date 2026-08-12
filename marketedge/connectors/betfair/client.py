"""Betfair Exchange API client.

Certificate (non-interactive) login plus the Sports AP JSON-RPC betting
endpoints needed for market data (spec section 9): listEventTypes,
listCompetitions, listEvents, listMarketCatalogue, listMarketBook.

Deliberately does *not* hard-code a fixed set of sports/event-type IDs —
`list_events` enumerates Betfair's own event-type catalogue at runtime and
filters by the configured `sports_enabled` names (spec section 40.1 /
Milestone 1 exit criteria: "must enumerate available sports/market types
rather than hard-code football/tennis as product boundaries").

No vendor SDK types leak out of this module — all public methods return
plain dicts (raw Betfair payloads) or raise `marketedge.domain.errors`
exceptions; `mapper.py` is the only place that reads Betfair's field names.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from marketedge.config.settings import Settings
from marketedge.domain.errors import ConnectorAuthError
from marketedge.observability.logging import log_event

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 3.5 * 60 * 60  # Betfair sessions are valid ~4-24h; refresh conservatively.


class BetfairClient:
    """Read-only market-data client. See `execution.py` for the (disabled by
    default) order-placement surface."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        # The client certificate is a Client-level (not per-request) httpx
        # option, so it must be set at construction time. Tests inject their
        # own `http_client` (a MockTransport with no real cert) and skip this.
        cert = (
            (settings.betfair_cert_path, settings.betfair_key_path)
            if settings.betfair_cert_path and settings.betfair_key_path
            else None
        )
        self._http = http_client or httpx.AsyncClient(timeout=10.0, cert=cert)
        self._session_token: str | None = None
        self._session_obtained_at: float = 0.0

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def is_configured(self) -> bool:
        return self._settings.betfair_credentials_configured

    async def _login(self) -> str:
        """Certificate login (non-interactive). Requires a client cert
        registered with the Betfair account out-of-band — see
        `.env.example` / docs/architecture.md assumption 3."""
        if not self.is_configured:
            raise ConnectorAuthError("Betfair credentials are not configured")

        response = await self._http.post(
            self._settings.betfair_identity_url,
            data={
                "username": self._settings.betfair_username,
                "password": self._settings.betfair_password,
            },
            headers={
                "X-Application": self._settings.betfair_app_key,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("loginStatus") != "SUCCESS":
            raise ConnectorAuthError(f"Betfair certlogin failed: {payload.get('loginStatus')}")

        log_event(logger, "betfair_login_success")
        token = str(payload["sessionToken"])
        self._session_token = token
        self._session_obtained_at = time.monotonic()
        return token

    async def get_session_token(self) -> str:
        if self._session_token is None or (
            time.monotonic() - self._session_obtained_at > _SESSION_TTL_SECONDS
        ):
            return await self._login()
        return self._session_token

    async def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        token = await self.get_session_token()
        response = await self._http.post(
            self._settings.betfair_api_url,
            json={
                "jsonrpc": "2.0",
                "method": f"SportsAPING/v1.0/{method}",
                "params": params,
                "id": 1,
            },
            headers={
                "X-Application": self._settings.betfair_app_key,
                "X-Authentication": token,
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise ConnectorAuthError(f"Betfair RPC error calling {method}: {body['error']}")
        return body["result"]

    async def list_event_types(self, filter_: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Enumerates Betfair's sport catalogue at runtime. Never hard-code
        event-type IDs elsewhere in the codebase."""
        result: list[dict[str, Any]] = await self._rpc("listEventTypes", {"filter": filter_ or {}})
        return result

    async def list_competitions(self, filter_: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._rpc("listCompetitions", {"filter": filter_})
        return result

    async def list_events(self, filter_: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._rpc("listEvents", {"filter": filter_})
        return result

    async def list_market_catalogue(
        self,
        filter_: dict[str, Any],
        market_projection: list[str] | None = None,
        max_results: int = 200,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._rpc(
            "listMarketCatalogue",
            {
                "filter": filter_,
                "marketProjection": market_projection
                or [
                    "EVENT",
                    "MARKET_START_TIME",
                    "RUNNER_DESCRIPTION",
                    "COMPETITION",
                    "MARKET_DESCRIPTION",
                ],
                "maxResults": max_results,
            },
        )
        return result

    async def list_market_book(
        self,
        market_ids: list[str],
        price_projection: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._rpc(
            "listMarketBook",
            {
                "marketIds": market_ids,
                "priceProjection": price_projection
                or {"priceData": ["EX_BEST_OFFERS"], "virtualise": True},
            },
        )
        return result

    async def healthcheck(self) -> bool:
        if not self.is_configured:
            return False
        try:
            await self.get_session_token()
            return True
        except Exception:  # noqa: BLE001 — health check must never raise
            log_event(logger, "betfair_healthcheck_failed", level=logging.WARNING)
            return False
