#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

API_PID_FILE=".api.pid"
STREAMLIT_PID_FILE=".streamlit.pid"

cleanup_on_error() {
  if [[ -f "$API_PID_FILE" ]]; then
    kill "$(cat "$API_PID_FILE")" 2>/dev/null || true
    rm -f "$API_PID_FILE"
  fi
  if [[ -f "$STREAMLIT_PID_FILE" ]]; then
    kill "$(cat "$STREAMLIT_PID_FILE")" 2>/dev/null || true
    rm -f "$STREAMLIT_PID_FILE"
  fi
}

wait_for_http() {
  local url="$1"
  local retries="${2:-30}"
  local delay="${3:-1}"

  for _ in $(seq 1 "$retries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

listener_pid_on_port() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
}

ensure_port_available() {
  local port="$1"
  local label="$2"
  local expected_pattern="$3"

  local pid
  pid="$(listener_pid_on_port "$port")"
  if [[ -z "$pid" ]]; then
    return 0
  fi

  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"

  if [[ -n "$cmd" && "$cmd" == *"$expected_pattern"* ]]; then
    echo "Stopping stale $label on port $port (PID $pid)..."
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    pid="$(listener_pid_on_port "$port")"
    if [[ -n "$pid" ]]; then
      echo "Failed to free port $port (still used by PID $pid)"
      exit 1
    fi
    return 0
  fi

  echo "Port $port is already in use by an unrelated process."
  if [[ -n "$cmd" ]]; then
    echo "Command: $cmd"
  fi
  echo "Stop that process before running ./start_local.sh"
  exit 1
}

trap cleanup_on_error ERR

if [[ ! -f ".env" ]]; then
  echo "Missing .env file"
  echo "Run: cp .env.example .env"
  exit 1
fi

while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
    eval "export $line"
  fi
done < ".env"

if [[ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]]; then
  mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

echo "Checking PostgreSQL container..."
if ! docker ps --format '{{.Names}}' | grep -qx 'cygnet-postgres-only'; then
  echo "Starting PostgreSQL container..."
  docker compose -f docker-compose.minimal.yml up -d
fi

echo "Waiting for PostgreSQL readiness..."
until docker exec cygnet-postgres-only pg_isready -U cygnet -d energy_db >/dev/null 2>&1; do
  sleep 2
done
echo "PostgreSQL is ready"

echo "Running database migrations..."
poetry run alembic upgrade head

if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Detected local Ollama service"
else
  echo "Local Ollama not detected (optional)"
fi

ensure_port_available "8001" "API" "uvicorn src.api.main:app"
echo "Starting API on 127.0.0.1:8001..."
AUTH_BYPASS_DEV="${AUTH_BYPASS_DEV:-true}" \
nohup poetry run uvicorn src.api.main:app --host 127.0.0.1 --port 8001 > api.log 2>&1 < /dev/null &
API_PID=$!
echo "$API_PID" > "$API_PID_FILE"

if ! kill -0 "$API_PID" >/dev/null 2>&1; then
  echo "API process exited immediately. Inspect api.log"
  exit 1
fi

if ! wait_for_http "http://127.0.0.1:8001/healthz" 45 1; then
  echo "API failed health check. Inspect api.log"
  exit 1
fi

history_status="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8001/api/reports/history?limit=1" || true)"
if [[ "$history_status" == "404" ]]; then
  echo "API started but /api/reports/history returned 404."
  echo "This usually means an outdated API process is still bound to port 8001."
  echo "Run ./stop_local.sh, then ./start_local.sh"
  exit 1
fi
echo "API is healthy"

ensure_port_available "8501" "Streamlit" "streamlit run main_app.py"
echo "Starting Streamlit on 127.0.0.1:8501..."
nohup poetry run streamlit run main_app.py --server.port 8501 --server.address 127.0.0.1 > streamlit.log 2>&1 < /dev/null &
STREAMLIT_PID=$!
echo "$STREAMLIT_PID" > "$STREAMLIT_PID_FILE"

if ! wait_for_http "http://127.0.0.1:8501" 60 1; then
  echo "Streamlit failed startup check. Inspect streamlit.log"
  exit 1
fi
echo "Streamlit is running"

trap - ERR
echo
echo "Local stack started"
echo "Streamlit: http://127.0.0.1:8501"
echo "API:       http://127.0.0.1:8001"
echo "DB:        localhost:5433 (docker: cygnet-postgres-only)"
echo
echo "Logs:"
echo "  tail -f api.log"
echo "  tail -f streamlit.log"
echo
echo "Stop with: ./stop_local.sh"
