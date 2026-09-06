from collections import defaultdict

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from inventory_api.db import stock_events


def get_balance_rows_query(warehouse: str, sku: str | None = None):
    """Строит и возвращает запрос агрегированного остатка по складу и по коду товара.

    Args:
        warehouse: идентификатор склада.
        sku: идентификатор товара, если указан, то дополнительно фильтрует по товару.
    """

    query = select(
        stock_events.c.sku,
        func.sum(case((stock_events.c.operation == "receipt", stock_events.c.qty), else_=-stock_events.c.qty)).label("qty"),
    ).where(
        stock_events.c.warehouse == warehouse
    )

    if sku is not None:
        query = query.where(stock_events.c.sku == sku)

    return query.group_by(stock_events.c.sku)


async def get_balance_rows(conn: AsyncConnection, warehouse: str, sku: str | None = None) -> list:
    """Выполняет запрос остатков и возвращает его результат.

    Args:
        conn: подключение к БД.
        warehouse: идентификатор склада.
        sku: идентификатор товара

    Returns:
        Список строк-маппингов (sku, qty).
    """

    return (await conn.execute(get_balance_rows_query(warehouse, sku))).mappings().all()


async def get_balance(conn: AsyncConnection, warehouse: str, sku: str | None = None) -> int:
    """Возвращает суммарный остаток по складу и товару.

    Args:
        conn: подключение к БД.
        warehouse: идентификатор склада.
        sku: идентификатор товара

    Returns:
        Итоговый остаток (может быть 0, если данных нет).
    """

    rows = await get_balance_rows(conn, warehouse, sku)
    if not rows:
        return 0
    
    return sum(row["qty"] or 0 for row in rows)


async def get_warehouses(conn: AsyncConnection) -> list[dict]:
    """Возвращает сводку по каждому складу.

    Args:
        conn: подключение к БД.

    Returns:
        Список словарей (warehouse, total_qty, sku_count) по каждому складу.
    """

    query = select(
        stock_events.c.warehouse,
        func.sum(case((stock_events.c.operation == "receipt", stock_events.c.qty), else_=-stock_events.c.qty)).label("total_qty"),
        func.count(func.distinct(stock_events.c.sku)).label("sku_count"),
    ).group_by(
        stock_events.c.warehouse
    ).order_by(
        stock_events.c.warehouse
    )

    rows = (await conn.execute(query)).mappings().all()
    
    return [
        {
            "warehouse": row["warehouse"],
            "total_qty": row["total_qty"] or 0,
            "sku_count": row["sku_count"] or 0,
        }
        for row in rows
    ]


async def get_top_skus(conn: AsyncConnection, top_n: int, show_wh: bool = False) -> list[dict]:
    """Возвращает топ товаров по суммарному остатку.

    Args:
        conn: подключение к БД.
        top_n: количество возвращаемых товаров.
        show_wh: если True — добавляет расшифровку по складам с остатком > 0.

    Returns:
        Список словарей (sku, total_qty, [warehouses]).
    """

    balance = case((stock_events.c.operation == "receipt", stock_events.c.qty), else_=-stock_events.c.qty)
    top_query = (
        select(
            stock_events.c.sku,
            func.sum(balance).label("total_qty")
        ).group_by(
            stock_events.c.sku
        ).order_by(
            func.sum(balance).desc(), 
            stock_events.c.sku
        ).limit(top_n)
    )
    rows = (await conn.execute(top_query)).mappings().all()

    result = [
        {"sku": row["sku"], "total_qty": row["total_qty"] or 0}
        for row in rows
    ]
    if not show_wh:
        return result

    skus = [row["sku"] for row in rows]
    if not skus:
        return result

    per_wh_query = (
        select(
            stock_events.c.sku,
            stock_events.c.warehouse,
            func.sum(balance).label("qty"),
        )
        .where(stock_events.c.sku.in_(skus))
        .group_by(stock_events.c.sku, stock_events.c.warehouse)
        .having(func.sum(balance) > 0)
        .order_by(stock_events.c.sku, func.sum(balance).desc(), stock_events.c.warehouse)
    )
    per_wh_rows = (await conn.execute(per_wh_query)).mappings().all()

    by_sku = defaultdict(list)
    for row in per_wh_rows:
        by_sku[row["sku"]].append({"warehouse": row["warehouse"], "qty": row["qty"]})

    for item in result:
        item["warehouses"] = by_sku.get(item["sku"], [])

    return result