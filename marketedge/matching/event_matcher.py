"""Cross-venue event matching decision (spec section 11.3 gates):

```text
>= 0.98    auto-match
0.90-0.98 manual review / alias queue
< 0.90     do not match
```

Pure and synchronous — takes already-fetched candidates so it has no
database dependency of its own; `EventRepository` (which does have
repository access) is the caller.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from marketedge.matching.confidence import MatchCandidate, event_match_score

AUTO_MATCH_THRESHOLD = 0.98
REVIEW_THRESHOLD = 0.90


class MatchDecision(str, Enum):
    AUTO_MATCH = "AUTO_MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"


@dataclass(frozen=True)
class MatchResult:
    decision: MatchDecision
    score: float
    matched_index: int | None


def find_best_match(new: MatchCandidate, candidates: Sequence[MatchCandidate]) -> MatchResult:
    if not candidates:
        return MatchResult(MatchDecision.NO_MATCH, 0.0, None)

    scores = [event_match_score(new, candidate) for candidate in candidates]
    best_index = max(range(len(scores)), key=lambda i: scores[i])
    best_score = scores[best_index]

    if best_score >= AUTO_MATCH_THRESHOLD:
        return MatchResult(MatchDecision.AUTO_MATCH, best_score, best_index)
    if best_score >= REVIEW_THRESHOLD:
        return MatchResult(MatchDecision.REVIEW, best_score, best_index)
    return MatchResult(MatchDecision.NO_MATCH, best_score, None)
