from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from analytics_worker.db import stock_agg


async def get_balance_rows(conn: AsyncConnection, warehouse: str, sku: str | None = None) -> list:
    """Возвращает текущие остатки по складу и единице товара.
    
    Args:
        conn: соединение с бд.
        warehouse: идентификатор склада.
        sku: идентификатор товара.
    """

    balance_q = (
        select(stock_agg.c.warehouse, stock_agg.c.sku, stock_agg.c.qty)
        .where(stock_agg.c.warehouse == warehouse)
        .order_by(stock_agg.c.sku)
    )
    
    if sku is not None:
        balance_q = balance_q.where(stock_agg.c.sku == sku)
        
    return (await conn.execute(balance_q)).mappings().all()