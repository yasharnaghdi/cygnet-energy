#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENV_PATHS = {
    "local": ROOT / ".env",
    "docker": ROOT / ".env.docker",
}
EXAMPLE_PATHS = {
    "local": ROOT / ".env.example",
    "docker": ROOT / ".env.docker.example",
}

SYNC_GROUPS = [
    ("API_TOKEN", "ENTSOE_API_TOKEN"),
    ("EIA_API_KEY",),
    ("OPENAI_API_KEY",),
    ("OPENAI_MODEL",),
    ("OPENAI_MAX_TOKENS",),
    ("OPENAI_TEMPERATURE",),
    ("OLLAMA_MODEL",),
    ("HF_MODEL",),
    ("POSTGRES_USER",),
    ("POSTGRES_PASSWORD",),
    ("POSTGRES_DB",),
]

PLACEHOLDER_PREFIXES = ("YOUR_",)
PLACEHOLDER_VALUES = {
    "",
    "your_entsoe_token_here",
    "your_eia_key_here",
    "your_openai_key_here",
    "sk-...",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create and sync .env files for local and Docker runtimes.")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output.")
    return parser.parse_args()


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def is_placeholder(value: str) -> bool:
    return value in PLACEHOLDER_VALUES or value.startswith(PLACEHOLDER_PREFIXES)


def ensure_env_file(kind: str) -> bool:
    env_path = ENV_PATHS[kind]
    if env_path.exists():
        return False
    example_path = EXAMPLE_PATHS[kind]
    if not example_path.exists():
        raise FileNotFoundError(f"Missing template: {example_path}")
    shutil.copyfile(example_path, env_path)
    return True


def upsert_env_value(path: Path, key: str, value: str) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    replacement = f"{key}={value}"
    updated = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            if line == replacement:
                return False
            lines[index] = replacement
            updated = True
            break
    if not updated:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(replacement)
        updated = True
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def sync_direction(source_kind: str, target_kind: str) -> list[str]:
    source_values = read_env(ENV_PATHS[source_kind])
    target_values = read_env(ENV_PATHS[target_kind])
    changed_keys: list[str] = []

    for group in SYNC_GROUPS:
        source_value = ""
        for key in group:
            candidate = source_values.get(key, "")
            if candidate and not is_placeholder(candidate):
                source_value = candidate
                break
        if not source_value:
            continue

        for key in group:
            current = target_values.get(key, "")
            if current and not is_placeholder(current):
                continue
            if upsert_env_value(ENV_PATHS[target_kind], key, source_value):
                target_values[key] = source_value
                changed_keys.append(key)

    return changed_keys


def main() -> int:
    args = parse_args()
    created: list[str] = []
    for kind in ("local", "docker"):
        if ensure_env_file(kind):
            created.append(ENV_PATHS[kind].name)

    docker_updates = sync_direction("local", "docker")
    local_updates = sync_direction("docker", "local")

    if not args.quiet:
        if created:
            print(f"Created: {', '.join(created)}")
        if docker_updates:
            print(f"Updated .env.docker: {', '.join(sorted(set(docker_updates)))}")
        if local_updates:
            print(f"Updated .env: {', '.join(sorted(set(local_updates)))}")
        if not created and not docker_updates and not local_updates:
            print("Environment files already set up.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
