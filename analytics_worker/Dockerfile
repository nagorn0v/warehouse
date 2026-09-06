# Базовый лёгкий образ Python (>= 3.10) на Alpine
FROM python:3.12-alpine AS runtime

# Оптимизация рантайма: без __pycache__, буферизованный вывод, без проверок pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Билд-стадия: здесь ставятся нативные зависимости и пакеты
FROM runtime AS builder

# Компиляторы для сборки asyncpg (нативные модули); в runtime не попадают
RUN apk add --no-cache gcc musl-dev postgresql-dev

COPY requirements.txt .

# Установка зависимостей в отдельный префикс /opt/deps
RUN pip install --prefix=/opt/deps -r requirements.txt

# Финальная стадия: чистый runtime сборочный слой
FROM runtime

# Копируем установленные пакеты из билд-стадии
COPY --from=builder /opt/deps /usr/local

# Скрипт ожидания сервисов и запуска миграций
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

# Исходный код воркера устанавливается из wheel (см. pyproject.toml + dist/*.whl)
COPY dist/*.whl /tmp/

# Устанавливаем пакет из wheel; зависимости уже в /usr/local из билд-стадии, поэтому --no-deps
RUN pip install --no-deps /tmp/*.whl

# Конфигурация и миграции Alembic (entrypoint: alembic upgrade head)
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

WORKDIR /app

# HTTP-порт health-эндпоинта
EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]

# Точка входа воркера: health-сервер + Redis Streams consumer (asyncio-задача)
CMD ["analytics-worker"]