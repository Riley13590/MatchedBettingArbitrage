"""arbitrage opportunity segment + economics telemetry (Milestone 3)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_NEW_COLUMNS = (
    sa.Column("sport", sa.String(), nullable=True),
    sa.Column("competition", sa.String(), nullable=True),
    sa.Column("market_family", sa.String(), nullable=True),
    sa.Column("venues", sa.String(), nullable=True),
    sa.Column("time_to_start_bucket", sa.String(), nullable=True),
    sa.Column("quote_age_ms_at_detection", sa.Numeric(12, 2), nullable=True),
    sa.Column("executable_stake_gbp", sa.Numeric(14, 2), nullable=True),
    sa.Column("executable_edge_gbp", sa.Numeric(14, 2), nullable=True),
    sa.Column("lifetime_ms", sa.Numeric(14, 2), nullable=True),
    sa.Column("verification_outcome", sa.String(), nullable=True),
    sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("verified_bookmaker_price", sa.Numeric(12, 5), nullable=True),
    sa.Column("verified_exchange_price", sa.Numeric(12, 5), nullable=True),
)


def upgrade() -> None:
    for column in _NEW_COLUMNS:
        op.add_column("opportunities", column)
    op.create_index(
        "idx_opportunities_segment",
        "opportunities",
        ["sport", "market_family", "detected_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_opportunities_segment", table_name="opportunities")
    for column in reversed(_NEW_COLUMNS):
        op.drop_column("opportunities", column.name)
