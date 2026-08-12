from decimal import Decimal

from marketedge.connectors.betfair.mapper import (
    map_event,
    map_market,
    map_market_book,
    map_stream_change_message,
)
from marketedge.domain.enums import Side


def test_map_event_splits_home_away() -> None:
    raw = {
        "event": {
            "id": "31234567",
            "name": "Arsenal v Chelsea",
            "openDate": "2026-08-15T14:00:00.000Z",
        }
    }
    draft = map_event("Soccer", raw)
    assert draft.vendor_event_id == "31234567"
    assert draft.home_participant == "Arsenal"
    assert draft.away_participant == "Chelsea"
    assert draft.sport == "Soccer"


def test_map_market_known_type() -> None:
    raw = {
        "marketId": "1.234567890",
        "marketName": "Match Odds",
        "runners": [
            {"selectionId": 111111, "runnerName": "Arsenal"},
            {"selectionId": 222222, "runnerName": "The Draw"},
            {"selectionId": 333333, "runnerName": "Chelsea"},
        ],
        "event": {"id": "31234567"},
        "description": {"marketType": "MATCH_ODDS"},
    }
    draft = map_market(raw)
    assert draft.market_type == "MATCH_ODDS"
    assert draft.period == "FULL_TIME"
    assert draft.settlement_scope == "REGULATION_ONLY"
    assert draft.line is None
    outcome_keys = {r.outcome_key for r in draft.runners}
    assert "DRAW" in outcome_keys


def test_map_market_unknown_type_never_collides_with_known() -> None:
    raw = {
        "marketId": "1.999",
        "marketName": "Some New Market",
        "runners": [{"selectionId": 1, "runnerName": "X"}],
        "event": {"id": "31234567"},
        "description": {"marketType": "SOME_NEW_MARKET_TYPE"},
    }
    draft = map_market(raw)
    assert draft.settlement_scope.startswith("UNVERIFIED:")
    assert draft.settlement_scope != "REGULATION_ONLY"


def test_map_market_extracts_total_line() -> None:
    raw = {
        "marketId": "1.234567891",
        "marketName": "Over/Under 2.5 Goals",
        "runners": [
            {"selectionId": 444444, "runnerName": "Over 2.5 Goals"},
            {"selectionId": 555555, "runnerName": "Under 2.5 Goals"},
        ],
        "event": {"id": "31234567"},
        "description": {"marketType": "OVER_UNDER_25"},
    }
    draft = map_market(raw)
    assert draft.market_type == "TOTAL"
    assert draft.line == Decimal("2.5")
    outcome_keys = {r.outcome_key for r in draft.runners}
    assert outcome_keys == {"OVER", "UNDER"}


def test_map_market_book_produces_back_and_lay_quotes() -> None:
    raw = {
        "marketId": "1.234567890",
        "inplay": False,
        "runners": [
            {
                "selectionId": 111111,
                "ex": {
                    "availableToBack": [{"price": 2.04, "size": 120.5}],
                    "availableToLay": [{"price": 2.06, "size": 88.2}],
                },
            }
        ],
    }
    drafts = map_market_book(raw)
    assert len(drafts) == 2
    back = next(d for d in drafts if d.side == Side.BACK)
    lay = next(d for d in drafts if d.side == Side.LAY)
    assert back.price == Decimal("2.04")
    assert lay.price == Decimal("2.06")
    assert back.is_live is False


def test_map_stream_change_message_uses_publish_time() -> None:
    message = {
        "op": "mcm",
        "pt": 1786000000000,
        "mc": [
            {
                "id": "1.234567890",
                "marketDefinition": {"inPlay": False},
                "rc": [{"id": 111111, "batb": [[0, 2.04, 120.5]], "batl": [[0, 2.06, 88.2]]}],
            }
        ],
    }
    drafts = map_stream_change_message(message)
    assert len(drafts) == 2
    assert all(d.source_timestamp_utc is not None for d in drafts)
    assert all(d.vendor_market_id == "1.234567890" for d in drafts)
