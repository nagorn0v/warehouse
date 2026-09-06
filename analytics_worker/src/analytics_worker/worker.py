import asyncio
import logging
import os

from aiohttp import web
from redis.asyncio import Redis

from analytics_worker.config import get_settings
from analytics_worker.consumer import AnalyticsConsumer
from analytics_worker.db import create_engine
from analytics_worker.main import create_app

logger = logging.getLogger(__name__)


def _start_debug() -> None:
    """Добавляет дебаггер (debugpy)."""

    import debugpy

    debugpy.listen(("0.0.0.0", 5678))


async def run() -> None:
    """Запускает worker-консьюмера из стримов redis, api-server
       Консьюмер слушает 2 стрима: на приход товара и на расход товара - обновляет текущий остаток.
    """

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if os.getenv("DEBUG", "").lower() == "true":
        _start_debug()

    settings = get_settings()
    engine = create_engine(settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    consumer = AnalyticsConsumer(engine, redis, settings)
    consumer_task = asyncio.create_task(consumer.run())

    def _on_consumer_done(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("consumer task terminated unexpectedly")

    consumer_task.add_done_callback(_on_consumer_done)

    app = create_app(engine)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.host, settings.port)
    await site.start()

    try:
        while True:
            await asyncio.sleep(3600)

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    finally:
        consumer.stop()
        consumer_task.cancel()

        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

        await redis.aclose()
        await engine.dispose()
        await runner.cleanup()


def main() -> None:
    """Синхронная точка входа (для console-script и python -m)."""
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
