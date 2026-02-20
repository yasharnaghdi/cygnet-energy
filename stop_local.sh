#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

stop_pid_file() {
  local pid_file="$1"
  local label="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      echo "Stopped $label (PID $pid)"
    else
      echo "$label PID file found but process is not running"
    fi
    rm -f "$pid_file"
  else
    echo "$label is not running (no PID file)"
  fi
}

STOP_DB=false
if [[ "${1:-}" == "--stop-db" ]]; then
  STOP_DB=true
fi

stop_pid_file ".api.pid" "API"
stop_pid_file ".streamlit.pid" "Streamlit"

if [[ "$STOP_DB" == true ]]; then
  docker compose -f docker-compose.minimal.yml down
  echo "Stopped PostgreSQL container"
elif [[ -t 0 ]]; then
  read -r -p "Stop PostgreSQL container too? [y/N] " reply
  if [[ "$reply" =~ ^[Yy]$ ]]; then
    docker compose -f docker-compose.minimal.yml down
    echo "Stopped PostgreSQL container"
  else
    echo "Left PostgreSQL container running"
  fi
else
  echo "Left PostgreSQL container running"
fi
