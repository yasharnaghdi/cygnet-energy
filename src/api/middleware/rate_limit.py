from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.models.schemas import ErrorResponse


def _rate_limit_key(request: Request) -> str:
    # Prefer stable subject from validated JWT so limits follow the user identity.
    sub = getattr(request.state, "token_sub", None)
    if sub:
        return f"sub:{sub}"

    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=["100/hour"])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after: Optional[str] = None
    if hasattr(exc, "headers") and exc.headers:
        retry_after = exc.headers.get("Retry-After")

    headers = {"Retry-After": retry_after} if retry_after else None
    payload = ErrorResponse(
        detail="Rate limit exceeded",
        error_code="RATE_LIMIT_EXCEEDED",
        timestamp=datetime.now(timezone.utc),
    )
    return JSONResponse(status_code=429, content=payload.model_dump(), headers=headers)
