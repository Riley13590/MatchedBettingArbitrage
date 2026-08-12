from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from marketedge.storage.db import get_engine

_APP_TABLES = (
    "signal_evaluations",
    "fills",
    "orders",
    "opportunities",
    "quotes",
    "selections",
    "markets",
    "vendor_events",
    "events",
    "api_usage",
    "participant_aliases",
)


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    """Truncates all non-seed tables after every integration/replay test so
    tests don't depend on execution order. `venues` is intentionally
    excluded from the TRUNCATE — it holds the migration-seeded capability
    rows every test relies on — but dynamically-created bookmaker venue
    rows (`oddsapi:*`, spec section 40.1's runtime venue discovery) are
    deleted individually so they don't leak between tests either."""
    yield
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
        await conn.execute(text("DELETE FROM venues WHERE code LIKE 'oddsapi:%'"))
