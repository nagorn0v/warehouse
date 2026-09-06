from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса, читаются из env.

    Attributes:
        database_url: URL подключения к БД
        redis_url: URL подключения к Redis
        outbox_poll_interval: интервал опроса outbox-таблицы, сек.
        outbox_batch_size: размер батча публикации событий из outbox.
        host: адрес HTTP-сервера.
        port: порт HTTP-сервера.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    redis_url: str
    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 100
    host: str = "0.0.0.0"
    port: int = 8080


def get_settings() -> Settings:
    """Возвращает настройки сервиса."""

    return Settings()