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
)


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    """Truncates all non-seed tables after every integration/replay test so
    tests don't depend on execution order. `venues` is intentionally
    excluded — it holds the migration-seeded capability rows every test
    relies on."""
    yield
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
