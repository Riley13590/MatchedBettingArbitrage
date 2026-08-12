"""Contract tests: sanitised, recorded Betfair payloads (tests/fixtures)
parsed through the real client + mapper code path, with only the HTTP
transport faked (spec section 27.2). No network access, no credentials.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from marketedge.config.settings import Settings
from marketedge.connectors.betfair.client import BetfairClient
from marketedge.connectors.betfair.mapper import map_event, map_market, map_market_book


def _settings() -> Settings:
    return Settings(
        BETFAIR_APP_KEY="test-app-key",
        BETFAIR_USERNAME="test-user",
        BETFAIR_PASSWORD="test-pass",
        BETFAIR_CERT_PATH="/tmp/does-not-need-to-exist.crt",
        BETFAIR_KEY_PATH="/tmp/does-not-need-to-exist.key",
    )


def _make_client(load_fixture: Any, rpc_fixture_by_method: dict[str, str]) -> BetfairClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/certlogin"):
            return httpx.Response(
                200, json={"sessionToken": "fake-session", "loginStatus": "SUCCESS"}
            )

        body = json.loads(request.content)
        method = body["method"].rsplit("/", 1)[-1]
        fixture_name = rpc_fixture_by_method[method]
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "result": load_fixture(fixture_name)}
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return BetfairClient(_settings(), http_client=http_client)


@pytest.mark.asyncio
async def test_list_event_types_contract(load_fixture: Any) -> None:
    client = _make_client(load_fixture, {"listEventTypes": "betfair_list_event_types.json"})
    result = await client.list_event_types()
    assert {e["eventType"]["name"] for e in result} == {"Soccer", "Tennis", "Cricket"}
    await client.aclose()


@pytest.mark.asyncio
async def test_list_events_maps_to_canonical_draft(load_fixture: Any) -> None:
    client = _make_client(load_fixture, {"listEvents": "betfair_list_events.json"})
    raw_events = await client.list_events({"eventTypeIds": ["1"]})
    drafts = [map_event("Soccer", item) for item in raw_events]
    assert len(drafts) == 1
    assert drafts[0].home_participant == "Arsenal"
    assert drafts[0].away_participant == "Chelsea"
    await client.aclose()


@pytest.mark.asyncio
async def test_list_market_catalogue_maps_settlement_fields(load_fixture: Any) -> None:
    client = _make_client(
        load_fixture, {"listMarketCatalogue": "betfair_list_market_catalogue.json"}
    )
    raw_markets = await client.list_market_catalogue({"eventIds": ["31234567"]})
    drafts = [map_market(item) for item in raw_markets]
    assert len(drafts) == 2
    match_odds = next(d for d in drafts if d.market_type == "MATCH_ODDS")
    totals = next(d for d in drafts if d.market_type == "TOTAL")
    assert match_odds.settlement_scope == "REGULATION_ONLY"
    assert totals.line == pytest.approx(2.5)
    await client.aclose()


@pytest.mark.asyncio
async def test_list_market_book_maps_to_quote_drafts(load_fixture: Any) -> None:
    client = _make_client(load_fixture, {"listMarketBook": "betfair_list_market_book.json"})
    raw_books = await client.list_market_book(["1.234567890"])
    drafts = [d for book in raw_books for d in map_market_book(book)]
    # 3 runners, 2 price levels for runner 1 (back+lay) + 1 level each for the other two
    assert len(drafts) == (2 + 2) + 2 + 2
    await client.aclose()
