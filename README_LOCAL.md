# Local Development Setup

This mode keeps PostgreSQL in Docker and runs API + Streamlit directly on your machine.

## Prerequisites

- Docker Desktop running
- Python 3.11+
- Poetry installed
- `.env` populated with a valid `ENTSOE_API_TOKEN`
- Optional: Ollama running locally for local LLM backend

## Quick Start

1. Create local env file:
```bash
cp .env.example .env
```

2. Update required values in `.env`:
- `DATABASE_URL=postgresql://cygnet:cygnet_pass@localhost:5433/energy_db`
- `ENTSOE_API_TOKEN=<your_token>`
- `API_TOKEN=<same_token>`
- `AUTH_BYPASS_DEV=true`
- `CYGNET_API_URL=http://127.0.0.1:8001`

3. Start stack:
```bash
./start_local.sh
```

4. Open:
- Streamlit: `http://127.0.0.1:8501`
- API docs: `http://127.0.0.1:8001/api/docs`

5. Stop stack:
```bash
./stop_local.sh
```

## What Runs Where

- PostgreSQL: Docker (`docker-compose.minimal.yml`)
- FastAPI: local Python process
- Streamlit: local Python process
- Ollama: optional local process on `localhost:11434`

## Useful Commands

```bash
# API logs
tail -f api.log

# Streamlit logs
tail -f streamlit.log

# PostgreSQL logs
docker logs -f cygnet-postgres-only
```

## Troubleshooting

```bash
# Recreate DB container
docker compose -f docker-compose.minimal.yml down -v
docker compose -f docker-compose.minimal.yml up -d

# Port checks
lsof -i :5433
lsof -i :8001
lsof -i :8501

# Run migrations manually
poetry run alembic upgrade head
```
