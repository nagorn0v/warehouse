import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from analytics_worker.config import Settings
from analytics_worker.db import processed_events, stock_agg

logger = logging.getLogger(__name__)


class AnalyticsConsumer:
    """Класс потребителя событий из redis-stream.
    
    Attributes:
        engine: движок бд
        redis: клиент redis
        group: имя консьюмер-группы
        consumer: имя консьюмера в группе
        batch: размер батча чтения из стрима
        block: время блокирующего ожидания чтения
        stop: событие остановки консьюмера.
    """

    _STREAMS = ("inventory.receipt", "inventory.issue")
    _REQUIRED_FIELDS = ("stock_event_id", "operation", "sku", "warehouse", "qty")
    _VALID_OPERATIONS = frozenset({"receipt", "issue"})

    def __init__(self, engine: AsyncEngine, redis: Redis, settings: Settings) -> None:
        self._engine = engine
        self._redis = redis
        self._group = settings.consumer_group
        self._consumer = settings.consumer_name
        self._batch = settings.batch_size
        self._block = settings.block_ms
        self._stop = asyncio.Event()

    def validate_event(self, payload: dict) -> tuple[bool, int | None, str | None]:
        """Валидирует событие. 
           Проверяет: 
            - заполненность обязательных полей
            - тип операции
            - корректность значения количества.
        
        Returns:
            Кортеж вида (Флаг валидности, дельта остатка, сообщение об ошибке).
            Дельта положительна для прихода, отрицательна для расхода.
        """

        missing = [f for f in self._REQUIRED_FIELDS if f not in payload or payload[f] is None]
        if missing:
            return False, None, f"missing fields: {missing}"

        operation = payload["operation"]
        if operation not in self._VALID_OPERATIONS:
            return False, None, f"invalid operation: {operation!r}"

        qty_raw = payload["qty"]
        try:
            qty = int(qty_raw)
        except (TypeError, ValueError):
            return False, None, f"invalid qty: {qty_raw!r}"
        
        if isinstance(qty_raw, bool) or qty <= 0:
            return False, None, f"invalid qty: {qty_raw!r}"

        delta = qty if operation == "receipt" else -qty

        return True, delta, None

    async def _upsert(self, conn: AsyncConnection, warehouse: str, sku: str, delta: int) -> None:
        """Обновляет остатки по указанной единице товара в указанном складе.
        
        Args:
            conn: соединение с бд.
            warehouse: идентификатор склада.
            sku: идентификатор товара.
            delta: обновляемое значение (дельта)
        """

        insert_q = pg_insert(stock_agg).values(
            warehouse=warehouse,
            sku=sku,
            qty=delta,
            updated_at=func.now(),
        )
        upsert_q = insert_q.on_conflict_do_update(
            index_elements=[stock_agg.c.warehouse, stock_agg.c.sku],
            set_={
                "qty": stock_agg.c.qty + insert_q.excluded.qty,
                "updated_at": func.now(),
            },
        )

        await conn.execute(upsert_q)

    async def _apply_event(self, conn: AsyncConnection, stream: str, message_id: bytes | str, payload: dict) -> None:
        """Обрабатывает событие из stream: валидирует, обновляет таблицу обрабатываемых событий, обновляет баланс товара.

        Args:
            conn: соединение с бд.
            stream: имя стрима.
            message_id: идентификатор сообщения.
            payload: данные сообщения.
        """

        ok, delta, error = self.validate_event(payload)
        if not ok:
            logger.warning("skip invalid event stream=%s id=%s: %s", stream, message_id, error)

            return

        stock_event_id = int(payload["stock_event_id"])
        processed_event_insert_q = pg_insert(processed_events).values(
            stock_event_id=stock_event_id, processed_at=func.now()
        ).on_conflict_do_nothing(index_elements=[processed_events.c.stock_event_id])

        insert_result = await conn.execute(processed_event_insert_q)

        # Если событие уже есть в таблице обрабатываемых событий, то это дубликат
        if insert_result.rowcount == 0:
            logger.info("skip duplicate event id=%s", stock_event_id)

            return

        await self._upsert(conn, payload["warehouse"], payload["sku"], delta)

    async def _ensure_groups(self) -> None:
        """Создает консьюмер-группы для стримов."""

        for stream in self._STREAMS:
            try:
                await self._redis.xgroup_create(stream, self._group, id="$", mkstream=True)
            except ResponseError as exc:
                # Если группы уже созданы, игнорируем
                if "BUSYGROUP" not in str(exc):

                    raise

    async def _handle_batch(self, batch) -> None:
        """Обрабатывает сообщения из redis:
           Добавляет события в таблицу обрабатываемых значений, обновляет остатки товара, подтверждает обработку сообщений.

        Args:
            batch: события из стрима.
        """

        for entries in batch:
            if not entries:
                continue

            stream, messages = entries
            async with self._engine.begin() as conn:
                for message_id, fields in messages:
                    await self._apply_event(conn, stream, message_id, fields)

            await self._redis.xack(stream, self._group, *[m[0] for m in messages])

    async def run(self) -> None:
        """entry-point чтения из redis."""

        await self._ensure_groups()

        while not self._stop.is_set():
            try:
                batch = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer,
                    count=self._batch,
                    block=self._block,
                    streams={stream: ">" for stream in self._STREAMS},
                )
                if batch:
                    await self._handle_batch(batch)

            except asyncio.CancelledError:

                raise

            except Exception:
                logger.exception("consumer loop error")

    def stop(self) -> None:
        """Останавливает сервис."""

        self._stop.set()