"""api_usage + participant_aliases (Milestone 2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("sport_key", sa.String(), nullable=True),
        sa.Column("market_keys", sa.String(), nullable=True),
        sa.Column("regions", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credits_used", sa.BigInteger(), nullable=True),
        sa.Column("remaining_credits_reported", sa.BigInteger(), nullable=True),
        sa.Column("response_status", sa.BigInteger(), nullable=True),
        sa.Column("response_latency_ms", sa.BigInteger(), nullable=True),
    )
    op.create_index("idx_api_usage_provider_requested", "api_usage", ["provider", "requested_at"])

    op.create_table(
        "participant_aliases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("sport", sa.String(), nullable=False),
        sa.Column("raw_name", sa.String(), nullable=False),
        sa.Column("canonical_key", sa.String(), nullable=False),
        sa.UniqueConstraint("sport", "raw_name"),
    )


def downgrade() -> None:
    op.drop_table("participant_aliases")
    op.drop_index("idx_api_usage_provider_requested", table_name="api_usage")
    op.drop_table("api_usage")
