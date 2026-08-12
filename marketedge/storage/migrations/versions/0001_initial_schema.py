"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-12

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from marketedge.config.venue_rules import DEFAULT_VENUES

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    venues = op.create_table(
        "venues",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data_allowed", sa.Boolean(), nullable=False),
        sa.Column("execution_allowed", sa.Boolean(), nullable=False),
        sa.Column("geo_status", sa.String(), nullable=False),
        sa.Column("terms_status", sa.String(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_url", sa.String(), nullable=True),
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sport", sa.String(), nullable=False),
        sa.Column("competition", sa.String(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("home_participant", sa.String(), nullable=True),
        sa.Column("away_participant", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "vendor_events",
        sa.Column("venue_id", sa.BigInteger(), sa.ForeignKey("venues.id"), primary_key=True),
        sa.Column("vendor_event_id", sa.String(), primary_key=True),
        sa.Column(
            "canonical_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id"),
            nullable=True,
        ),
        sa.Column("raw_name", sa.String(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_confidence", sa.Numeric(6, 5), nullable=True),
    )

    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False
        ),
        sa.Column("market_type", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("line", sa.Numeric(12, 4), nullable=True),
        sa.Column("settlement_scope", sa.String(), nullable=False),
        sa.UniqueConstraint("event_id", "market_type", "period", "line", "settlement_scope"),
    )

    op.create_table(
        "selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=False
        ),
        sa.Column("outcome_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.UniqueConstraint("market_id", "outcome_key"),
    )

    op.create_table(
        "quotes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.BigInteger(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column(
            "selection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("selections.id"),
            nullable=False,
        ),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(12, 5), nullable=False),
        sa.Column("available_size", sa.Numeric(14, 2), nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_live", sa.Boolean(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "idx_quotes_selection_received", "quotes", ["selection_id", sa.text("received_at DESC")]
    )

    op.create_table(
        "opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy", sa.String(), nullable=False),
        sa.Column(
            "event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=True
        ),
        sa.Column(
            "market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=True
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("expected_roi", sa.Numeric(10, 6), nullable=True),
        sa.Column("worst_case_profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", sa.BigInteger(), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id"),
            nullable=True,
        ),
        sa.Column("client_order_id", sa.String(), nullable=False, unique=True),
        sa.Column("vendor_order_id", sa.String(), nullable=True),
        sa.Column(
            "selection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("selections.id"),
            nullable=False,
        ),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("requested_price", sa.Numeric(12, 5), nullable=False),
        sa.Column("requested_size", sa.Numeric(14, 2), nullable=False),
        sa.Column("matched_size", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("average_matched_price", sa.Numeric(12, 5), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "fills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False
        ),
        sa.Column("price", sa.Numeric(12, 5), nullable=False),
        sa.Column("size", sa.Numeric(14, 2), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vendor_fill_id", sa.String(), nullable=True),
        sa.UniqueConstraint("order_id", "vendor_fill_id"),
    )

    op.create_table(
        "signal_evaluations",
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id"),
            primary_key=True,
        ),
        sa.Column("taken_price", sa.Numeric(12, 5), nullable=True),
        sa.Column("fair_price_at_signal", sa.Numeric(12, 5), nullable=True),
        sa.Column("reference_price_t60", sa.Numeric(12, 5), nullable=True),
        sa.Column("reference_price_t10", sa.Numeric(12, 5), nullable=True),
        sa.Column("closing_price", sa.Numeric(12, 5), nullable=True),
        sa.Column("clv", sa.Numeric(10, 6), nullable=True),
        sa.Column("expected_value", sa.Numeric(10, 6), nullable=True),
        sa.Column("realised_pnl", sa.Numeric(14, 2), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        venues,
        [
            {
                "code": seed.code,
                "name": seed.name,
                "data_allowed": seed.data_allowed,
                "execution_allowed": seed.execution_allowed,
                "geo_status": seed.geo_status,
                "terms_status": seed.terms_status,
                "checked_at": now,
                "evidence_url": seed.evidence_url,
            }
            for seed in DEFAULT_VENUES
        ],
    )


def downgrade() -> None:
    op.drop_table("signal_evaluations")
    op.drop_table("fills")
    op.drop_table("orders")
    op.drop_table("opportunities")
    op.drop_index("idx_quotes_selection_received", table_name="quotes")
    op.drop_table("quotes")
    op.drop_table("selections")
    op.drop_table("markets")
    op.drop_table("vendor_events")
    op.drop_table("events")
    op.drop_table("venues")
