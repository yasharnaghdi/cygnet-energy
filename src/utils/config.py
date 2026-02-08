import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(Path(__file__).resolve().parent.parent.parent / ".env")

# ENTSO-E API
API_TOKEN = os.getenv("API_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "https://web-api.tp.entsoe.eu/api")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

#Database
DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DS_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "cygnet_energy")


# App setting
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validation
if not API_TOKEN:
    raise ValueError("API not found in .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env")

print(f" Config Loaded: ENV={ENVIRONMENT}, DEBUG={DEBUG}")
