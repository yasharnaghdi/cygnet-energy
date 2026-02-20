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
cp .env.docker.example .env.docker
poetry install
make start
make status
```

Expected healthy state:
- Docker baseline stack shows running containers for `postgres`, `api`, and `app`.

Useful commands:
```bash
make logs
make stop
```

## v1.1.0 Scope
- OIDC/JWT auth with JWKS-backed token validation
- Subject-aware rate limiting
- `/healthz` and `/readyz` probes
- Hardened deployment stack via `docker-compose.secure.yml` + nginx/oauth2-proxy
- Production docs replacing the former setup guide

Experimental analytics and secret-sauce modeling are not part of the active v1.1.0 mainline runtime scope.
