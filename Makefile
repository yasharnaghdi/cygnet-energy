SHELL := /bin/bash

.PHONY: start stop restart status logs migrate start-local stop-local

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
