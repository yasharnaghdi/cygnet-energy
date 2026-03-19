from __future__ import annotations

import os
import time
from typing import Dict, List
from uuid import UUID

import requests
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.api.middleware.auth_dev import get_dev_token
from src.api.models.schemas import TokenData
from src.db.constants import SEED_TENANT_ID

_auth_scheme = HTTPBearer(auto_error=False)

_jwks_cache: Dict[str, object] | None = None
_jwks_cached_at: float = 0.0
_JWKS_CACHE_SECONDS = int(os.getenv("OIDC_JWKS_CACHE_SECONDS", "300"))


def _load_settings() -> tuple[str, str | None, str, List[str], List[str]]:
    issuer = os.getenv("OIDC_ISSUER")
    jwks_url = os.getenv("OIDC_JWKS_URL")
    audience = os.getenv("OIDC_AUDIENCE")
    required_scopes = [s.strip() for s in os.getenv("OIDC_REQUIRED_SCOPES", "").split(",") if s.strip()]
    required_roles = [r.strip() for r in os.getenv("OIDC_REQUIRED_ROLES", "").split(",") if r.strip()]

    if not issuer or not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC_ISSUER and OIDC_JWKS_URL must be configured",
        )

    return issuer, audience, jwks_url, required_scopes, required_roles


def _fetch_jwks(jwks_url: str) -> Dict[str, object]:
    global _jwks_cache, _jwks_cached_at

    now = time.time()
    if _jwks_cache and (now - _jwks_cached_at) < _JWKS_CACHE_SECONDS:
        return _jwks_cache

    try:
        resp = requests.get(jwks_url, timeout=5)
        resp.raise_for_status()
        data: Dict[str, object] = resp.json()
        _jwks_cache = data
        _jwks_cached_at = now
        return data
    except Exception as exc:  # pragma: no cover - defensive network error handling
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to download JWKS",
        ) from exc


def _select_key(token: str, jwks: Dict[str, object]) -> Dict[str, object]:
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    for key in keys:
        if key.get("kid") == kid:
            return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Signing key not found for token",
    )


def _extract_roles(payload: Dict[str, object]) -> List[str]:
    roles: List[str] = []
    realm_roles = payload.get("realm_access", {})
    if isinstance(realm_roles, dict):
        roles.extend(realm_roles.get("roles", []) or [])

    resource_roles = payload.get("resource_access", {})
    if isinstance(resource_roles, dict):
        for res in resource_roles.values():
            if isinstance(res, dict):
                roles.extend(res.get("roles", []) or [])

    roles.extend(payload.get("roles", []) or [])
    return sorted(set(r for r in roles if isinstance(r, str)))


def _ensure_required(values: List[str], required: List[str], error: str) -> None:
    if not required:
        return
    missing = [val for val in required if val not in values]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required {error}: {', '.join(missing)}",
        )


def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_auth_scheme),
) -> TokenData:
    dev_token = get_dev_token(request)
    if dev_token is not None:
        return dev_token

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    issuer, audience, jwks_url, required_scopes, required_roles = _load_settings()
    jwks = _fetch_jwks(jwks_url)
    key = _select_key(credentials.credentials, jwks)

    try:
        payload = jwt.decode(
            credentials.credentials,
            key,
            algorithms=[key.get("alg", "RS256")],
            audience=audience,
            issuer=issuer,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing subject",
        )

    scopes = payload.get("scope") or payload.get("scopes") or payload.get("scp") or ""
    if isinstance(scopes, str):
        scope_list = [s.strip() for s in scopes.split(" ") if s.strip()]
    elif isinstance(scopes, list):
        scope_list = [s for s in scopes if isinstance(s, str)]
    else:
        scope_list = []

    roles = _extract_roles(payload)
    tenant_claim = payload.get("tenant_id")
    try:
        tenant_id = UUID(str(tenant_claim)) if tenant_claim else SEED_TENANT_ID
    except (TypeError, ValueError):
        tenant_id = SEED_TENANT_ID

    _ensure_required(scope_list, required_scopes, "scopes")
    _ensure_required(roles, required_roles, "roles")

    email = payload.get("email")
    request.state.token_sub = subject
    request.state.token_roles = roles
    request.state.token_scopes = scope_list
    request.state.tenant_id = tenant_id

    return TokenData(
        sub=subject,
        email=email,
        roles=roles,
        scopes=scope_list,
        issuer=payload.get("iss"),
        audience=payload.get("aud"),
        tenant_id=tenant_id,
    )
