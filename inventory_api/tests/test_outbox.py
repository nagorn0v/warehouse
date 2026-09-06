from datetime import datetime, timezone

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, insert, text
from sqlalchemy.ext.asyncio import AsyncEngine

from inventory_api.enum import StockStream
from inventory_api.db import outbox, stock_events
from inventory_api.outbox import OutboxPublisher


async def test_publish(engine, redis):
    """Тестирует, что публикатор пишет сообщение в стрим receipt без изменений."""

    publisher = OutboxPublisher(engine, redis, poll_interval=1.0, batch_size=100)
    await publisher.publish(StockStream.receipt, {"stock_event_id": 1, "sku": "S", "qty": 2})

    entries = await redis.xrange(StockStream.receipt.value)
    assert len(entries) == 1

    _, fields = entries[0]
    assert fields == {"stock_event_id": "1", "sku": "S", "qty": "2"}


async def test_publish_issue_stream(engine, redis):
    """Тестирует, что публикатор пишет сообщение в стрим issue без изменений."""

    publisher = OutboxPublisher(engine, redis, poll_interval=1.0, batch_size=100)
    await publisher.publish(StockStream.issue, {"stock_event_id": 1, "sku": "S", "qty": 2})

    assert await redis.xrange(StockStream.receipt.value) == []

    entries = await redis.xrange(StockStream.issue.value)
    assert len(entries) == 1

    _, fields = entries[0]
    assert fields == {"stock_event_id": "1", "sku": "S", "qty": "2"}


async def test_publisher_publishes_and_marks(engine, redis, clean_tables):
    """Тестирует публикацию из outbox."""

    async with engine.begin() as conn:
        row = await conn.execute(
            insert(stock_events).values(
                operation="receipt", sku="SKU-X", qty=3, warehouse="WH-B"
            )
        )
        event = {
            "stock_event_id": 1,
            "operation": "receipt",
            "sku": "SKU-X",
            "qty": 3,
            "warehouse": "WH-B",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await conn.execute(insert(outbox).values(stock_event_id=1, payload=event))

    publisher = OutboxPublisher(engine, redis, poll_interval=1.0, batch_size=100)
    await publisher.run_once()

    entries = await redis.xrange(StockStream.receipt.value)
    assert len(entries) == 1

    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT published_at FROM outbox WHERE id = 1"))).scalar()
        assert row is not None


async def test_publisher_skips_published(engine, redis, clean_tables):
    """Тестирует, что ранее опубликованные события пропускаются."""

    async with engine.begin() as conn:
        await conn.execute(
            insert(stock_events).values(
                operation="receipt", sku="SKU-Y", qty=1, warehouse="WH-C"
            )
        )
        event = {
            "stock_event_id": 1,
            "operation": "receipt",
            "sku": "SKU-Y",
            "qty": 1,
            "warehouse": "WH-C",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await conn.execute(
            insert(outbox).values(
                stock_event_id=1,
                payload=event,
                published_at=func.now(),
            )
        )

    publisher = OutboxPublisher(engine, redis, poll_interval=1.0, batch_size=100)
    await publisher.run_once()
    entries = await redis.xrange(StockStream.receipt.value)
    assert entries == []