import pathlib

from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo, SwaggerUiSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from analytics_worker.schemas import StockList, StockQuery, StockSnapshot, StockLine
from analytics_worker.stock_repo import get_balance_rows

_COMPONENTS_PATH = str(pathlib.Path(__file__).resolve().parent / "components.yaml")


def _format_validation_errors(exc) -> list[dict]:
    """Форматирует исключение по ошибке валидации.
    
    Args:
        exc: исключение.
    """
    return [{k: v for k, v in error.items() if k != "ctx"} for error in exc.errors()]


async def health(_: web.Request) -> web.Response:
    """
    Health-check
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


async def get_wh_balance(request: web.Request) -> web.Response:
    """
    Get warehouse balance
    ---
    summary: Возвращает остатки по складу
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
        return web.json_response({"detail": _format_validation_errors(exc)}, status=400)

    engine: AsyncEngine = request.app["engine"]
    async with engine.connect() as conn:
        rows = await get_balance_rows(conn, query.warehouse, query.sku)

        if not rows:

            return web.json_response({"detail": "not found"}, status=404)

        if query.sku is not None:
            response = StockSnapshot(
                warehouse=query.warehouse,
                sku=query.sku,
                qty=rows[0]["qty"] or 0,
            )
        else:
            response = StockList(
                warehouse=query.warehouse,
                skus=[StockLine(sku=row["sku"], qty=row["qty"]) for row in rows],
            )

        return web.json_response(response.model_dump(mode="json"), status=200)


def create_app(engine: AsyncEngine) -> web.Application:
    app = web.Application()
    app["engine"] = engine

    swagger = SwaggerDocs(
        app,
        validate=False,
        info=SwaggerInfo(title="Analytics Worker API", version="1.0.0", description="Агрегированные остатки (stock_agg)"),
        components=_COMPONENTS_PATH,
        swagger_ui_settings=SwaggerUiSettings(path="/docs"),
    )
    swagger.add_get("/health", health)
    swagger.add_get("/stock", get_wh_balance)

    return app
