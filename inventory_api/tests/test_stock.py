from api import issue, receipt


async def test_stock_by_sku(client, clean_tables):
    """Тестирует остаток конкретного товара на складе.
       Сценарий:
        Приход 5 - приход 3 - расход 2, ожидается остаток - 6
    """

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    assert (await receipt(client, "SKU-1", 3, "WH-A")).status == 201
    assert (await issue(client, "SKU-1", 2, "WH-A")).status == 201

    response = await client.get("/stock?warehouse=WH-A&sku=SKU-1")
    assert response.status == 200

    body = await response.json()
    assert body == {"warehouse": "WH-A", "sku": "SKU-1", "qty": 6}


async def test_stock_all_skus(client, clean_tables):
    """Тестирует остатки всех товаров склада.
       Сценарий:
        Приход sku-1 5 - расход sku-1 1 - приход sku-2 4. 
        Ожидается остаток sku-1 - 4, sku-2 - 4.
    """

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    assert (await issue(client, "SKU-1", 1, "WH-A")).status == 201
    assert (await receipt(client, "SKU-2", 4, "WH-A")).status == 201

    response = await client.get("/stock?warehouse=WH-A")
    assert response.status == 200

    body = await response.json()
    assert body["warehouse"] == "WH-A"

    skus = {item["sku"]: item["qty"] for item in body["skus"]}
    assert skus == {"SKU-1": 4, "SKU-2": 4}


async def test_stock_zero_balance(client, clean_tables):
    """Тестирует нулевой остаток при полном списании товара.
       Сценарий:
        Приход 5 - расход 5. Ожидается остаток 0.
    """

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    assert (await issue(client, "SKU-1", 5, "WH-A")).status == 201

    response = await client.get("/stock?warehouse=WH-A&sku=SKU-1")
    assert response.status == 200

    body = await response.json()
    assert body == {"warehouse": "WH-A", "sku": "SKU-1", "qty": 0}


async def test_stock_not_found_warehouse(client, clean_tables):
    """Тестирует ответ 404 для несуществующего склада."""

    response = await client.get("/stock?warehouse=NULL")
    assert response.status == 404


async def test_stock_not_found_sku(client, clean_tables):
    """Тестирует ответ 404 для несуществующего товара на складе."""

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201

    response = await client.get("/stock?warehouse=WH-A&sku=NULL")
    assert response.status == 404


async def test_stock_missing_warehouse(client):
    """Тестирует ответ 400 при отсутствующем параметре warehouse."""

    response = await client.get("/stock?sku=SKU-1")
    assert response.status == 400


async def test_stock_blank_warehouse(client):
    """Тестирует ответ 400 при пустом значении warehouse."""

    response = await client.get("/stock?warehouse=   ")
    assert response.status == 400


async def test_stock_keeps_other_warehouses_isolated(client, clean_tables):
    """Тестирует отображение по разным складам.
       Сценарий:
        Приход sku-1 (wh-a) 5, приход sku-1 (wh-b) 9. 
        Ожидается, что по складу wh-b (sku-1) остаток - 9
    """

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    assert (await receipt(client, "SKU-1", 9, "WH-B")).status == 201

    response = await client.get("/stock?warehouse=WH-B&sku=SKU-1")

    assert response.status == 200
    assert (await response.json())["qty"] == 9