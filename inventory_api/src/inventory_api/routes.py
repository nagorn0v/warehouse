import json
import logging
from datetime import datetime, timezone

from aiohttp import web
from sqlalchemy import insert

from inventory_api.api import get_balance, get_balance_rows, get_top_skus, get_warehouses
from inventory_api.db import outbox, stock_events
from inventory_api.enum import StockOperation
from inventory_api.schemas import (
    StockList,
    StockOpIn,
    StockOpOut,
    StockQuery,
    StockSnapshot,
    StockSummary,
    StockSummaryQuery,
)

logger = logging.getLogger(__name__)


def _safe_validation_errors(exc) -> list[dict]:
    """Возвращает ошибки валидации.

    Args:
        exc: исключение со списком ошибок (например, ValidationError).

    Returns:
        Список словарей ошибок.
    """

    return [
        {k: v for k, v in error.items() if k != "ctx"} for error in exc.errors()
    ]


async def health(request: web.Request) -> web.Response:
    """
    Health check
    ---
    summary: Проверка готовности сервиса
    tags:
      - system
    responses:
      '200':
        description: Сервис жив
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
    """
    return web.json_response({"status": "ok"})


async def _create_stock_event(request: web.Request, operation: StockOperation) -> web.Response:
    """Создаёт событие склада в транзакции с записью в outbox.

    Args:
        request: запрос.
        operation: тип операции — StockOperation.receipt или StockOperation.issue.

    Returns:
        Ответ:
          - 201 с созданным событием
          - 400 при ошибке валидации или недостаточном остатке
          - 500 при ошибке БД.
    """

    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"detail": "invalid json"}, status=400)

    try:
        payload = StockOpIn(**data)
    except Exception as exc:
        return web.json_response(
            {"detail": _safe_validation_errors(exc)}, status=400
        )

    engine = request.app["engine"]
    now = datetime.now(timezone.utc)

    try:
        async with engine.begin() as conn:
            if operation == StockOperation.issue:
                balance = await get_balance(conn, payload.warehouse, payload.sku)
                if payload.qty > balance:
                    return web.json_response({"detail": "insufficient stock"}, status=400)
                
            result = await conn.execute(
                insert(
                  stock_events
                ).values(
                  operation=operation.value, 
                  sku=payload.sku, 
                  qty=payload.qty, 
                  warehouse=payload.warehouse
                ).returning(
                  stock_events.c.id, 
                  stock_events.c.created_at
                )
            )
            row = result.one()

            event = {
                "stock_event_id": row.id,
                "operation": operation.value,
                "sku": payload.sku,
                "qty": payload.qty,
                "warehouse": payload.warehouse,
                "timestamp": (row.created_at or now).isoformat(),
            }

            await conn.execute(insert(outbox).values(stock_event_id=row.id, payload=event))

    except Exception:
        logger.exception("failed to store stock event")
        return web.json_response({"detail": "internal error"}, status=500)

    response = StockOpOut(
        id=row.id,
        sku=payload.sku,
        qty=payload.qty,
        warehouse=payload.warehouse,
        created_at=row.created_at or now,
    )

    return web.json_response(response.model_dump(mode="json"), status=201)


async def create_receipt(request: web.Request) -> web.Response:
    """
    Create receipt
    ---
    summary: Приход товара на склад
    tags:
      - stock
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/StockOpIn"
    responses:
      '201':
        description: Событие создано
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/StockOpOut"
      '400':
        description: Некорректное тело запроса
      '500':
        description: Внутренняя ошибка
    """

    return await _create_stock_event(request, StockOperation.receipt)


async def create_issue(request: web.Request) -> web.Response:
    """
    Create issue
    ---
    summary: Расход товара со склада
    tags:
      - stock
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/StockOpIn"
    responses:
      '201':
        description: Событие создано
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/StockOpOut"
      '400':
        description: Некорректное тело или недостаточный остаток
      '500':
        description: Внутренняя ошибка
    """

    return await _create_stock_event(request, StockOperation.issue)


async def get_stock(request: web.Request) -> web.Response:
    """
    Get stock
    ---
    summary: Остатки на складе
    tags:
      - stock
    parameters:
      - name: warehouse
        in: query
        required: true
        description: Идентификатор склада
        schema:
          type: string
      - name: sku
        in: query
        required: false
        description: Идентификатор товара
        schema:
          type: string
    responses:
      '200':
        description: Остаток(и)
        content:
          application/json:
            schema:
              oneOf:
                - $ref: "#/components/schemas/StockSnapshot"
                - $ref: "#/components/schemas/StockList"
      '400':
        description: Некорректные параметры
      '404':
        description: Данные не найдены
    """

    try:
        query = StockQuery(**request.query)
    except Exception as exc:
        
        return web.json_response({"detail": _safe_validation_errors(exc)}, status=400)

    engine = request.app["engine"]
    async with engine.connect() as conn:
        rows = await get_balance_rows(conn, query.warehouse, query.sku)
        if not rows:
            
            return web.json_response({"detail": "not found"}, status=404)

        if query.sku is not None:
            response = StockSnapshot(
                warehouse=query.warehouse,
                sku=query.sku,
                qty=sum(row["qty"] or 0 for row in rows),
            )
        else:
            response = StockList(
              warehouse=query.warehouse,
              skus=[{"sku": row["sku"], "qty": row["qty"] or 0} for row in rows],
            )

        return web.json_response(response.model_dump(mode="json"), status=200)


async def get_stock_summary(request: web.Request) -> web.Response:
    """
    Stock summary
    ---
    summary: Сводка по складам и топ товаров
    tags:
      - stock
    parameters:
      - name: top_n
        in: query
        required: false
        description: Количество товаров в топе (по умолчанию 5)
        schema:
          type: integer
          minimum: 1
          default: 5
      - name: show_wh
        in: query
        required: false
        description: Если true, к каждому товару добавляется расшифровка по складам с остатками > 0
        schema:
          type: boolean
          default: false
    responses:
      '200':
        description: Сводка
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/StockSummary"
      '400':
        description: Некорректные параметры
    """
    
    try:
        query = StockSummaryQuery(**request.query)
    except Exception as exc:
        
        return web.json_response({"detail": _safe_validation_errors(exc)}, status=400)

    engine = request.app["engine"]
    top_n = query.top_n if query.top_n is not None else 5

    async with engine.connect() as conn:
        warehouses = await get_warehouses(conn)
        top_skus = await get_top_skus(conn, top_n, show_wh=bool(query.show_wh))

    response = StockSummary(warehouses=warehouses, top_skus=top_skus)
    
    return web.json_response(response.model_dump(mode="json", exclude_none=True), status=200)


def setup_routes(app: web.Application, swagger) -> None:
    """Регистрирует HTTP-роуты сервиса в Swagger.

    Args:
        app: aiohttp-приложение.
        swagger: экземпляр SwaggerDocs для добавления маршрутов.
    """

    swagger.add_get("/health", health)
    swagger.add_post("/receipts", create_receipt)
    swagger.add_post("/issues", create_issue)
    swagger.add_get("/stock/summary", get_stock_summary)
    swagger.add_get("/stock", get_stock)