import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import psycopg2
import psycopg2.extras
import yaml
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


_cfg = load_config()
_db_cfg = _cfg["database"]
_DOCKER_DB_HOST_ALIASES = {"postgres", "db", "timescaledb"}
_UUID_ADAPTER_REGISTERED = False


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


def _local_postgres_host() -> str:
    return os.getenv("LOCAL_POSTGRES_HOST", "localhost")


def _local_postgres_port(configured_port: int | None) -> int:
    if configured_port in (None, 5432):
        return int(os.getenv("LOCAL_POSTGRES_PORT", "5433"))
    return int(configured_port)


def _should_rewrite_to_local(host: str | None) -> bool:
    if _running_in_docker():
        return False
    normalized = (host or "").strip().lower()
    return normalized in _DOCKER_DB_HOST_ALIASES


def _best_effort_local_rewrite(configured: str) -> str:
    if _running_in_docker():
        return configured

    # Handles malformed DSNs where SQLAlchemy URL parsing fails.
    replacement = f"@{_local_postgres_host()}:{_local_postgres_port(None)}"
    return re.sub(
        r"@(postgres|db|timescaledb)(?::\d+)?(?=/)",
        replacement,
        configured,
        count=1,
        flags=re.IGNORECASE,
    )


def _normalized_configured_database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if not configured:
        return ""

    try:
        url = make_url(configured)
    except Exception:
        return _best_effort_local_rewrite(configured)

    if not _should_rewrite_to_local(url.host):
        return configured

    return url.set(
        host=_local_postgres_host(),
        port=_local_postgres_port(url.port),
    ).render_as_string(hide_password=False)


def _psycopg_database_url() -> str | None:
    database_url = _normalized_configured_database_url()
    if not database_url:
        return None
    return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)


def _ensure_uuid_adapter() -> None:
    global _UUID_ADAPTER_REGISTERED
    if _UUID_ADAPTER_REGISTERED:
        return
    psycopg2.extras.register_uuid()
    _UUID_ADAPTER_REGISTERED = True


def database_url() -> str:
    configured = _normalized_configured_database_url()
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
    _ensure_uuid_adapter()
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
