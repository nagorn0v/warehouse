from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.types import JSON

from inventory_api.config import Settings

metadata = MetaData()

# Перечисление типов операций склада: приход (receipt) или расход (issue).
stock_operation_type = Enum(
    "receipt", # приход
    "issue", # расход
    name="stock_operation_type",
)

# таблица операций (прихода/расхода) по единицам товарам в определенном складе
stock_events = Table(
    "stock_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("operation", stock_operation_type, nullable=False),
    Column("sku", Text, nullable=False),
    Column("qty", Integer, nullable=False),
    Column("warehouse", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("qty > 0", name="ck_stock_events_qty_positive"),
    Index("ix_stock_events_wh_sku", "warehouse", "sku"),
    Index("ix_stock_events_sku", "sku"),
)

# таблица хранения опубликованных событий прихода/расхода товара
outbox = Table(
    "outbox",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("stock_event_id", BigInteger, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Index("ix_outbox_unpublished", "published_at", "id"),
)


def get_engine(settings: Settings) -> AsyncEngine:
    """Создаёт и возвращает движок для работы с бд.

    Args:
        settings: настройки сервиса.
    """

    return create_async_engine(settings.database_url, echo=False)
