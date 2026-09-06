
async def test_health(client):
    """Тестирование health-check сервиса."""

    response = await client.get("/health")
    assert response.status == 200

    body = await response.json()
    
    assert body == {"status": "ok"}