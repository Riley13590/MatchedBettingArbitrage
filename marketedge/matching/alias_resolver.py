"""DB-backed alias override layer (spec section 11.2).

Checked before the fuzzy `aliases.normalize()` fallback because it is exact
and human-verified — e.g. seeded via `scripts/seed_aliases.py` or from a
confirmed manual review of a `REVIEW`-confidence event match. Not currently
called from inside a connector mapper (those must stay synchronous and
I/O-free — see `matching/selection_matcher.py`); it's for future use by an
async review workflow or a promotion path that turns confirmed matches into
permanent aliases.
"""

from __future__ import annotations

from marketedge.matching.aliases import normalize
from marketedge.storage.repositories.aliases import ParticipantAliasRepository


class AliasResolver:
    def __init__(self, repository: ParticipantAliasRepository) -> None:
        self._repository = repository

    async def resolve(self, sport: str, raw_name: str) -> str:
        override = await self._repository.lookup(sport, raw_name)
        if override is not None:
            return override
        return normalize(raw_name)
