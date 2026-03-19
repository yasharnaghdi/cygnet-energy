#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000}"
STREAMLIT_URL="${STREAMLIT_URL:-http://127.0.0.1:8501}"

wait_http_ok() {
  local url="$1"
  local retries="${2:-60}"
  local delay="${3:-2}"

  for _ in $(seq 1 "$retries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done

  echo "Timed out waiting for $url"
  return 1
}

wait_http_ok "$API_URL/healthz"
wait_http_ok "$API_URL/api/reports/history?limit=1"
wait_http_ok "$FRONTEND_URL"
wait_http_ok "$STREAMLIT_URL/_stcore/health"

echo "Stack smoke checks passed"
