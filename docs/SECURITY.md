# Security

## OIDC/JWT Model
- API endpoints are protected by bearer-token authentication.
- Tokens are validated against issuer/audience and signing keys from `OIDC_JWKS_URL`.
- JWKS responses are cached using `OIDC_JWKS_CACHE_SECONDS` to reduce key-fetch overhead.
- Required scopes and roles are enforced before request handlers execute.

## No-Secrets-In-Git Rules
- Never commit real tokens, client secrets, private keys, or production URLs with credentials.
- Keep `.env` untracked; use `.env.example` placeholders only.
- Store certificates and runtime secrets outside git-tracked paths.

## Rotation Guidance
- Rotate OIDC client secret, cookie secret, and database credentials on role changes or suspected exposure.
- After rotation, update runtime secret stores first, then restart `oauth2-proxy`, API, and nginx.
- Re-run `/healthz` and `/readyz` checks after rotation.

## Rate Limiting Semantics
- Rate limiting keys requests by authenticated subject (`sub`) when available.
- Fallback keying uses `X-API-Key` header and then client IP.

## Headers and CSP
- nginx applies security headers including HSTS, X-Frame-Options, X-Content-Type-Options, and CSP.
- CSP should remain least-privilege and be tightened whenever front-end dependencies change.
