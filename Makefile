SHELL := /bin/bash

PROJECT_NAME := cygnet-full
TEST_PROJECT_NAME := cygnet-test
ENV_FILE := .env.docker
COMPOSE := docker compose -p $(PROJECT_NAME) --env-file $(ENV_FILE) -f docker-compose.yml
TEST_COMPOSE := docker compose -p $(TEST_PROJECT_NAME) --env-file $(ENV_FILE) -f docker-compose.test.yml

.PHONY: start stop restart status logs migrate env start-local stop-local up down build backend frontend streamlit test test-compose backend-test frontend-test streamlit-test smoke ingest-de ingest-fr

start:
	./scripts/start_docker.sh

stop:
	./scripts/stop_docker.sh

restart: stop start

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=120

migrate:
	$(COMPOSE) exec -T api poetry run alembic upgrade head

env:
	python3 scripts/setup_env.py

start-local:
	./start_local.sh

stop-local:
	./stop_local.sh --stop-db

up:
	$(COMPOSE) up -d postgres api frontend app

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build api frontend app

backend:
	$(COMPOSE) up api

frontend:
	$(COMPOSE) up frontend

streamlit:
	$(COMPOSE) up app

test: backend-test frontend-test streamlit-test

test-compose:
	@set -euo pipefail; \
	trap '$(TEST_COMPOSE) down -v' EXIT; \
	$(TEST_COMPOSE) up -d --build postgres api; \
	$(TEST_COMPOSE) run --rm pytest; \
	$(TEST_COMPOSE) run --rm frontend-test; \
	$(TEST_COMPOSE) run --rm streamlit-test

smoke:
	./scripts/stack_smoke.sh

backend-test:
	poetry run pytest -v tests

frontend-test:
	cd frontend && npm run test:run

streamlit-test:
	poetry run pytest -v tests/streamlit

ingest-de:
	curl -X POST http://127.0.0.1:8001/api/ingest/generation \
	  -H "Content-Type: application/json" \
	  -d '{"zone":"DE","start":"2025-12-01T00:00:00","end":"2025-12-31T23:00:00"}'

ingest-fr:
	curl -X POST http://127.0.0.1:8001/api/ingest/generation \
	  -H "Content-Type: application/json" \
	  -d '{"zone":"FR","start":"2025-11-01T00:00:00","end":"2025-11-30T23:00:00"}'
