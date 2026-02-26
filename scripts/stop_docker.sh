#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/docker_common.sh"

ENV_FILE="${ENV_FILE:-.env.docker}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROJECT_NAME="${PROJECT_NAME:-cygnet-full}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Missing required command: docker"
  exit 1
fi

ensure_docker_credential_helper_on_path

docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans
