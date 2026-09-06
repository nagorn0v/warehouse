"""Outbox-механизм публикации событий склада в Redis Streams.


"""

import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from inventory_api.db import outbox
from inventory_api.enum import StockStream

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Периодический публикатор событий из outbox-таблицы в Redis.
       События сначала пишутся в таблицу outbox, а затем публикуются в Redis стримы в зависимости от операции.

    Args:
        engine: асинхронный движок SQLAlchemy.
        redis: асинхронный клиент Redis.
        poll_interval: интервал между опросами outbox, сек.
        batch_size: размер батча за один опрос.
    """

    def __init__(self, engine: AsyncEngine, redis: Redis, poll_interval: float, batch_size: int) -> None:
        self._engine = engine
        self._redis = redis
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._stop = asyncio.Event()

    async def publish(self, stream: StockStream, payload: dict) -> None:
        """Публикует событие в redis стрим.

        Args:
            stream: стрим, в который публикуется событие.
            payload: данные события.
        """

        await self._redis.xadd(stream.value, {k: str(v) for k, v in payload.items()})

    async def run_once(self) -> None:
        """Публикует неопубликованные события."""

        async with self._engine.connect() as conn:
            non_published_rows = (
                await conn.execute(
                    select(
                        outbox.c.id, outbox.c.payload
                    ).where(
                        outbox.c.published_at.is_(None)
                    ).order_by(
                        outbox.c.id
                    ).limit(
                        self._batch_size
                    )
                )
            ).mappings().all()

        for row in non_published_rows:
            try:
                await self.publish(StockStream[row["payload"]["operation"]], row["payload"])
            except Exception:
                logger.exception("failed to publish outbox id=%s", row["id"])
                break

            await self._mark_published(row["id"])

    async def _mark_published(self, outbox_id: int) -> None:
        """Помечает событие outbox как опубликованное.

        Args:
            outbox_id: идентификатор строки outbox.
        """

        async with self._engine.begin() as conn:
            await conn.execute(
                update(outbox).where(outbox.c.id == outbox_id).values(published_at=func.now())
            )

    async def run(self) -> None:
        """Запускает цикл публикаций."""

        while not self._stop.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("outbox publisher loop error")

            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """Вызывает остановку цикла публикации."""

        self._stop.set()