import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import psycopg2
import psycopg2.extras
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


_cfg = load_config()
_db_cfg = _cfg["database"]


def _psycopg_database_url() -> str | None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)


def database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        if configured.startswith("postgresql+psycopg2://"):
            return configured
        if configured.startswith("postgresql://"):
            return configured.replace("postgresql://", "postgresql+psycopg2://", 1)
        return configured

    user = quote_plus(str(_db_cfg["user"]))
    password = quote_plus(str(_db_cfg["password"]))
    host = _db_cfg["host"]
    port = _db_cfg["port"]
    name = _db_cfg["name"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_connection():
    configured = _psycopg_database_url()
    if configured:
        return psycopg2.connect(configured)

    return psycopg2.connect(
        host=_db_cfg["host"],
        port=_db_cfg["port"],
        dbname=_db_cfg["name"],
        user=_db_cfg["user"],
        password=_db_cfg["password"],
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker:
    engine = create_engine(database_url(), pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def get_db_session() -> Session:
    return _session_factory()()


def test_connection() -> None:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT 1;")
    cur.fetchone()
    cur.close()
    conn.close()
