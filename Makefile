SHELL := /bin/bash

.PHONY: start stop restart status logs migrate start-local stop-local up down build backend frontend streamlit test backend-test frontend-test streamlit-test

start:
	./scripts/start_docker.sh

stop:
	./scripts/stop_docker.sh

restart: stop start

status:
	docker compose -p cygnet-full --env-file .env.docker -f docker-compose.yml ps

logs:
	docker compose -p cygnet-full --env-file .env.docker -f docker-compose.yml logs -f --tail=120

migrate:
	docker compose -p cygnet-full --env-file .env.docker -f docker-compose.yml exec -T api poetry run alembic upgrade head

start-local:
	./start_local.sh

stop-local:
	./stop_local.sh --stop-db

up:
	docker compose up -d postgres api frontend app

down:
	docker compose down

build:
	docker compose build api frontend app

backend:
	docker compose up api

frontend:
	docker compose up frontend

streamlit:
	docker compose up app

test: backend-test frontend-test streamlit-test

backend-test:
	poetry run pytest -v tests

frontend-test:
	cd frontend && npm run test:run

streamlit-test:
	poetry run pytest -v tests/streamlit
