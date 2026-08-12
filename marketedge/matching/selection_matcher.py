"""Assigns a canonical `outcome_key` to a vendor runner/outcome.

Pure and synchronous — called from inside connector mappers while they
build a `MarketDraft`, so it cannot make a database round trip (that would
mean every mapper doing async I/O mid-mapping, breaking the "mapper is a
pure translation" shape connectors are built around). It only needs to
compare a runner's name against *that same vendor's own* event participant
names — e.g. Betfair's own "Arsenal" runner against Betfair's own "Arsenal"
event participant — so the fast fuzzy `normalize()` fallback is sufficient
here; it does not need the DB-backed alias table cross-venue matching uses
(see `event_matcher.py`, which does have repository access).

Getting HOME/AWAY/DRAW/OVER/UNDER consistent *within* one vendor's own
naming is what lets two different vendors' selections for the same
canonical market converge on the same `outcome_key` and therefore the same
`selections` row (spec section 11 — without this every vendor's runners
would carry vendor-specific numeric fallback keys that could never join).
"""

from __future__ import annotations

from marketedge.matching.aliases import normalize

_DRAW_MARKERS = ("DRAW", "TIE", "THE_DRAW")
_OVER_MARKERS = ("OVER",)
_UNDER_MARKERS = ("UNDER",)
_YES_MARKERS = ("YES", "BTTS YES")
_NO_MARKERS = ("NO", "BTTS NO")

_TWO_OR_THREE_WAY_TYPES = {"MATCH_ODDS", "MONEYLINE"}


def assign_outcome_key(
    raw_name: str,
    market_type: str,
    sport: str,
    home_participant: str | None,
    away_participant: str | None,
    fallback_key: str,
) -> str:
    normalized_name = normalize(raw_name)

    if market_type in _TWO_OR_THREE_WAY_TYPES:
        if normalized_name in _DRAW_MARKERS:
            return "DRAW"
        if home_participant is not None and normalized_name == normalize(home_participant):
            return "HOME"
        if away_participant is not None and normalized_name == normalize(away_participant):
            return "AWAY"
        return fallback_key

    if market_type == "TOTAL":
        if any(normalized_name.startswith(marker) for marker in _OVER_MARKERS):
            return "OVER"
        if any(normalized_name.startswith(marker) for marker in _UNDER_MARKERS):
            return "UNDER"
        return fallback_key

    if market_type == "BTTS":
        if normalized_name in _YES_MARKERS:
            return "YES"
        if normalized_name in _NO_MARKERS:
            return "NO"
        return fallback_key

    return fallback_key
