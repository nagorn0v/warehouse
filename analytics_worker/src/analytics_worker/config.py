from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Класс настроек сервиса."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str

    # redis
    redis_url: str
    consumer_group: str
    consumer_name: str
    # Количество забираемых событий из стрима
    batch_size: int
    # Время блокирующего ожидания новых событий
    block_ms: int

    # Хост/порт api-сервера по-умолчанию
    host: str = "0.0.0.0"
    port: int = 8080


def get_settings() -> Settings:
    """Возвращает настройки сервиса."""

    return Settings()