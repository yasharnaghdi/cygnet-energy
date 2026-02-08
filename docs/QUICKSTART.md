# Quickstart

## Prerequisites
- Docker Engine with Compose v2
- Python 3.11 and Poetry
- Copy `.env.example` to `.env` and set required placeholders for local use

## Local Development (baseline stack)
```bash
cp .env.example .env
docker compose up --build -d
poetry install
python scripts/smoke_check.py
```

## Smoke Check Command
```bash
python scripts/smoke_check.py
```

## Expected Healthy Output
- `Ingestion check OK: ... generation columns`
- `Model execution check OK`
- `App boot check OK (py_compile)`
- `All smoke checks passed.`
- `docker compose ps` shows `postgres` and `app` in running/healthy state
