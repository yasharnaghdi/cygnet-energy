from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.db.connection import database_url


@lru_cache(maxsize=1)
def get_db_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)
