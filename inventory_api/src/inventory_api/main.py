import asyncio
import logging
import os
import pathlib

from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo, SwaggerUiSettings
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from inventory_api.config import Settings, get_settings
from inventory_api.db import get_engine
from inventory_api.outbox import OutboxPublisher
from inventory_api.routes import setup_routes

logger = logging.getLogger(__name__)
_COMPONENTS_PATH = str(pathlib.Path(__file__).resolve().parent / "components.yaml")


def get_app(
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    redis_client: Redis | None = None,
    start_publisher: bool = True,
) -> web.Application:
    """Создает и возвращает сервис.

    Args:
        settings: настройки сервиса
        engine: асинхронный движок
        redis_client: клиент Redis
        start_publisher: признак необходимости запуска outbox-публикатора.

    Returns:
        Собранный web.Application.
    """

    settings = settings or get_settings()
    app = web.Application()

    app["settings"] = settings
    app["engine"] = engine or get_engine(settings)
    app["redis"] = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)

    # swagger-документация
    swagger = SwaggerDocs(
        app,
        validate=False,
        info=SwaggerInfo(title="Inventory API", version="1.0.0", description="REST API прихода, расхода и остатков"),
        components=_COMPONENTS_PATH,
        swagger_ui_settings=SwaggerUiSettings(path="/docs"),
    )
    setup_routes(app, swagger)

    if start_publisher:
        publisher = OutboxPublisher(
            app["engine"],
            app["redis"],
            poll_interval=settings.outbox_poll_interval,
            batch_size=settings.outbox_batch_size,
        )
        app["publisher"] = publisher
        app.on_startup.append(_start_publisher)
        app.on_shutdown.append(_stop_publisher)

    app.on_shutdown.append(_close_resources)

    return app


async def _start_publisher(app: web.Application) -> None:
    """Запускает задачу outbox-публикатора.

    Args:
        app: aiohttp-приложение.
    """

    app["publisher_task"] = asyncio.create_task(app["publisher"].run())


async def _stop_publisher(app: web.Application) -> None:
    """Останавливает outbox-публикатор.

    Args:
        app: aiohttp-приложение.
    """

    publisher = app.get("publisher")
    if publisher is None:
        return
    
    publisher.stop()

    task = app.get("publisher_task")
    if task is not None:
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


async def _close_resources(app: web.Application) -> None:
    """Закрывает движок БД и клиент Redis.

    Args:
        app: aiohttp-приложение.
    """

    await app["engine"].dispose()
    await app["redis"].aclose()


def main() -> None:
    """Точка входа: настраивает логирование, стартует сервер."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if os.getenv("DEBUG", "").lower() == "true":
        _start_debug()

    settings = get_settings()
    app = get_app(settings)
    web.run_app(app, host=settings.host, port=settings.port)


def _start_debug() -> None:
    """Включает debugpy-сервер на порту 5678."""

    import debugpy

    debugpy.listen(("0.0.0.0", 5678))


if __name__ == "__main__":
    main()