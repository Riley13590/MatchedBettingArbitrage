"""Seed the `participant_aliases` table with a small set of known naming
variants (spec section 11.2 — a controlled alias table, preferred over
relying solely on fuzzy matching).

This is a bootstrap starting set, not exhaustive; extend it as genuine
cross-venue mismatches are found (e.g. via a `REVIEW`-confidence event that
turns out correct on manual inspection).

Usage:
    python -m scripts.seed_aliases
"""

from __future__ import annotations

import asyncio

from marketedge.storage.db import session_scope
from marketedge.storage.repositories.aliases import ParticipantAliasRepository

# (sport, raw_name_as_seen_from_a_vendor, canonical_key)
SEED_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("Soccer", "Man Utd", "MANCHESTER_UNITED"),
    ("Soccer", "Manchester United", "MANCHESTER_UNITED"),
    ("Soccer", "Man City", "MANCHESTER_CITY"),
    ("Soccer", "Manchester City", "MANCHESTER_CITY"),
    ("Soccer", "Spurs", "TOTTENHAM_HOTSPUR"),
    ("Soccer", "Tottenham", "TOTTENHAM_HOTSPUR"),
    ("Soccer", "Tottenham Hotspur", "TOTTENHAM_HOTSPUR"),
    ("Soccer", "Wolves", "WOLVERHAMPTON_WANDERERS"),
    ("Soccer", "Wolverhampton Wanderers", "WOLVERHAMPTON_WANDERERS"),
    ("Soccer", "Nott'm Forest", "NOTTINGHAM_FOREST"),
    ("Soccer", "Nottingham Forest", "NOTTINGHAM_FOREST"),
)


async def main() -> None:
    async with session_scope() as session:
        repo = ParticipantAliasRepository(session)
        for sport, raw_name, canonical_key in SEED_ALIASES:
            await repo.upsert(sport, raw_name, canonical_key)
    print(f"Seeded {len(SEED_ALIASES)} participant aliases.")


if __name__ == "__main__":
    asyncio.run(main())
