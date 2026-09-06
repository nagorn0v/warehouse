from sqlalchemy import text

from api import receipt


async def test_create_receipt_201(client, engine, clean_tables):
    """Тестирует успешное создание прихода и запись в БД/outbox.
       Сценарий:
        Создается 1 приход, ожидается, что появятся записи в stock_events, outbox.
    """

    response = await receipt(client, "SKU-1", 5, "WH-A")
    assert response.status == 201

    body = await response.json()
    assert body["sku"] == "SKU-1"
    assert body["qty"] == 5
    assert body["warehouse"] == "WH-A"
    assert body["id"] > 0
    assert "created_at" in body

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM stock_events"))).mappings().all()
        assert len(rows) == 1
        assert rows[0]["sku"] == "SKU-1"
        assert rows[0]["operation"] == "receipt"

        outbox_rows = (await conn.execute(text("SELECT * FROM outbox"))).mappings().all()
        assert len(outbox_rows) == 1
        assert outbox_rows[0]["stock_event_id"] == rows[0]["id"]
        assert outbox_rows[0]["published_at"] is None


async def test_create_receipt_validation(client, clean_tables):
    """Тестирует отклонение невалидного тела прихода."""

    response = await receipt(client, "", 5, "WH-A")
    assert response.status == 400

    response = await receipt(client, "SKU-1", 0, "WH-A")
    assert response.status == 400

    response = await client.post(
        "/receipts",
        json={"sku": "SKU-1", "qty": 5},
    )
    assert response.status == 400