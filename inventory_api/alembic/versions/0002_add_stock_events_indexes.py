"""add stock_events indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _index_names(bind) -> set[str]:
    return {i["name"] for i in inspect(bind).get_indexes("stock_events")}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _index_names(bind)

    if "ix_stock_events_wh_sku" not in existing:
        op.create_index(
            "ix_stock_events_wh_sku", "stock_events", ["warehouse", "sku"], unique=False
        )

    if "ix_stock_events_sku" not in existing:
        op.create_index("ix_stock_events_sku", "stock_events", ["sku"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _index_names(bind)

    if "ix_stock_events_sku" in existing:
        op.drop_index("ix_stock_events_sku", table_name="stock_events")

    if "ix_stock_events_wh_sku" in existing:
        op.drop_index("ix_stock_events_wh_sku", table_name="stock_events")
