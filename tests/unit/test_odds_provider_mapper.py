from decimal import Decimal

from marketedge.connectors.odds_provider.mapper import map_event, map_event_snapshot
from marketedge.domain.enums import Side


def _raw_event() -> dict:
    return {
        "id": "e1b2c3d4",
        "sport_key": "soccer_epl",
        "commence_time": "2026-08-15T14:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "williamhill",
                "title": "William Hill",
                "last_update": "2026-08-12T00:05:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.05},
                            {"name": "Draw", "price": 3.6},
                            {"name": "Chelsea", "price": 3.9},
                        ],
                    }
                ],
            }
        ],
    }


def test_map_event_extracts_participants() -> None:
    draft = map_event("soccer_epl", "Soccer", "EPL", _raw_event())
    assert draft.vendor_event_id == "e1b2c3d4"
    assert draft.home_participant == "Arsenal"
    assert draft.away_participant == "Chelsea"


def test_map_event_snapshot_produces_one_batch_per_bookmaker_market() -> None:
    event_draft, batches = map_event_snapshot("soccer_epl", "Soccer", "EPL", _raw_event())
    assert len(batches) == 1
    batch = batches[0]
    assert batch.bookmaker_key == "williamhill"
    assert batch.market.market_type == "MATCH_ODDS"  # has a draw outcome
    assert batch.market.settlement_scope == "REGULATION_ONLY"

    outcome_keys = {r.outcome_key for r in batch.market.runners}
    assert outcome_keys == {"HOME", "AWAY", "DRAW"}

    assert all(q.side == Side.BACK for q in batch.quotes)
    assert all(q.available_size is None for q in batch.quotes)
    prices = {q.price for q in batch.quotes}
    assert Decimal("2.05") in prices


def test_map_event_snapshot_two_way_market_has_no_draw() -> None:
    raw = _raw_event()
    raw["bookmakers"][0]["markets"][0]["outcomes"] = [
        {"name": "Arsenal", "price": 1.8},
        {"name": "Chelsea", "price": 2.1},
    ]
    _, batches = map_event_snapshot("soccer_epl", "Soccer", "EPL", raw)
    assert batches[0].market.market_type == "MONEYLINE"


def test_map_event_snapshot_totals_extracts_line() -> None:
    raw = _raw_event()
    raw["bookmakers"][0]["markets"][0] = {
        "key": "totals",
        "outcomes": [
            {"name": "Over", "price": 1.9, "point": 2.5},
            {"name": "Under", "price": 1.9, "point": 2.5},
        ],
    }
    _, batches = map_event_snapshot("soccer_epl", "Soccer", "EPL", raw)
    market = batches[0].market
    assert market.market_type == "TOTAL"
    assert market.line == Decimal("2.5")
    assert {r.outcome_key for r in market.runners} == {"OVER", "UNDER"}
