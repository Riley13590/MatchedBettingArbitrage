"""Betfair Exchange Stream API client.

Real implementation of Betfair's line-delimited JSON protocol over a TLS
socket (not a polling shim) — spec Milestone 1 explicitly asks for "Market
stream ingestion". Protocol summary (Betfair Exchange Stream API docs):

1. Open a TLS connection to `stream-api.betfair.com:443`.
2. Send an `authentication` operation with the app key + session token.
3. Send a `marketSubscription` operation with a market filter.
4. Read newline-delimited JSON `mcm` (market change message) frames until
   disconnected; reconnect with backoff on failure.

Falls back to nothing by itself — if streaming cannot be established, the
caller (ingestion orchestrator) is responsible for falling back to REST
polling via `client.list_market_book`. That fallback decision does not
belong in this module.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
from collections.abc import AsyncIterator
from typing import Any

import orjson

from marketedge.config.settings import Settings
from marketedge.domain.errors import ConnectorAuthError
from marketedge.observability.logging import log_event

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_SECONDS = 5.0
_MAX_BACKOFF_SECONDS = 30.0


class BetfairStreamClient:
    def __init__(self, settings: Settings, get_session_token: Any) -> None:
        """`get_session_token` is an async callable returning a valid
        Betfair session token — reused from `BetfairClient` so login logic
        lives in exactly one place."""
        self._settings = settings
        self.get_session_token = get_session_token
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._closed = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _connect(self) -> None:
        ssl_context = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            self._settings.betfair_stream_host,
            self._settings.betfair_stream_port,
            ssl=ssl_context,
        )
        self._reader, self._writer = reader, writer

        token = await self.get_session_token()
        await self._send(
            {
                "op": "authentication",
                "id": self._next_id(),
                "appKey": self._settings.betfair_app_key,
                "session": token,
            }
        )
        status = await self._read_message()
        if status is None or status.get("statusCode") != "SUCCESS":
            raise ConnectorAuthError(f"Betfair stream authentication failed: {status}")
        log_event(logger, "betfair_stream_authenticated", connection_id=status.get("connectionId"))

    async def _send(self, message: dict[str, Any]) -> None:
        if self._writer is None:
            raise RuntimeError("stream not connected")
        self._writer.write(orjson.dumps(message) + b"\r\n")
        await self._writer.drain()

    async def _read_message(self) -> dict[str, Any] | None:
        if self._reader is None:
            raise RuntimeError("stream not connected")
        line = await self._reader.readline()
        if not line:
            return None
        return orjson.loads(line)  # type: ignore[no-any-return]

    async def _subscribe(self, market_ids: list[str]) -> None:
        await self._send(
            {
                "op": "marketSubscription",
                "id": self._next_id(),
                "marketFilter": {"marketIds": market_ids},
                "marketDataFilter": {
                    "fields": ["EX_BEST_OFFERS", "EX_MARKET_DEF"],
                    "ladderLevels": 3,
                },
            }
        )

    async def _heartbeat_loop(self) -> None:
        while not self._closed:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
            with contextlib.suppress(Exception):
                await self._send({"op": "heartbeat", "id": self._next_id()})

    async def stream_market_changes(self, market_ids: list[str]) -> AsyncIterator[dict[str, Any]]:
        """Yields raw `mcm` message dicts, reconnecting with exponential
        backoff on any failure until `aclose()` is called. Callers pass
        each yielded message to `mapper.map_stream_change_message`."""
        backoff = 1.0
        while not self._closed:
            heartbeat_task: asyncio.Task[None] | None = None
            try:
                await self._connect()
                await self._subscribe(market_ids)
                backoff = 1.0
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                while not self._closed:
                    message = await self._read_message()
                    if message is None:
                        raise ConnectionError("Betfair stream closed the connection")
                    if message.get("op") == "mcm":
                        yield message
                    # "connection"/"status"/heartbeat-ack frames are ignored.
            except Exception as exc:  # noqa: BLE001 — reconnect on any failure
                log_event(
                    logger,
                    "betfair_stream_error",
                    level=logging.WARNING,
                    error=str(exc),
                    backoff_seconds=backoff,
                )
                if self._closed:
                    return
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                await self._disconnect()

    async def _disconnect(self) -> None:
        if self._writer is not None:
            with contextlib.suppress(Exception):
                self._writer.close()
                await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def aclose(self) -> None:
        self._closed = True
        await self._disconnect()
