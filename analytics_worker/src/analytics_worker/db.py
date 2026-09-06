from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from analytics_worker.config import Settings

metadata = MetaData()

# таблица остатков в разрезе единицы товара и склада
stock_agg = Table(
    "stock_agg",
    metadata,
    Column("warehouse", Text, nullable=False),
    Column("sku", Text, nullable=False),
    Column("qty", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("warehouse", "sku"),
)

# Реестр применённых событий, необходим для избежания случая, когда одно и тоже событие обрабатывается несколько раз
# stock_event_id — PK строки из inventory.stock_events
processed_events = Table(
    "processed_events",
    metadata,
    Column("stock_event_id", BigInteger, primary_key=True, autoincrement=False),
    Column("processed_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def create_engine(settings: Settings) -> AsyncEngine:
    """Создает движок для работы с БД.
    
    Args:
        settings: настройки сервиса.
    """
    
    return create_async_engine(settings.database_url, echo=False)