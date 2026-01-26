"""FastAPI application entrypoint for Cygnet Energy."""
from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        from src.api.main import app

        return app
    raise AttributeError(f"module 'src.api' has no attribute {name!r}")
