from sqlalchemy import func, insert

from analytics_worker.db import stock_agg


async def _insert_stock(engine, warehouse, sku, qty):
    """Вставляет запись агрегированного остатка напрямую в БД.

    Args:
        engine: движок sqlalchemy.
        warehouse: идентификатор склада.
        sku: идентификатор товара.
        qty: остаток.
    """

    async with engine.begin() as conn:
        await conn.execute(
            insert(stock_agg).values(
                warehouse=warehouse, sku=sku, qty=qty, updated_at=func.now()
            )
        )


async def test_stock_not_found(client, clean_tables):
    """Тестирует ответ 404 для склада без остатков."""

    response = await client.get("/stock?warehouse=WH-A")

    assert response.status == 404


async def test_stock_by_sku(client, engine, clean_tables):
    """Тестирует получение остатка конкретного sku на складе."""

    await _insert_stock(engine, "WH-A", "SKU-1", 6)

    response = await client.get("/stock?warehouse=WH-A&sku=SKU-1")

    assert response.status == 200
    assert await response.json() == {
        "warehouse": "WH-A",
        "sku": "SKU-1",
        "qty": 6,
    }


async def test_stock_all_skus(client, engine, clean_tables):
    """Тестирует получение остатков всех sku выбранного склада."""

    await _insert_stock(engine, "WH-A", "SKU-1", 6)
    await _insert_stock(engine, "WH-A", "SKU-2", 4)
    await _insert_stock(engine, "WH-B", "SKU-9", 10)

    response = await client.get("/stock?warehouse=WH-A")
    assert response.status == 200

    body = await response.json()
    assert body["warehouse"] == "WH-A"
    assert {item["sku"]: item["qty"] for item in body["skus"]} == {"SKU-1": 6, "SKU-2": 4}


async def test_stock_sku_not_found_in_warehouse(client, engine, clean_tables):
    """Тестирует ответ 404 для несуществующего sku на складе."""

    await _insert_stock(engine, "WH-A", "SKU-1", 6)

    response = await client.get("/stock?warehouse=WH-A&sku=TEST")
    assert response.status == 404


async def test_stock_missing_warehouse(client):
    """Тестирует ответ 400 при отсутствии обязательного параметра warehouse."""

    response = await client.get("/stock?sku=SKU-1")
    assert response.status == 400


async def test_stock_blank_warehouse(client):
    """Тестирует 400 для пустого значения warehouse."""

    response = await client.get("/stock?warehouse=   ")
    assert response.status == 400