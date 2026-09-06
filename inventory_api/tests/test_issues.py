from sqlalchemy import text

from api import issue, receipt


async def test_create_issue_201(client, engine, clean_tables):
    """Тестирует успешное создание расхода и запись в БД/outbox.
       Сценарий:
        Создаем приход 5, затем расход 3, ожидается, что в outbox будет 2 события.
    """

    resp = await receipt(client, "SKU-1", 5, "WH-A")
    assert resp.status == 201

    response = await issue(client, "SKU-1", 3, "WH-A")
    assert response.status == 201

    body = await response.json()
    assert body["sku"] == "SKU-1"
    assert body["qty"] == 3
    assert body["warehouse"] == "WH-A"
    assert body["id"] > 0
    assert "created_at" in body

    async with engine.connect() as conn:
        issues = (
            await conn.execute(
                text("SELECT * FROM stock_events WHERE operation = 'issue'")
            )
        ).mappings().all()
        assert len(issues) == 1
        assert issues[0]["sku"] == "SKU-1"
        assert issues[0]["warehouse"] == "WH-A"

        outbox_rows = (await conn.execute(text("SELECT * FROM outbox"))).mappings().all()
        assert len(outbox_rows) == 2
        for row in outbox_rows:
            assert row["published_at"] is None


async def test_create_issue_insufficient_stock(client, engine, clean_tables):
    """Тестирует отклонение расхода при недостаточном остатке.
       Сценарий:
        Расход 5 - получаем ошибку, т.к. прихода не было. Приход 2 - расход 5 - получаем ошибку, т.к. расход больше прихода.
        Конечный результат - 2, т.к. расходы не повлияли на приход.
    """

    response = await issue(client, "SKU-1", 5, "WH-A")
    assert response.status == 400

    body = await response.json()
    assert body["detail"] == "insufficient stock"

    await receipt(client, "SKU-1", 2, "WH-A")
    response = await issue(client, "SKU-1", 5, "WH-A")
    assert response.status == 400
    assert (await response.json())["detail"] == "insufficient stock"

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM stock_events"))).mappings().all()
        assert len(rows) == 1
        assert rows[0]["operation"] == "receipt"


async def test_create_issue_validation(client, clean_tables):
    """Тестирует отклонение некорректного запроса расхода."""

    await receipt(client, "SKU-1", 5, "WH-A")
    response = await issue(client, "", 5, "WH-A")
    assert response.status == 400

    response = await issue(client, "SKU-1", 0, "WH-A")
    assert response.status == 400

    response = await client.post(
        "/issues",
        json={"sku": "SKU-1", "qty": 5},
    )
    assert response.status == 400