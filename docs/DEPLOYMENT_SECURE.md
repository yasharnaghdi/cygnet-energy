# Secure Deployment

## Run Hardened Stack
```bash
cp .env.example .env
docker compose -f docker-compose.secure.yml up --build -d
```

## Required Environment Variables (names only)
- `CYGNET_VERSION`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL`
- `ENTSOE_API_TOKEN`
- `OIDC_ISSUER`
- `OIDC_JWKS_URL`
- `OIDC_AUDIENCE`
- `OIDC_REQUIRED_SCOPES`
- `OIDC_REQUIRED_ROLES`
- `OIDC_JWKS_CACHE_SECONDS`
- `OAUTH2_PROXY_CLIENT_ID`
- `OAUTH2_PROXY_CLIENT_SECRET`
- `OAUTH2_PROXY_COOKIE_SECRET`
- `OAUTH2_PROXY_REDIRECT_URL`
- `OAUTH2_PROXY_ISSUER_URL`
- `OAUTH2_PROXY_SCOPE`
- `OAUTH2_PROXY_EMAIL_DOMAINS`

## Component Placement
- TLS termination and security headers are handled by nginx (`deploy/nginx/default.conf`).
- User authentication flow is handled by `oauth2-proxy` against the configured OIDC provider.
- Authenticated API requests are forwarded to FastAPI (`cygnet-api`).
- Postgres is the readiness dependency checked by `/readyz`.

## Troubleshooting
- `curl http://localhost:8000/healthz` fails: check API container logs and process startup.
- `curl http://localhost:8000/readyz` fails: verify `DATABASE_URL`, Postgres health, and dependency order.
- OIDC/JWKS errors (401/503): verify `OIDC_ISSUER`, `OIDC_JWKS_URL`, audience/scopes/roles, and outbound connectivity from API container.
- nginx auth loop: verify oauth2-proxy redirect URL, cookie secret length, and trusted domain settings.
