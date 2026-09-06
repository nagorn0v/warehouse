"""create stock_agg and processed_events

Revision ID: 0001
Revises:
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "stock_agg"):
        op.create_table(
            "stock_agg",
            sa.Column("warehouse", sa.Text(), nullable=False),
            sa.Column("sku", sa.Text(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("warehouse", "sku"),
        )

    if not _table_exists(bind, "processed_events"):
        op.create_table(
            "processed_events",
            sa.Column("stock_event_id", sa.BigInteger(), autoincrement=False, nullable=False),
            sa.Column(
                "processed_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("stock_event_id"),
        )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("stock_agg")