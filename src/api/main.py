from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from src.api.models.schemas import ErrorResponse
from src.api.routes import carbon_intensity, generation, legacy, optimization, regimes

app = FastAPI(
    title="Cygnet Energy API",
    version="1.0.1",
    description="European grid intelligence platform - Real-time electricity data",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_code_for_status(status_code: int, detail: str) -> str:
    if status_code == 400:
        if "zone" in detail.lower():
            return "INVALID_ZONE"
        return "INVALID_REQUEST"
    if status_code == 401:
        if "unauthorized" in detail.lower():
            return "UNAUTHORIZED"
        return "INVALID_TOKEN"
    if status_code == 404:
        if "not found" in detail.lower():
            return "NOT_FOUND"
        return "NO_DATA"
    if status_code == 429:
        return "RATE_LIMIT_EXCEEDED"
    return "INTERNAL_ERROR"


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    payload = ErrorResponse(
        detail=detail,
        error_code=_error_code_for_status(exc.status_code, detail),
        timestamp=datetime.now(timezone.utc),
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    payload = ErrorResponse(
        detail="Invalid request",
        error_code="INVALID_REQUEST",
        timestamp=datetime.now(timezone.utc),
    )
    return JSONResponse(status_code=400, content=payload.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    payload = ErrorResponse(
        detail="Internal server error",
        error_code="INTERNAL_ERROR",
        timestamp=datetime.now(timezone.utc),
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


app.include_router(legacy.router)
app.include_router(carbon_intensity.router)
app.include_router(optimization.router)
app.include_router(generation.router)
app.include_router(regimes.router)
