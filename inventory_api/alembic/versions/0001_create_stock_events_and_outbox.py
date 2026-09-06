"""create stock_events and outbox

Revision ID: 0001
Revises:
Create Date: 2026-09-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

stock_operation_type = PG_ENUM(
    "receipt",
    "issue",
    name="stock_operation_type",
    create_type=False,
)


def _enum_exists(bind) -> bool:
    return stock_operation_type.name in {e.name for e in inspect(bind).get_enums()}


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _index_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_indexes("outbox")


def upgrade() -> None:
    bind = op.get_bind()

    if not _enum_exists(bind):
        stock_operation_type.create(bind)

    if not _table_exists(bind, "stock_events"):
        op.create_table(
            "stock_events",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("operation", stock_operation_type, nullable=False),
            sa.Column("sku", sa.Text(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("warehouse", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint("qty > 0", name="ck_stock_events_qty_positive"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists(bind, "outbox"):
        op.create_table(
            "outbox",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("stock_event_id", sa.BigInteger(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["stock_event_id"],
                ["stock_events.id"],
                name="fk_outbox_stock_event",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists(bind, "ix_outbox_unpublished"):
        op.create_index(
            "ix_outbox_unpublished", "outbox", ["published_at", "id"], unique=False
        )


def downgrade() -> None:
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_table("stock_events")
    if _enum_exists(op.get_bind()):
        stock_operation_type.drop(op.get_bind())