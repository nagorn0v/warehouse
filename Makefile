.PHONY: up down dev test test-inventory test-analytics build build-inventory build-analytics debug-inventory debug-analytics test-local

TEST ?= tests
DEBUG_PORT ?= 5678

# Stage-среда: инфраструктура + оба сервиса
up:
	docker compose up -d --build

# Остановка
down:
	docker compose down

# Dev-среда: инфраструктура + оба сервиса (Dockerfile.dev, debugpy, alembic mount)
dev:
	docker compose -f docker-compose.dev.yml up -d --build

# Сборка wheel обоих сервисов в их dist/ (перед docker build требуется наличие dist/*.whl)
build:
	$(MAKE) build-inventory
	$(MAKE) build-analytics

# Сборка wheel inventory_api
build-inventory:
	rm -rf inventory_api/build inventory_api/*.egg-info
	pip wheel ./inventory_api --no-deps --no-build-isolation -w inventory_api/dist

# Сборка wheel analytics_worker
build-analytics:
	rm -rf analytics_worker/build analytics_worker/*.egg-info
	pip wheel ./analytics_worker --no-deps --no-build-isolation -w analytics_worker/dist

# Прогнать тесты обоих сервисов
test:
	$(MAKE) test-inventory
	$(MAKE) test-analytics

# Тесты inventory_api
test-inventory:
	docker compose -f docker-compose.tests.yml --profile tests run --rm inventory_api_tests

# Тесты analytics_worker
test-analytics:
	docker compose -f docker-compose.tests.yml --profile tests run --rm analytics_worker_tests

# Тесты inventory_api под отладчиком (debugpy ждёт attach из VSCode)
# Пример: make debug-inventory [TEST=tests/test_outbox.py::test_publish] [DEBUG_PORT=5678]
debug-inventory:
	docker compose -f docker-compose.tests.yml --profile tests run --rm \
		-p $(DEBUG_PORT):5678 \
		inventory_api_tests \
		python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m pytest -v -x $(TEST)

# Тесты analytics_worker под отладчиком (debugpy ждёт attach из VSCode)
# Пример: make debug-analytics [TEST=tests/test_stock.py::test_stock_by_sku] [DEBUG_PORT=5679]
debug-analytics: DEBUG_PORT ?= 5679
debug-analytics:
	docker compose -f docker-compose.tests.yml --profile tests run --rm \
		-p $(DEBUG_PORT):5678 \
		analytics_worker_tests \
		python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m pytest -v -x $(TEST)

# Локальные тесты (venv) против поднятой infra (compose infra): postgres/redis на localhost-портах
test-local:
	docker compose -f docker-compose.infra.yml up -d
	$(MAKE) test-local-inventory
	$(MAKE) test-local-analytics

test-local-inventory:
	set -a; . ./.env; set +a; \
	cd inventory_api && . .venv/bin/activate && \
	pip install -q --no-build-isolation -e . && \
	TEST_DATABASE_URL="postgresql+asyncpg://$${INVENTORY_DB_USER}:$${INVENTORY_DB_PASSWORD}@localhost:55432/inventory_test" \
	TEST_REDIS_URL="redis://localhost:56379/1" \
	pytest -v

test-local-analytics:
	set -a; . ./.env; set +a; \
	cd analytics_worker && . .venv/bin/activate && \
	pip install -q --no-build-isolation -e . && \
	TEST_DATABASE_URL="postgresql+asyncpg://$${ANALYTICS_DB_USER}:$${ANALYTICS_DB_PASSWORD}@localhost:55433/analytics_test" \
	pytest -v
