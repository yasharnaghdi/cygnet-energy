"""FastAPI application for Cygnet Energy."""


def create_app():
    from src.api.main import app

    return app


__all__ = ["create_app"]
