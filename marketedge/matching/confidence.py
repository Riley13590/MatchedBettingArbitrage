"""Event match confidence scoring (spec section 11.3, formula verbatim).

```text
score = 0.40 * participant_similarity(a, b)
      + 0.30 * start_time_similarity(a, b)
      + 0.20 * competition_similarity(a, b)
      + 0.10 * home_away_consistency(a, b)
```

All component functions return a value in [0, 1]. Pure and synchronous —
callers (`event_matcher.py`) supply already-fetched candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from marketedge.matching.aliases import normalize

# Beyond this, two events cannot plausibly be the same fixture regardless of
# how well everything else matches.
_MAX_START_TIME_DELTA_SECONDS = 6 * 3600


@dataclass(frozen=True)
class MatchCandidate:
    """The minimal shape `confidence.py`/`event_matcher.py` need from either
    a freshly-mapped vendor event or an existing canonical event row —
    decoupled from both `connectors.drafts.EventDraft` and
    `storage.orm.Event` so this module has no dependency on either."""

    sport: str
    competition: str
    start_time_utc: datetime
    home_participant: str | None
    away_participant: str | None


def participant_similarity(a: MatchCandidate, b: MatchCandidate) -> float:
    a_home = normalize(a.home_participant) if a.home_participant else ""
    a_away = normalize(a.away_participant) if a.away_participant else ""
    b_home = normalize(b.home_participant) if b.home_participant else ""
    b_away = normalize(b.away_participant) if b.away_participant else ""

    if not (a_home and a_away and b_home and b_away):
        return 0.0

    same_orientation = a_home == b_home and a_away == b_away
    swapped_orientation = a_home == b_away and a_away == b_home
    if same_orientation or swapped_orientation:
        return 1.0
    # Partial credit: exactly one side matches (e.g. a name-formatting
    # difference on the other side that normalize() didn't catch).
    one_side_matches = a_home in (b_home, b_away) or a_away in (b_home, b_away)
    return 0.5 if one_side_matches else 0.0


def start_time_similarity(a: MatchCandidate, b: MatchCandidate) -> float:
    delta_seconds = abs((a.start_time_utc - b.start_time_utc).total_seconds())
    if delta_seconds >= _MAX_START_TIME_DELTA_SECONDS:
        return 0.0
    return 1.0 - (delta_seconds / _MAX_START_TIME_DELTA_SECONDS)


def competition_similarity(a: MatchCandidate, b: MatchCandidate) -> float:
    a_norm, b_norm = normalize(a.competition), normalize(b.competition)
    if not a_norm or not b_norm:
        return 0.5  # unknown competition on one side — neither confirms nor denies
    if a_norm == b_norm:
        return 1.0
    a_tokens, b_tokens = set(a_norm.split("_")), set(b_norm.split("_"))
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
    return overlap


def home_away_consistency(a: MatchCandidate, b: MatchCandidate) -> float:
    a_home = normalize(a.home_participant) if a.home_participant else ""
    b_home = normalize(b.home_participant) if b.home_participant else ""
    if not a_home or not b_home:
        return 0.5
    return 1.0 if a_home == b_home else 0.0


def event_match_score(a: MatchCandidate, b: MatchCandidate) -> float:
    if a.sport.strip().lower() != b.sport.strip().lower():
        return 0.0
    return (
        0.40 * participant_similarity(a, b)
        + 0.30 * start_time_similarity(a, b)
        + 0.20 * competition_similarity(a, b)
        + 0.10 * home_away_consistency(a, b)
    )
