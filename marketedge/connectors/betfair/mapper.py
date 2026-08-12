"""Vendor (Betfair) -> canonical mapping.

This is the *only* module allowed to know Betfair's field names
(`marketId`, `selectionId`, `ex.availableToBack`, ...). Everything it
produces is a plain, vendor-neutral draft the ingestion pipeline persists
via the storage repositories, which is where canonical UUIDs get assigned.

Settlement-scope/period inference is a deliberate bootstrap heuristic
(spec section 11.4 requires the *field* to always be populated; getting its
value verified precisely across every market type is Milestone 2 work,
done alongside cross-venue market matching). Nothing downstream may treat
two markets as settlement-compatible unless this field matches exactly, so
an overly coarse heuristic here fails safe (it just prevents a match) —
it can never manufacture a false equivalence between mislabeled markets;
different Betfair marketType codes always land on different
market_type/period/settlement_scope tuples.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from marketedge.connectors.drafts import EventDraft, MarketDraft, QuoteDraft, RunnerDraft
from marketedge.domain.enums import Side
from marketedge.matching.selection_matcher import assign_outcome_key

# Betfair `description.marketType` -> (our market_type, period, settlement_scope).
# Extend as new Betfair market types are ingested; never guess silently for
# an unmapped type (see `_market_type_tuple` fallback below).
_KNOWN_MARKET_TYPES: dict[str, tuple[str, str, str]] = {
    "MATCH_ODDS": ("MATCH_ODDS", "FULL_TIME", "REGULATION_ONLY"),
    "MONEYLINE": ("MONEYLINE", "FULL_MATCH", "FULL_MATCH"),
    "OVER_UNDER_25": ("TOTAL", "FULL_TIME", "REGULATION_ONLY"),
    "OVER_UNDER_15": ("TOTAL", "FULL_TIME", "REGULATION_ONLY"),
    "OVER_UNDER_35": ("TOTAL", "FULL_TIME", "REGULATION_ONLY"),
    "BOTH_TEAMS_TO_SCORE": ("BTTS", "FULL_TIME", "REGULATION_ONLY"),
    "ASIAN_HANDICAP": ("HANDICAP", "FULL_TIME", "REGULATION_ONLY"),
}


def _market_type_tuple(betfair_market_type: str) -> tuple[str, str, str]:
    if betfair_market_type in _KNOWN_MARKET_TYPES:
        return _KNOWN_MARKET_TYPES[betfair_market_type]
    # Unmapped market type: pass the vendor code through verbatim as both
    # market_type and settlement_scope so it can never collide with (and be
    # wrongly treated as equivalent to) a known, mapped market type.
    return (betfair_market_type, "UNKNOWN", f"UNVERIFIED:{betfair_market_type}")


def _parse_line(betfair_market_type: str, market_name: str) -> Decimal | None:
    """Betfair encodes handicap/total lines in the market type suffix or
    market name (e.g. OVER_UNDER_25 -> 2.5); best-effort extraction."""
    digits = "".join(ch for ch in betfair_market_type if ch.isdigit())
    if betfair_market_type.startswith(("OVER_UNDER_",)) and digits:
        # OVER_UNDER_25 -> 2.5
        return Decimal(digits[:-1] + "." + digits[-1])
    return None


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def map_event(sport: str, raw_event_item: dict[str, Any]) -> EventDraft:
    event = raw_event_item["event"]
    name = event.get("name", "")
    home, away = _split_participants(name)
    return EventDraft(
        vendor_event_id=str(event["id"]),
        sport=sport,
        competition=event.get("competition", {}).get("name", "")
        if isinstance(event.get("competition"), dict)
        else "",
        start_time_utc=_parse_iso(event.get("openDate")) or datetime.now(UTC),
        home_participant=home,
        away_participant=away,
        raw_name=name,
    )


def _split_participants(name: str) -> tuple[str | None, str | None]:
    for sep in (" v ", " vs "):
        if sep in name:
            home, _, away = name.partition(sep)
            return home.strip(), away.strip()
    return None, None


def map_market(
    raw_market_catalogue_item: dict[str, Any],
    sport: str = "",
    home_participant: str | None = None,
    away_participant: str | None = None,
) -> MarketDraft:
    """`sport`/`home_participant`/`away_participant` come from the
    already-matched canonical event and are used to assign HOME/AWAY
    outcome keys that are consistent across venues (spec section 11 —
    without this, two venues' selections for the same match-odds market can
    never join on `outcome_key`). Callers that don't yet have a matched
    event (e.g. isolated contract tests) may omit them; runners then fall
    back to a vendor-derived key that simply won't cross-venue-match, which
    is a safe (if less useful) default — see `selection_matcher.py`.
    """
    description = raw_market_catalogue_item.get("description", {})
    betfair_market_type = description.get(
        "marketType", raw_market_catalogue_item.get("marketName", "UNKNOWN")
    )
    market_type, period, settlement_scope = _market_type_tuple(betfair_market_type)
    line = _parse_line(betfair_market_type, raw_market_catalogue_item.get("marketName", ""))

    runners = tuple(
        RunnerDraft(
            vendor_selection_id=str(runner["selectionId"]),
            outcome_key=assign_outcome_key(
                raw_name=str(runner.get("runnerName", "")),
                market_type=market_type,
                sport=sport,
                home_participant=home_participant,
                away_participant=away_participant,
                fallback_key=f"RUNNER_{runner['selectionId']}",
            ),
            display_name=runner.get("runnerName", str(runner["selectionId"])),
        )
        for runner in raw_market_catalogue_item.get("runners", [])
    )

    return MarketDraft(
        vendor_market_id=str(raw_market_catalogue_item["marketId"]),
        vendor_event_id=str(raw_market_catalogue_item["event"]["id"]),
        market_type=market_type,
        period=period,
        line=line,
        settlement_scope=settlement_scope,
        runners=runners,
    )


def map_market_book(raw_market_book: dict[str, Any]) -> list[QuoteDraft]:
    market_id = str(raw_market_book["marketId"])
    is_live = bool(raw_market_book.get("inplay", False))
    drafts: list[QuoteDraft] = []
    for runner in raw_market_book.get("runners", []):
        selection_id = str(runner["selectionId"])
        ex = runner.get("ex", {})
        for level in ex.get("availableToBack", []):
            drafts.append(
                QuoteDraft(
                    vendor_market_id=market_id,
                    vendor_selection_id=selection_id,
                    side=Side.BACK,
                    price=Decimal(str(level["price"])),
                    available_size=Decimal(str(level["size"])),
                    is_live=is_live,
                    source_timestamp_utc=None,
                )
            )
        for level in ex.get("availableToLay", []):
            drafts.append(
                QuoteDraft(
                    vendor_market_id=market_id,
                    vendor_selection_id=selection_id,
                    side=Side.LAY,
                    price=Decimal(str(level["price"])),
                    available_size=Decimal(str(level["size"])),
                    is_live=is_live,
                    source_timestamp_utc=None,
                )
            )
    return drafts


def map_stream_change_message(message: dict[str, Any]) -> list[QuoteDraft]:
    """Maps a Betfair Stream API `mcm` (market change message) into quote
    drafts, using the message's own publish time (`pt`, epoch ms) as the
    source timestamp — unlike REST polling, the stream gives us a genuine
    upstream timestamp for latency measurement (spec section 10.2)."""
    publish_time_ms = message.get("pt")
    source_ts = (
        datetime.fromtimestamp(publish_time_ms / 1000, tz=UTC)
        if publish_time_ms is not None
        else None
    )

    drafts: list[QuoteDraft] = []
    for market_change in message.get("mc", []):
        market_id = str(market_change["id"])
        is_live = bool(market_change.get("marketDefinition", {}).get("inPlay", False))
        for runner in market_change.get("rc", []):
            selection_id = str(runner["id"])
            # batb/batl ladder entries are [level, price, size].
            for entry in runner.get("batb", []):
                _, price, size = entry
                drafts.append(
                    QuoteDraft(
                        vendor_market_id=market_id,
                        vendor_selection_id=selection_id,
                        side=Side.BACK,
                        price=Decimal(str(price)),
                        available_size=Decimal(str(size)),
                        is_live=is_live,
                        source_timestamp_utc=source_ts,
                    )
                )
            for entry in runner.get("batl", []):
                _, price, size = entry
                drafts.append(
                    QuoteDraft(
                        vendor_market_id=market_id,
                        vendor_selection_id=selection_id,
                        side=Side.LAY,
                        price=Decimal(str(price)),
                        available_size=Decimal(str(size)),
                        is_live=is_live,
                        source_timestamp_utc=source_ts,
                    )
                )
    return drafts
