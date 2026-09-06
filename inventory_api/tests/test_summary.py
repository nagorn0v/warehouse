from api import issue, receipt


async def test_summary_basic(client, clean_tables):
    """Тестирует сводку остатков по складам."""

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    assert (await issue(client, "SKU-1", 2, "WH-A")).status == 201
    assert (await receipt(client, "SKU-2", 4, "WH-A")).status == 201
    assert (await receipt(client, "SKU-1", 9, "WH-B")).status == 201

    response = await client.get("/stock/summary")
    assert response.status == 200
    body = await response.json()

    warehouses = {w["warehouse"]: w for w in body["warehouses"]}

    assert warehouses["WH-A"]["total_qty"] == 7 # 5 - 2 + 4
    assert warehouses["WH-A"]["sku_count"] == 2
    assert warehouses["WH-B"]["total_qty"] == 9
    assert warehouses["WH-B"]["sku_count"] == 1


async def test_summary_top_skus_order_and_default(client, clean_tables):
    """Тестирует топ по умолчанию (5 товаров) и сортировку по остатку."""

    assert (await receipt(client, "SKU-1", 10, "WH-A")).status == 201
    assert (await receipt(client, "SKU-2", 3, "WH-A")).status == 201
    assert (await receipt(client, "SKU-3", 8, "WH-A")).status == 201
    assert (await receipt(client, "SKU-4", 1, "WH-A")).status == 201
    assert (await receipt(client, "SKU-5", 5, "WH-A")).status == 201
    assert (await receipt(client, "SKU-6", 2, "WH-A")).status == 201

    response = await client.get("/stock/summary")
    body = await response.json()

    assert len(body["top_skus"]) == 5
    assert body["top_skus"][0]["sku"] == "SKU-1"
    assert body["top_skus"][0]["total_qty"] == 10


async def test_summary_top_n(client, clean_tables):
    """Тестирует, что параметр top_n ограничивает размер топа."""

    assert (await receipt(client, "SKU-1", 10, "WH-A")).status == 201
    assert (await receipt(client, "SKU-2", 7, "WH-A")).status == 201

    response = await client.get("/stock/summary?top_n=1")
    assert response.status == 200

    body = await response.json()
    assert len(body["top_skus"]) == 1
    assert body["top_skus"][0] == {"sku": "SKU-1", "total_qty": 10}


async def test_summary_invalid_top_n(client):
    """Тестирует ответ 400 при невалидном значении top_n."""

    for value in ["0", "-1", "abc"]:
        response = await client.get(f"/stock/summary?top_n={value}")
        assert response.status == 400, value


async def test_summary_empty_db(client):
    """Тестирует пустую сводку при отсутствии данных."""

    response = await client.get("/stock/summary")
    assert response.status == 200
    assert await response.json() == {"warehouses": [], "top_skus": []}


async def test_summary_show_wh_false_and_absent(client, clean_tables):
    """Тестирует, что без show_wh расшифровка по складам не выводится."""

    assert (await receipt(client, "SKU-1", 10, "WH-A")).status == 201

    for params in ["", "show_wh=false"]:
        response = await client.get(f"/stock/summary?{params}")
        assert response.status == 200
        body = await response.json()
        assert body["top_skus"][0] == {"sku": "SKU-1", "total_qty": 10}
        assert "warehouses" not in body["top_skus"][0]


async def test_summary_show_wh_true(client, clean_tables):
    """Тестирует расшифровку top-товаров по складам при show_wh=true."""

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    assert (await issue(client, "SKU-1", 2, "WH-A")).status == 201  # 3 в WH-A
    assert (await receipt(client, "SKU-1", 9, "WH-B")).status == 201
    assert (await receipt(client, "SKU-2", 4, "WH-A")).status == 201

    response = await client.get("/stock/summary?show_wh=true")
    assert response.status == 200

    body = await response.json()
    by_sku = {item["sku"]: item for item in body["top_skus"]}
    assert "warehouses" in by_sku["SKU-1"]

    wh = {w["warehouse"]: w["qty"] for w in by_sku["SKU-1"]["warehouses"]}
    assert wh == {"WH-A": 3, "WH-B": 9}
    assert by_sku["SKU-2"]["warehouses"] == [{"warehouse": "WH-A", "qty": 4}]


async def test_summary_show_wh_zero_warehouse_excluded(client, clean_tables):
    """Тестирует исключение складов с нулевым остатком из расшифровки."""

    assert (await receipt(client, "SKU-1", 5, "WH-A")).status == 201
    # приход на WH-B и полный расчёт списывает в ноль
    assert (await receipt(client, "SKU-1", 3, "WH-B")).status == 201
    assert (await issue(client, "SKU-1", 3, "WH-B")).status == 201

    response = await client.get("/stock/summary?show_wh=true")
    assert response.status == 200
    body = await response.json()

    sku1 = next(item for item in body["top_skus"] if item["sku"] == "SKU-1")
    warehouses = [w["warehouse"] for w in sku1["warehouses"]]
    assert warehouses == ["WH-A"]  # WH-B обнулился и исключён


async def test_summary_show_wh_invalid(client):
    """Тестирует ответ 400 при невалидном значении show_wh."""

    for value in ["abc", "1", "0", "yes", "on"]:
        response = await client.get(f"/stock/summary?show_wh={value}")
        assert response.status == 400, value
        