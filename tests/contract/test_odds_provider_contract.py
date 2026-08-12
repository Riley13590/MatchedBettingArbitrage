"""Contract tests: sanitised The Odds API payloads (tests/fixtures) parsed
through the real client + mapper code path, with only the HTTP transport
faked. No network access, no API key."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from marketedge.config.settings import Settings
from marketedge.connectors.odds_provider.client import OddsProviderClient
from marketedge.connectors.odds_provider.mapper import map_event_snapshot


def _settings() -> Settings:
    return Settings(ODDS_PROVIDER_API_KEY="test-key")


def _make_client(load_fixture: Any, fixture_by_path: dict[str, str]) -> OddsProviderClient:
    def handler(request: httpx.Request) -> httpx.Response:
        for path_suffix, fixture_name in fixture_by_path.items():
            if request.url.path.endswith(path_suffix):
                return httpx.Response(
                    200,
                    json=load_fixture(fixture_name),
                    headers={
                        "x-requests-remaining": "499",
                        "x-requests-used": "1",
                        "x-requests-last": "1",
                    },
                )
        raise AssertionError(f"unexpected request path {request.url.path}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return OddsProviderClient(_settings(), http_client=http_client)


@pytest.mark.asyncio
async def test_list_sports_contract(load_fixture: Any) -> None:
    client = _make_client(load_fixture, {"/sports": "oddsapi_sports.json"})
    sports, usage = await client.list_sports()
    assert {s["key"] for s in sports} == {
        "soccer_epl",
        "tennis_atp_wimbledon",
        "americanfootball_nfl",
    }
    assert usage.remaining_credits_reported == 499
    await client.aclose()


@pytest.mark.asyncio
async def test_get_odds_maps_to_bookmaker_batches(load_fixture: Any) -> None:
    client = _make_client(load_fixture, {"/odds": "oddsapi_odds_soccer_epl.json"})
    raw_events, usage = await client.get_odds("soccer_epl")
    assert len(raw_events) == 1
    event_draft, batches = map_event_snapshot("soccer_epl", "Soccer", "EPL", raw_events[0])
    assert event_draft.home_participant == "Arsenal"
    assert {b.bookmaker_key for b in batches} == {"williamhill", "bet365"}
    assert usage.credits_used == 1
    await client.aclose()
