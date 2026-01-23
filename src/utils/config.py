import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

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
DB_NAME = os.getenv("DB_NAME", "cygnet-energy")


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
