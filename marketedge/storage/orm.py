"""SQLAlchemy 2 ORM models — the persistence shape of the schema in spec
section 8.

Deliberately separate from `marketedge.domain.models` (pure, vendor-neutral
dataclasses used by strategy/connector code). Repositories translate
between the two; strategy code never imports this module.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    data_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    geo_status: Mapped[str] = mapped_column(String, nullable=False)
    terms_status: Mapped[str] = mapped_column(String, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    competition: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    home_participant: Mapped[str | None] = mapped_column(String, nullable=True)
    away_participant: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    markets: Mapped[list[Market]] = relationship(back_populates="event")


class VendorEvent(Base):
    __tablename__ = "vendor_events"

    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), primary_key=True)
    vendor_event_id: Mapped[str] = mapped_column(String, primary_key=True)
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=True
    )
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)


class Market(Base):
    __tablename__ = "markets"
    __table_args__ = (
        UniqueConstraint("event_id", "market_type", "period", "line", "settlement_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    market_type: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    line: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    settlement_scope: Mapped[str] = mapped_column(String, nullable=False)

    event: Mapped[Event] = relationship(back_populates="markets")
    selections: Mapped[list[Selection]] = relationship(back_populates="market")


class Selection(Base):
    __tablename__ = "selections"
    __table_args__ = (UniqueConstraint("market_id", "outcome_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"))
    outcome_key: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)

    market: Mapped[Market] = relationship(back_populates="selections")


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"))
    selection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("selections.id"))
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 5), nullable=False)
    available_size: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    market_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id")
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_profit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    expected_roi: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    worst_case_profit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True
    )
    client_order_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    vendor_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    selection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("selections.id"))
    side: Mapped[str] = mapped_column(String, nullable=False)
    requested_price: Mapped[Decimal] = mapped_column(Numeric(12, 5), nullable=False)
    requested_size: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    matched_size: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0)
    )
    average_matched_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 5), nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Fill(Base):
    __tablename__ = "fills"
    __table_args__ = (UniqueConstraint("order_id", "vendor_fill_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 5), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vendor_fill_id: Mapped[str | None] = mapped_column(String, nullable=True)


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), primary_key=True
    )
    taken_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 5), nullable=True)
    fair_price_at_signal: Mapped[Decimal | None] = mapped_column(Numeric(12, 5), nullable=True)
    reference_price_t60: Mapped[Decimal | None] = mapped_column(Numeric(12, 5), nullable=True)
    reference_price_t10: Mapped[Decimal | None] = mapped_column(Numeric(12, 5), nullable=True)
    closing_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 5), nullable=True)
    clv: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    realised_pnl: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiUsage(Base):
    """Milestone 2 / spec section 41.2 — one row per outbound request to a
    metered market-data provider, so credit usage/budget forecasting never
    has to be reconstructed from logs."""

    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    sport_key: Mapped[str | None] = mapped_column(String, nullable=True)
    market_keys: Mapped[str | None] = mapped_column(String, nullable=True)
    regions: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    credits_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remaining_credits_reported: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    response_status: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    response_latency_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ParticipantAlias(Base):
    """Spec section 11.2 — controlled alias table, e.g. "Man Utd" -> team
    key "MAN_UTD", preferred over relying solely on fuzzy matching."""

    __tablename__ = "participant_aliases"
    __table_args__ = (UniqueConstraint("sport", "raw_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    canonical_key: Mapped[str] = mapped_column(String, nullable=False)
