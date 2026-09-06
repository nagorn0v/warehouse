
async def test_health(client):
    """Проверяет эндпоинт health."""

    response = await client.get("/health")
    assert response.status == 200
    
    body = await response.json()
    assert body == {"status": "ok"}