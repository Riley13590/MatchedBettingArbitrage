"""The Odds API -> canonical mapping.

Unlike Betfair's REST API, one `/v4/sports/{sport}/odds` call returns every
bookmaker's prices for every market on every event in that sport at once —
deliberately calling this out because it's why the odds-provider ingestion
loop (`marketedge.ingestion.odds_provider_ingestion`) does not follow the
same list_events -> list_markets -> get_quotes waterfall the
`MarketDataConnector` protocol describes: forcing one bundled response
through three separate calls per event would multiply metered API credit
usage for no benefit, undermining the budget goal this same milestone
introduces (spec section 41.2). `map_sport_snapshot` therefore returns
everything from a single response in one pass.

Each bookmaker becomes its own venue (see
`storage.repositories.venues.VenueRepository.upsert_bookmaker`), so prices
stay attributable to the specific book they came from (spec section 40.3's
discovery hierarchy includes BOOKMAKER as a required level).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from marketedge.connectors.drafts import EventDraft, MarketDraft, QuoteDraft, RunnerDraft
from marketedge.domain.enums import Side
from marketedge.matching.selection_matcher import assign_outcome_key

_DRAW_NAMES = {"DRAW", "TIE"}


def _period_and_scope(sport_key: str) -> tuple[str, str]:
    if sport_key.startswith("tennis_"):
        return "FULL_MATCH", "FULL_MATCH"
    return "FULL_TIME", "REGULATION_ONLY"


def _market_shape(
    odds_api_market_key: str, sport_key: str, has_draw_outcome: bool
) -> tuple[str, str, str]:
    period, base_scope = _period_and_scope(sport_key)
    if odds_api_market_key == "h2h":
        market_type = "MATCH_ODDS" if has_draw_outcome else "MONEYLINE"
        return market_type, period, base_scope
    if odds_api_market_key == "totals":
        return "TOTAL", period, base_scope
    if odds_api_market_key == "spreads":
        return "HANDICAP", period, base_scope
    # Unmapped market key: never silently claim equivalence with a known
    # type (mirrors marketedge.connectors.betfair.mapper's fallback rule).
    return odds_api_market_key.upper(), "UNKNOWN", f"UNVERIFIED:{odds_api_market_key}"


def _line_for_market(odds_api_market_key: str, outcomes: list[dict[str, Any]]) -> Decimal | None:
    if odds_api_market_key not in ("totals", "spreads"):
        return None
    for outcome in outcomes:
        point = outcome.get("point")
        if point is not None:
            return Decimal(str(abs(point)))
    return None


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def map_event(
    sport_key: str, sport_group: str, sport_title: str, raw_event: dict[str, Any]
) -> EventDraft:
    """`sport_group` is the general sport (The Odds API's `group`, e.g.
    "Soccer" — matches Betfair's `eventType.name`, which is what makes
    cross-venue event matching's sport-equality check line up at all).
    `sport_title` is the specific league (e.g. "EPL") and becomes
    `competition` — each Odds API "sport" is already one league, unlike
    Betfair where competition is a separate field on the event."""
    return EventDraft(
        vendor_event_id=str(raw_event["id"]),
        sport=sport_group,
        competition=sport_title,
        start_time_utc=_parse_iso(raw_event.get("commence_time")) or datetime.now(UTC),
        home_participant=raw_event.get("home_team"),
        away_participant=raw_event.get("away_team"),
        raw_name=f"{raw_event.get('home_team', '?')} v {raw_event.get('away_team', '?')}",
    )


@dataclass(frozen=True)
class BookmakerQuoteBatch:
    bookmaker_key: str
    bookmaker_title: str
    market: MarketDraft
    quotes: tuple[QuoteDraft, ...]


def map_event_snapshot(
    sport_key: str, sport_group: str, sport_title: str, raw_event: dict[str, Any]
) -> tuple[EventDraft, list[BookmakerQuoteBatch]]:
    """Maps one event's full bundled response (all bookmakers, all markets,
    all prices) in a single pass — see module docstring for why this isn't
    split into separate list_markets/get_quotes calls."""
    event_draft = map_event(sport_key, sport_group, sport_title, raw_event)
    vendor_event_id = event_draft.vendor_event_id

    batches: list[BookmakerQuoteBatch] = []
    for bookmaker in raw_event.get("bookmakers", []):
        bookmaker_key = str(bookmaker["key"])
        bookmaker_title = str(bookmaker.get("title", bookmaker_key))
        last_update = _parse_iso(bookmaker.get("last_update"))

        for market in bookmaker.get("markets", []):
            odds_api_market_key = str(market["key"])
            outcomes = market.get("outcomes", [])
            has_draw = any(str(o.get("name", "")).upper() in _DRAW_NAMES for o in outcomes)
            market_type, period, settlement_scope = _market_shape(
                odds_api_market_key, sport_key, has_draw
            )
            line = _line_for_market(odds_api_market_key, outcomes)
            vendor_market_id = f"{vendor_event_id}:{bookmaker_key}:{odds_api_market_key}"

            runners = []
            quotes = []
            for outcome in outcomes:
                name = str(outcome.get("name", ""))
                vendor_selection_id = f"{vendor_market_id}:{name}"
                outcome_key = assign_outcome_key(
                    raw_name=name,
                    market_type=market_type,
                    sport=sport_group,
                    home_participant=event_draft.home_participant,
                    away_participant=event_draft.away_participant,
                    fallback_key=f"OUTCOME_{name.upper()}",
                )
                runners.append(
                    RunnerDraft(
                        vendor_selection_id=vendor_selection_id,
                        outcome_key=outcome_key,
                        display_name=name,
                    )
                )
                price = outcome.get("price")
                if price is None:
                    continue
                # Bookmakers only ever offer a back-equivalent (fixed-odds)
                # price — there is no lay side (spec section 2: bookmaker
                # execution stays manual and one-sided).
                quotes.append(
                    QuoteDraft(
                        vendor_market_id=vendor_market_id,
                        vendor_selection_id=vendor_selection_id,
                        side=Side.BACK,
                        price=Decimal(str(price)),
                        available_size=None,
                        is_live=False,
                        source_timestamp_utc=last_update,
                    )
                )

            market_draft = MarketDraft(
                vendor_market_id=vendor_market_id,
                vendor_event_id=vendor_event_id,
                market_type=market_type,
                period=period,
                line=line,
                settlement_scope=settlement_scope,
                runners=tuple(runners),
            )
            batches.append(
                BookmakerQuoteBatch(
                    bookmaker_key=bookmaker_key,
                    bookmaker_title=bookmaker_title,
                    market=market_draft,
                    quotes=tuple(quotes),
                )
            )

    return event_draft, batches
