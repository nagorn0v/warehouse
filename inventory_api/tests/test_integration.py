from api import issue, receipt
from inventory_api.enum import StockStream
from inventory_api.outbox import OutboxPublisher


async def test_full_flow(client, engine, redis, app, clean_tables):
    """Проверяет полный путь: приход -> outbox -> Redis стрим."""

    response = await receipt(client, "SKU-FULL", 7, "WH-F")
    assert response.status == 201
    body = await response.json()

    publisher = OutboxPublisher(
        engine, redis, poll_interval=1.0, batch_size=100
    )
    await publisher.run_once()

    entries = await redis.xrange(StockStream.receipt.value)
    assert len(entries) == 1
    _, fields = entries[0]
    assert fields["stock_event_id"] == str(body["id"])
    assert fields["sku"] == "SKU-FULL"
    assert fields["qty"] == "7"
    assert fields["warehouse"] == "WH-F"
    assert fields["operation"] == "receipt"


async def test_issue_flow(client, engine, redis, app, clean_tables):
    """Проверяет полный путь: приход+расход -> outbox -> Redis стримы."""

    receipt_resp = await receipt(client, "SKU-ISSUE", 3, "WH-I")
    assert receipt_resp.status == 201

    response = await issue(client, "SKU-ISSUE", 3, "WH-I")
    assert response.status == 201
    body = await response.json()
    assert body["sku"] == "SKU-ISSUE"

    publisher = OutboxPublisher(
        engine, redis, poll_interval=1.0, batch_size=100
    )
    await publisher.run_once()

    entries = await redis.xrange(StockStream.issue.value)
    assert len(entries) == 1
    _, fields = entries[0]
    assert fields["stock_event_id"] == str(body["id"])
    assert fields["operation"] == "issue"

    assert len(await redis.xrange(StockStream.receipt.value)) == 1