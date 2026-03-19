from __future__ import annotations

import os
from typing import List

from fastapi import Request

from src.api.models.schemas import TokenData
from src.db.constants import SEED_TENANT_ID

_TRUE_VALUES = {"1", "true", "yes", "on"}


def auth_bypass_enabled() -> bool:
    return os.getenv("AUTH_BYPASS_DEV", "false").strip().lower() in _TRUE_VALUES


def _split_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or default


def get_dev_token(request: Request) -> TokenData | None:
    if not auth_bypass_enabled():
        return None

    token = TokenData(
        sub=os.getenv("AUTH_BYPASS_SUB", "dev-user"),
        email=os.getenv("AUTH_BYPASS_EMAIL", "dev-user@local"),
        roles=_split_csv(os.getenv("AUTH_BYPASS_ROLES"), ["analyst"]),
        scopes=_split_csv(os.getenv("AUTH_BYPASS_SCOPES"), ["api.read"]),
        issuer="auth-bypass-dev",
        audience=os.getenv("OIDC_AUDIENCE") or "cygnet-api",
        tenant_id=SEED_TENANT_ID,
    )

    request.state.token_sub = token.sub
    request.state.token_roles = token.roles
    request.state.token_scopes = token.scopes
    request.state.tenant_id = token.tenant_id
    return token
