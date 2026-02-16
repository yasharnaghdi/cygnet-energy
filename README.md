# Cygnet Quantum Analytics

Secure grid-carbon infrastructure on ENTSO-E data.

## Documentation
- Quickstart: `docs/QUICKSTART.md`
- Secure deployment: `docs/DEPLOYMENT_SECURE.md`
- Security model and secret policy: `docs/SECURITY.md`
- Docs index: `docs/README.md`
- Release policy: `RELEASE_POLICY.md`

## Quickstart
```bash
cp .env.example .env
poetry install
python scripts/smoke_check.py
docker compose up --build -d
docker compose ps
```

Expected healthy state:
- Smoke check ends with `All smoke checks passed.`
- Docker baseline stack shows running containers for `postgres`, `api`, and `app`.

## v1.1.0 Scope
- OIDC/JWT auth with JWKS-backed token validation
- Subject-aware rate limiting
- `/healthz` and `/readyz` probes
- Hardened deployment stack via `docker-compose.secure.yml` + nginx/oauth2-proxy
- Production docs replacing the former setup guide

Experimental analytics and secret-sauce modeling are not part of the active v1.1.0 mainline runtime scope.
