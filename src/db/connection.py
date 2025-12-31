from typing import Generator
import psycopg2
import psycopg2.extras
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


_cfg = load_config()
_db_cfg = _cfg["database"]


def get_connection():
    return psycopg2.connect(
        host=_db_cfg["host"],
        port=_db_cfg["port"],
        dbname=_db_cfg["name"],
        user=_db_cfg["user"],
        password=_db_cfg["password"],
    )


def test_connection() -> None:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT 1;")
    cur.fetchone()
    cur.close()
    conn.close()
