"""Adaptive per-sport discovery polling (spec section 41.3).

```text
>24h to start       30-60 min
6-24h                10-20 min
1-6h                  3-5 min
<1h                   1-2 min
```

The Odds API returns every event for a sport in one call, so cadence is
naturally per-sport here rather than per-market (see
`connectors.odds_provider.mapper` module docstring) — a documented,
deliberate adaptation of the spec's abstract per-sport/per-market policy to
how this concrete provider's API is shaped, not a simplification of the
policy's intent (every market for a sport is refreshed together anyway).
These interval defaults are configuration (spec: "These are configuration
defaults, not universal constants"), read from `Settings`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from marketedge.config.settings import Settings


@dataclass(frozen=True)
class PollingBucket:
    label: str
    max_time_to_start: timedelta | None  # None = catch-all / slowest bucket
    interval_seconds: int


def build_default_buckets(settings: Settings) -> list[PollingBucket]:
    return [
        PollingBucket("lt_1h", timedelta(hours=1), settings.discovery_poll_seconds_lt_1h),
        PollingBucket("1h_6h", timedelta(hours=6), settings.discovery_poll_seconds_1h_6h),
        PollingBucket("6h_24h", timedelta(hours=24), settings.discovery_poll_seconds_6h_24h),
        PollingBucket("gt_24h", None, settings.discovery_poll_seconds_gt_24h),
    ]


def bucket_for(buckets: list[PollingBucket], time_to_start: timedelta | None) -> PollingBucket:
    """`time_to_start=None` means no known upcoming event yet for this sport
    (e.g. never discovered before) — falls back to the slowest baseline
    cadence rather than the fastest, since there is nothing urgent to poll
    for yet."""
    if time_to_start is not None:
        for bucket in buckets:
            if bucket.max_time_to_start is not None and time_to_start <= bucket.max_time_to_start:
                return bucket
    return buckets[-1]


class DiscoveryScheduler:
    """Tracks, per sport, when the next poll is due. Pure state machine —
    the caller supplies `now` and the sport's nearest-event time-to-start
    so this class has no I/O of its own and is trivially unit-testable."""

    def __init__(self, settings: Settings) -> None:
        self._buckets = build_default_buckets(settings)
        self._next_due: dict[str, datetime] = {}
        self._last_bucket: dict[str, str] = {}

    def is_due(self, sport_key: str, now: datetime) -> bool:
        due = self._next_due.get(sport_key)
        return due is None or now >= due

    def mark_polled(self, sport_key: str, now: datetime, time_to_start: timedelta | None) -> None:
        bucket = bucket_for(self._buckets, time_to_start)
        self._next_due[sport_key] = now + timedelta(seconds=bucket.interval_seconds)
        self._last_bucket[sport_key] = bucket.label

    def bucket_label(self, sport_key: str) -> str | None:
        return self._last_bucket.get(sport_key)
