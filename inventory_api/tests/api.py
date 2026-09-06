
async def receipt(client, sku, qty, warehouse):
    """Отправляет запрос на создание прихода.

    Args:
        client: aiohttp-клиент.
        sku: идентификатор товара.
        qty: количество.
        warehouse: идентификатор склада.

    Returns:
        Объект ответа на POST /receipts.
    """

    return await client.post(
        "/receipts",
        json={"sku": sku, "qty": qty, "warehouse": warehouse},
    )


async def issue(client, sku, qty, warehouse):
    """Отправляет запрос на создание расхода.

    Args:
        client: aiohttp-клиент.
        sku: идентификатор товара.
        qty: количество.
        warehouse: идентификатор склада.

    Returns:
        Объект ответа на POST /issues.
    """

    return await client.post(
        "/issues",
        json={"sku": sku, "qty": qty, "warehouse": warehouse},
    )