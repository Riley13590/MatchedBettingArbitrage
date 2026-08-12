"""Turns a vendor QuoteDraft into a persisted Quote.

Vendor-neutral: takes plain values (already resolved to a canonical
selection UUID by the caller) and knows nothing about Betfair or any other
vendor's wire format. This is the seam `tests/replay` exercises to prove
the same input stream produces the same rows deterministically (spec
section 27.3).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from marketedge.domain.enums import Side
from marketedge.observability.logging import log_event
from marketedge.observability.metrics import quote_age_ms, quotes_received_total
from marketedge.storage.repositories.quotes import QuoteRepository

logger = logging.getLogger(__name__)

_LATEST_QUOTE_TTL_SECONDS = 300


@dataclass(frozen=True)
class ResolvedQuote:
    """A vendor QuoteDraft resolved against the canonical schema — the input
    to `QuoteProcessor.process`."""

    venue_id: int
    venue_code: str
    sport: str
    selection_id: uuid.UUID
    side: Side
    price: Decimal
    available_size: Decimal | None
    is_live: bool
    source_timestamp_utc: datetime | None
    raw_payload: dict[str, Any] | None = None


class QuoteProcessor:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def process(self, session: AsyncSession, quote: ResolvedQuote) -> None:
        received_at = datetime.now(UTC)

        await QuoteRepository(session).append(
            venue_id=quote.venue_id,
            selection_id=quote.selection_id,
            side=quote.side.value,
            price=quote.price,
            available_size=quote.available_size,
            source_timestamp=quote.source_timestamp_utc,
            received_at=received_at,
            is_live=quote.is_live,
            raw_payload=quote.raw_payload,
        )

        await self._write_latest_cache(quote, received_at)

        quotes_received_total.labels(venue=quote.venue_code).inc()
        if quote.source_timestamp_utc is not None:
            age_ms = (received_at - quote.source_timestamp_utc).total_seconds() * 1000
            quote_age_ms.labels(venue=quote.venue_code, sport=quote.sport).observe(age_ms)

        log_event(
            logger,
            "quote_processed",
            venue=quote.venue_code,
            selection_id=str(quote.selection_id),
            side=quote.side.value,
            price=str(quote.price),
        )

    async def _write_latest_cache(self, quote: ResolvedQuote, received_at: datetime) -> None:
        key = f"quote:latest:{quote.venue_code}:{quote.selection_id}:{quote.side.value}"
        await self._redis.hset(
            key,
            mapping={
                "price": str(quote.price),
                "available_size": str(quote.available_size)
                if quote.available_size is not None
                else "",
                "received_at": received_at.isoformat(),
                "is_live": "1" if quote.is_live else "0",
            },
        )
        await self._redis.expire(key, _LATEST_QUOTE_TTL_SECONDS)
