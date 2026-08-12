from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import redis.asyncio as redis_asyncio
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.config.settings import Settings, get_settings
from marketedge.storage.db import get_sessionmaker

_redis_client: redis_asyncio.Redis | None = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


def get_redis() -> redis_asyncio.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)
    return _redis_client


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[redis_asyncio.Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
