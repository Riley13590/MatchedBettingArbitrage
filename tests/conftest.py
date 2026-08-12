from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from marketedge.storage.db import dispose_engine

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str):
        return json.loads((FIXTURES_DIR / name).read_text())

    return _load


@pytest.fixture(autouse=True)
async def _dispose_engine_per_test() -> AsyncIterator[None]:
    """pytest-asyncio runs each test on its own event loop by default, but
    `marketedge.storage.db` caches a module-level engine/connection pool.
    Disposing after every test forces a fresh engine bound to the next
    test's loop instead of reusing asyncpg connections across loops."""
    yield
    await dispose_engine()
