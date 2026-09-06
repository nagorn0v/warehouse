# Warehouse

Двухсервисная система учёта склада:

- **`inventory_api`** (`:8080`) — REST API. Прихода/расходы записываются в `postgres-inventory`, событие публикуется в Redis Streams (`outbox`).
- **`analytics_worker`** (`:8081`) — читает Redis Streams, валидирует, дедуплицирует и агрегирует остатки в `stock_agg` в `postgres-analytics`.

## Документация

Схемы архитектуры (открываются в [draw.io](https://app.diagrams.net/)):

- [C4 — контекст системы](docs/diagrams/c4-context.drawio) — сервисы, хранилища и междусервисные потоки.
- [Sequence-диаграмма](docs/diagrams/sequence.drawio) — жизненный цикл события прихода/расхода: API → outbox → Redis Streams → агрегат.

## Предварительные требования

Проект можно запустить двумя способами — в Docker или локально.

**Вариант A (Docker - проритетный вариант):**
- Docker + Docker Compose.

**Вариант B (локально, venv):**
- Python 3.12 и пакет для `venv` (python3.12-venv).
- Запущенные локально Postgres (`localhost:5432`) и Redis (`localhost:6379`).
- Утилита `createdb` (или `psql`) для создания БД.

## Вариант A. Запуск в Docker (с нуля)

```bash
# 1. Конфигурация окружения (compose читает переменные из .env)
cp .env.example .env
# при необходимости отредактируйте значения — см. «Переменные окружения»;
# дефолты из .env.example работают «из коробки»

# 2. Сборка wheel обоих сервисов.
#    Обязательно: Dockerfile ставит пакеты из dist/*.whl, а dist/ в .gitignore,
#    поэтому при клонировании проекта без этого шага сборка упадёт.
#    также, необходимо каждый раз пересобирать whl, чтоб подтянулись новые изменения в сервисах
make build          # оба сервиса
# по отдельности:
make build-inventory
make build-analytics

# 3. Поднятие стека: две Postgres, Redis и оба сервиса
docker compose up -d --build
```

Миграции применяются автоматически: `entrypoint.sh` в каждом контейнере ждёт
готовности БД/Redis и выполняет `alembic upgrade head`.

Проверить, что всё работает:

```bash
docker compose ps | awk '{print $1}'
# ожидаемый результат: postgres-inventory, postgres-analytics, redis, inventory-api, analytics-worker — все healthy
```

Готовность API-сервисов:

```bash
curl -s http://127.0.0.1:8080/health   # inventory_api
curl -s http://127.0.0.1:8081/health   # analytics_worker
```

Оба должны вернуть `{"status": "ok"}`.

### Пересборка после правок кода

Код каждого сервиса упакован в wheel (см. `pyproject.toml`, `src/`-layout), поэтому
сначала пересоберите wheel, затем образ и контейнер:

```bash
make build-inventory && docker compose build inventory_api && docker compose up -d --force-recreate inventory_api
make build-analytics && docker compose build analytics_worker && docker compose up -d --force-recreate analytics_worker
```

## Вариант B. Запуск локально без Docker (с нуля)

```bash
# Требования: Python 3.12 (+ python3.12-venv), запущены Postgres (:5432) и Redis (:6379).
# Создайте БД (в примере — суперпользователь postgres; подставьте свои креды):
createdb -U postgres inventory
createdb -U postgres analytics
# или через psql: CREATE DATABASE inventory; CREATE DATABASE analytics;
```

```bash
# 1. venv и установка каждого сервиса (editable)
python3.12 -m venv inventory_api/.venv
inventory_api/.venv/bin/pip install -e ./inventory_api

python3.12 -m venv analytics_worker/.venv
analytics_worker/.venv/bin/pip install -e ./analytics_worker
```

```bash
# 2. Миграции. Обязательно из каталога сервиса (лежит alembic.ini);
#    строка подключения берётся из переменной DATABASE_URL.
cd inventory_api
DATABASE_URL=postgresql+asyncpg://inventory:inventory_pass@localhost:5432/inventory \
  .venv/bin/alembic upgrade head
cd ../analytics_worker
DATABASE_URL=postgresql+asyncpg://analytics:analytics_pass@localhost:5432/analytics \
  .venv/bin/alembic upgrade head
cd ..
```

```bash
# 3. Запуск inventory_api — отдельный терминал (:8080)
export DATABASE_URL=postgresql+asyncpg://inventory:inventory_pass@localhost:5432/inventory
export REDIS_URL=redis://localhost:6379/0
inventory_api/.venv/bin/inventory-server
# альтернатива: inventory_api/.venv/bin/python -m inventory_api.main
```

```bash
# 4. Запуск analytics_worker — отдельный терминал.
#    ВАЖНО: PORT=8081, иначе оба сервиса упрутся в дефолтный 8080.
export DATABASE_URL=postgresql+asyncpg://analytics:analytics_pass@localhost:5432/analytics
export REDIS_URL=redis://localhost:6379/0
export CONSUMER_GROUP=analytics
export CONSUMER_NAME=analytics-worker
export BATCH_SIZE=32
export BLOCK_MS=5000
export PORT=8081
analytics_worker/.venv/bin/analytics-worker
# альтернатива: analytics_worker/.venv/bin/python -m analytics_worker.worker
```

## Переменные окружения

| Переменная | Сервис | Обязательная | Docker (значение из `.env`) | Локально (venv) |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | оба | да | compose собирает из `*_DB_*` + имени сервиса (`postgres-inventory`/`postgres-analytics`) | `postgresql+asyncpg://<user>:<pass>@localhost:5432/inventory` (для analytics — БД `analytics`) |
| `REDIS_URL` | оба | да | `redis://redis:6379/0` (из `.env`) | `redis://localhost:6379/0` |
| `CONSUMER_GROUP` | analytics_worker | да | из `.env` | `analytics` |
| `CONSUMER_NAME` | analytics_worker | да | из `.env` | `analytics-worker` |
| `BATCH_SIZE` | analytics_worker | да | из `.env` | `32` |
| `BLOCK_MS` | analytics_worker | да | из `.env` | `5000` |
| `OUTBOX_POLL_INTERVAL` | inventory_api | нет (1.0) | — | — |
| `OUTBOX_BATCH_SIZE` | inventory_api | нет (100) | — | — |
| `PORT` | оба | нет (8080) | проброс портов в compose | `8081` для analytics_worker |
| `HOST` | оба | нет (0.0.0.0) | — | — |
| `DEBUG` | оба | нет | — | — |

`.env` в корне репозитория нужен только Docker-стеку (compose читает его
автоматически);

## Карта портов

| Что | Локально (venv) | Docker (проброс) | Назначение |
| --- | --- | --- | --- |
| `inventory_api` | `8080` | `8080` | REST API (приём, чтение source) |
| `analytics_worker` | `8081` (через `PORT`) | `8081` | проверка чтения из redis `stock_agg` |
| `postgres-inventory` | `5432` | `55432` | бд inventory |
| `postgres-analytics` | `5432` | `55433` | кэш-данные (analytics) |
| `redis` | `6379` | `56379` | Redis Streams |

## Запросы

Документация сервисов (Swagger UI) доступна на `/docs` в каждом сервисе:

- inventory_api — `http://127.0.0.1:8080/docs`
- analytics_worker — `http://127.0.0.1:8081/docs`

## Dev-среда (debug)

Отладочная среда: те же сервисы, но собраны из `Dockerfile.dev` (есть `debugpy`),
переменная `DEBUG`, проброшены debugpy-порты и смонтирован `alembic/` на хост
(созданные ревизии сохраняются в репо).

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Поднять dev-среду можно и через Makefile:

```bash
make dev
```

Отладка в VS Code: два Dev-профиля в `.vscode/launch.json` (5678/5679),
подключение через Debug: `Dev inventory_api (5678)` / `Dev analytics_worker (5679)`.
Миграции внутри dev-контейнера:

```bash
docker exec -it warehouse-inventory-api alembic revision --autogenerate -m "описание"
docker exec -it warehouse-inventory-api alembic upgrade head
```

## Тесты

### В Docker (изолированные контейнеры pytest)

```bash
make test-inventory    # inventory_api docker compose -f docker-compose.tests.yml --profile tests run --rm inventory_api_tests
make test-analytics    # analytics_worker docker compose -f docker-compose.tests.yml --profile tests run --rm analytics_worker_tests
make test              # оба
```

Один конкретный тест:

```bash
docker compose -f docker-compose.tests.yml --profile tests run --rm \
  inventory_api_tests pytest tests/test_summary.py::test_summary_show_wh_case_insensitive

# все тесты файла
docker compose -f docker-compose.tests.yml --profile tests run --rm \
  inventory_api_tests pytest tests/test_summary.py

# по ключевому слову
docker compose -f docker-compose.tests.yml --profile tests run --rm \
  inventory_api_tests pytest -k "show_wh"
```

`src/` и `tests/` смонтированы в контейнер (volume) — правки кода и тестов
подхватываются без пересборки образа. Перед первым запуском тестовых образов
нужно собрать wheel (`make build-inventory` / `make build-analytics`).

### Локально в venv (БД и Redis в Docker)

```bash
docker compose -f docker-compose.infra.yml up -d   # PG/Redis на портах 55432/55433/56379
make test-local                                    # создает .venv и прогоняет тесты обоих сервисов
```
Требуется `python3.12-venv`.

## Остановка

```bash
docker compose down
# с удалением данных обеих БД:
docker compose down -v
```
