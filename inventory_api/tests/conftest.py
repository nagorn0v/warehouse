import os

import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from inventory_api.config import Settings
from inventory_api.db import metadata
from inventory_api.main import get_app

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
TEST_REDIS_URL = os.environ["TEST_REDIS_URL"]


def _admin_url() -> str:
    """Возвращает URL для подключения к бд по-умолчанию."""

    return TEST_DATABASE_URL.replace("/inventory_test", "/postgres")


async def _create_test_db() -> None:
    """Создаёт тестовую базу inventory_test, если она еще не создана."""

    engine = create_async_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'inventory_test'")
        )
        if exists.scalar() is None:
            await conn.execute(text("CREATE DATABASE inventory_test"))

    await engine.dispose()


@pytest_asyncio.fixture
async def engine():
    """Создаёт и возвращает движок sqlalchemy с чистой схемой тестовой БД."""

    await _create_test_db()
    engine = create_async_engine(TEST_DATABASE_URL)

    # setup чистим перед тестом
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)

    yield engine

    # teardown закрываем соединение
    await engine.dispose()


@pytest_asyncio.fixture
async def redis():
    """Создаёт клиент redis с очищенной базой."""

    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)

    # setup чистим перед тестом
    await client.flushdb()

    yield client

    # teardown закрываем соединение
    await client.aclose()


@pytest_asyncio.fixture
async def app(engine, redis):
    """Создает и возвращает aiohttp-приложение без outbox-публикатора."""

    settings = Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
    )
    application = get_app(settings=settings, engine=engine, redis_client=redis, start_publisher=False)

    return application


@pytest_asyncio.fixture
async def client(app, aiohttp_client):
    """Создаёт и возвращет aiohttp-тест-клиент для приложения."""

    return await aiohttp_client(app)


@pytest_asyncio.fixture
async def clean_tables(engine):
    """Очищает таблицы outbox и stock_events до и после теста."""

    # setup чистим перед тестом
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE outbox, stock_events RESTART IDENTITY CASCADE"))

    yield

    # teardown чистим после теста
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE outbox, stock_events RESTART IDENTITY CASCADE"))