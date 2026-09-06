import os

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from analytics_worker.db import metadata, processed_events, stock_agg
from analytics_worker.main import create_app

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]


def _postgres_default_url() -> str:
    """Возвращает адрес бд по-умолчанию"""

    return TEST_DATABASE_URL.replace("/analytics_test", "/postgres")


async def _create_test_db() -> None:
    """Создает бд для тестов."""

    engine = create_async_engine(_postgres_default_url(), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        exists = await conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'analytics_test'"))
        if exists.scalar() is None:
            await conn.execute(text("CREATE DATABASE analytics_test"))

    await engine.dispose()


@pytest_asyncio.fixture
async def engine():
    """Создает движок для взаимодействия с бд."""

    await _create_test_db()
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def app(engine):
    """Создает api-сервис."""

    application = create_app(engine)
    return application


@pytest_asyncio.fixture
async def client(app, aiohttp_client):
    """Создает клиент для взаимодействия с сервисом."""

    return await aiohttp_client(app)


@pytest_asyncio.fixture
async def clean_tables(engine):
    """Очищает таблицы между тестами."""

    # setup - на случай, если тесты упали до teardown
    async with engine.begin() as conn:
        await conn.execute(stock_agg.delete())
        await conn.execute(processed_events.delete())

    yield

    # teardown - очистка данных после теста
    async with engine.begin() as conn:
        await conn.execute(stock_agg.delete())
        await conn.execute(processed_events.delete())