#!/usr/bin/env bash

# Ensure Docker credential helpers configured in ~/.docker/config.json
# are discoverable even when Docker Desktop binaries are not in PATH.
ensure_docker_credential_helper_on_path() {
  local docker_config_dir
  local docker_config_file
  local creds_store
  local helper
  local desktop_bin

  docker_config_dir="${DOCKER_CONFIG:-$HOME/.docker}"
  docker_config_file="$docker_config_dir/config.json"

  if [[ ! -f "$docker_config_file" ]]; then
    return 0
  fi

  creds_store="$(sed -nE 's/.*"credsStore"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$docker_config_file" | head -n 1)"
  if [[ -z "$creds_store" ]]; then
    return 0
  fi

  helper="docker-credential-${creds_store}"
  if command -v "$helper" >/dev/null 2>&1; then
    return 0
  fi

  desktop_bin="/Applications/Docker.app/Contents/Resources/bin"
  if [[ -x "$desktop_bin/$helper" ]]; then
    export PATH="$desktop_bin:$PATH"
    echo "Added Docker Desktop helper directory to PATH for this run."
    return 0
  fi

  echo "Docker is configured to use '$helper' but it is not on PATH."
  echo "Expected config: $docker_config_file"
  echo "Fix by adding '$desktop_bin' to PATH or updating Docker credsStore."
  return 1
}
