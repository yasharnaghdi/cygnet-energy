#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.docker}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_EXAMPLE="${ENV_FILE}.example"
PROJECT_NAME="${PROJECT_NAME:-cygnet-full}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
}

wait_http_ok() {
  local url="$1"
  local retries="${2:-90}"
  local delay="${3:-2}"

  for _ in $(seq 1 "$retries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

wait_service_healthy() {
  local service="$1"
  local retries="${2:-90}"
  local delay="${3:-2}"
  local container_id
  local status

  for _ in $(seq 1 "$retries"); do
    container_id="$(
      docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null || true
    )"
    if [[ -n "$container_id" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      if [[ "$status" == "healthy" || "$status" == "running" ]]; then
        return 0
      fi
    fi
    sleep "$delay"
  done
  return 1
}

require_cmd docker
require_cmd curl

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created $ENV_FILE from $ENV_EXAMPLE"
    echo "Edit $ENV_FILE and set ENTSOE_API_TOKEN before ingesting real data."
  else
    echo "Missing $ENV_FILE and no template found at $ENV_EXAMPLE"
    exit 1
  fi
fi

if grep -Eq '^(ENTSOE_API_TOKEN=|ENTSOE_API_TOKEN=your_entsoe_token_here|ENTSOE_API_TOKEN=YOUR_.*)$' "$ENV_FILE"; then
  echo "Warning: ENTSOE_API_TOKEN in $ENV_FILE is still a placeholder."
fi

if grep -Eq '^(OPENAI_API_KEY=|OPENAI_API_KEY=sk-\.\.\.|OPENAI_API_KEY=your_openai_key_here)$' "$ENV_FILE"; then
  echo "Warning: OPENAI_API_KEY in $ENV_FILE is empty. OpenAI backend will be unavailable."
fi

echo "Starting Docker stack..."
# Clean stale containers from both the canonical project and legacy default project.
docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
docker compose -p "cygnet-energy" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true

docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

echo "Waiting for service health..."
if ! wait_service_healthy "postgres" 90 2; then
  echo "Postgres did not become healthy in time."
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=120 postgres
  exit 1
fi
if ! wait_service_healthy "api" 90 2; then
  echo "API did not become healthy in time."
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=120 api
  exit 1
fi
if ! wait_service_healthy "app" 90 2; then
  echo "Streamlit did not become healthy in time."
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=120 app
  exit 1
fi

echo "Running migrations..."
docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api poetry run alembic upgrade head

if wait_http_ok "http://127.0.0.1:8001/healthz" 20 1; then
  api_status="ok"
else
  api_status="not reachable from host"
fi

if curl -fsS "http://127.0.0.1:8001/api/reports/history?limit=1" >/dev/null 2>&1; then
  history_msg="history endpoint ok"
else
  history_msg="history endpoint not reachable yet"
fi

echo
echo "Stack ready"
echo "API:       http://127.0.0.1:8001"
echo "Streamlit: http://127.0.0.1:8501"
echo "API host:  $api_status"
echo "Status:    $history_msg"
