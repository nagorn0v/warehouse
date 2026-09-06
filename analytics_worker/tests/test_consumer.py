from sqlalchemy import func, select

from analytics_worker.config import Settings
from analytics_worker.consumer import AnalyticsConsumer
from analytics_worker.db import processed_events, stock_agg


def _make_consumer(engine, redis=None):
    """Создаёт и возвращает консьюмера с тестовыми настройками.

    Args:
        engine: движок sqlalchemy.
        redis: клиент redis.

    Returns:
        Экземпляр AnalyticsConsumer.
    """

    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x",
        redis_url="redis://x",
        consumer_group="test-group",
        consumer_name="test-consumer",
        batch_size=2,
        block_ms=5,
    )

    return AnalyticsConsumer(engine, redis or object(), settings)


async def _qty(engine, warehouse, sku):
    """Возвращает агрегированный остаток sku на складе.

    Args:
        engine: асинхронный движок SQLAlchemy.
        warehouse: идентификатор склада.
        sku: идентификатор товара.

    Returns:
        Остаток или None, если пара (warehouse, sku) отсутствует.
    """

    async with engine.begin() as conn:
        row = (
            await conn.execute(select(stock_agg.c.qty).where(stock_agg.c.warehouse == warehouse, stock_agg.c.sku == sku))
        ).scalar_one_or_none()

    return row


async def _processed_count(engine):
    """Возвращает количество записей в processed_events.

    Args:
        engine: движок sqlalchemy.

    Returns:
        Количество обработанных событий.
    """

    async with engine.begin() as conn:
        return (await conn.execute(select(func.count()).select_from(processed_events))).scalar_one()


async def test_apply_event_receipt_upserts_stock(engine, clean_tables):
    """Тестирует, что приход увеличивает агрегированный остаток."""

    consumer = _make_consumer(engine)
    payload = {
        "stock_event_id": 1,
        "operation": "receipt",
        "sku": "SKU-1",
        "warehouse": "WH-A",
        "qty": 3,
    }

    async with engine.begin() as conn:
        await consumer._apply_event(conn, "inventory.receipt", b"1", payload)

    assert await _qty(engine, "WH-A", "SKU-1") == 3


async def test_apply_event_issue_reduces_stock(engine, clean_tables):
    """Тестирует, что расходы с разными stock_event_id для одной пары (warehouse, sku) уменьшает агрегированный остаток."""

    consumer = _make_consumer(engine)
    async with engine.begin() as conn:
        await consumer._apply_event(
            conn, "inventory.receipt", b"1",
            {"stock_event_id": 1, "operation": "receipt", "sku": "SKU-1", "warehouse": "WH-A", "qty": 5},
        )
        await consumer._apply_event(
            conn, "inventory.issue", b"2",
            {"stock_event_id": 2, "operation": "issue", "sku": "SKU-1", "warehouse": "WH-A", "qty": 2},
        )

    assert await _qty(engine, "WH-A", "SKU-1") == 3


async def test_apply_event_same_key_conflict_accumulates(engine, clean_tables): # fixme
    """Тестирует, что приходы с разными stock_event_id для одной пары (warehouse, sku) увеличивают агрегированный остаток."""

    consumer = _make_consumer(engine)
    async with engine.begin() as conn:
        await consumer._apply_event(
            conn, "inventory.receipt", b"1",
            {"stock_event_id": 1, "operation": "receipt", "sku": "SKU-1", "warehouse": "WH-A", "qty": 4},
        )
        await consumer._apply_event(
            conn, "inventory.receipt", b"2",
            {"stock_event_id": 2, "operation": "receipt", "sku": "SKU-1", "warehouse": "WH-A", "qty": 6},
        )

    assert await _qty(engine, "WH-A", "SKU-1") == 10


async def test_apply_event_skips_duplicate(engine, clean_tables):
    """Проверяет, что повторное событие с тем же stock_event_id игнорируется."""

    consumer = _make_consumer(engine)
    payload = {
        "stock_event_id": 1,
        "operation": "receipt",
        "sku": "SKU-1",
        "warehouse": "WH-A",
        "qty": 3,
    }

    async with engine.begin() as conn:
        await consumer._apply_event(conn, "inventory.receipt", b"1", payload)
        await consumer._apply_event(conn, "inventory.receipt", b"1", payload)

    assert await _qty(engine, "WH-A", "SKU-1") == 3
    assert await _processed_count(engine) == 1
