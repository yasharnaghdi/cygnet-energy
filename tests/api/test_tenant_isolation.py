from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request as StarletteRequest

from src.api.main import app
from src.api.middleware import auth_dev
from src.api.middleware.auth import verify_token
from src.api.models.schemas import TokenData
from src.api.routes import analytics, ingest, reports
from src.db.constants import SEED_TENANT_ID

TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
TENANT_A_TOKEN = "tenant-a-token"
TENANT_B_TOKEN = "tenant-b-token"


@pytest.fixture
def tenant_token_override():
    token_map = {
        TENANT_A_TOKEN: TENANT_A,
        TENANT_B_TOKEN: TENANT_B,
    }

    def _override(request: Request) -> TokenData:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        tenant_id = token_map.get(token, SEED_TENANT_ID)
        request.state.token_sub = f"user-{token or 'seed'}"
        request.state.token_roles = ["analyst"]
        request.state.token_scopes = ["api.read"]
        request.state.tenant_id = tenant_id
        return TokenData(
            sub=request.state.token_sub,
            roles=["analyst"],
            scopes=["api.read"],
            tenant_id=tenant_id,
        )

    app.dependency_overrides[verify_token] = _override
    yield
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_tenant_a_cannot_read_tenant_b_timeseries(tenant_token_override, async_client, monkeypatch) -> None:
    class DummyCursor:
        def __init__(self):
            self._rows = []

        def execute(self, _query: str, params=None) -> None:
            tenant = next((value for value in (params or []) if isinstance(value, UUID)), SEED_TENANT_ID)
            rows_by_tenant = {
                TENANT_A: [{"timestamp": "2026-03-01T00:00:00+00:00", "renewable_pct": 55.0}],
            }
            self._rows = rows_by_tenant.get(tenant, [])

        def fetchall(self):
            return self._rows

        def close(self) -> None:
            return None

    class DummyConnection:
        def cursor(self, cursor_factory=None):
            return DummyCursor()

        def close(self) -> None:
            return None

    monkeypatch.setattr(analytics, "get_connection", lambda: DummyConnection())

    response = await async_client.get(
        "/api/analytics/renewable-fraction",
        params={"zone": "DE", "start_date": "2026-03-01", "end_date": "2026-03-02"},
        headers={"Authorization": f"Bearer {TENANT_B_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_tenant_b_cannot_read_tenant_a_reports(tenant_token_override, async_client, monkeypatch) -> None:
    class FakeQuery:
        def __init__(self, rows):
            self._rows = list(rows)

        def join(self, *args, **kwargs):
            return self

        def filter(self, *criteria):
            rows = self._rows
            for criterion in criteria:
                key = getattr(getattr(criterion, "left", None), "key", None)
                right = getattr(criterion, "right", None)
                value = getattr(right, "value", None)
                if key is None:
                    continue
                rows = [row for row in rows if getattr(row, key, None) == value]
            self._rows = rows
            return self

        def count(self):
            return len(self._rows)

        def order_by(self, *args, **kwargs):
            return self

        def offset(self, value: int):
            self._rows = self._rows[value:]
            return self

        def limit(self, value: int):
            self._rows = self._rows[:value]
            return self

        def all(self):
            return list(self._rows)

    class FakeSession:
        def __init__(self, rows):
            self._rows = rows

        def query(self, _model):
            return FakeQuery(self._rows)

        def close(self) -> None:
            return None

    tenant_a_report = SimpleNamespace(
        report_id="rpt-a",
        session_id="session-a",
        generated_at=datetime.now(timezone.utc),
        persona="trader",
        zone="DE",
        scenario="Base Case",
        backend="fallback",
        model=None,
        is_favorite=False,
        tags=None,
        tenant_id=TENANT_A,
    )

    monkeypatch.setattr(reports, "get_db_session", lambda: FakeSession([tenant_a_report]))

    response = await async_client.get(
        "/api/reports/history",
        headers={"Authorization": f"Bearer {TENANT_B_TOKEN}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["reports"] == []


@pytest.mark.anyio
async def test_insert_scopes_to_token_tenant(tenant_token_override, async_client, monkeypatch) -> None:
    monkeypatch.setenv("ENTSOE_API_TOKEN", "test-token")
    captured: dict[str, UUID] = {}

    class FakeIngestionService:
        def fetch_and_store(self, zone, start, end, tenant_id):
            captured["tenant_id"] = tenant_id
            return {
                "zone": zone,
                "generation_records": 1,
                "load_records": 0,
                "total_records": 1,
                "freshest_timestamp": start,
            }

    monkeypatch.setattr(ingest, "EntsoEIngestionService", FakeIngestionService)

    response = await async_client.post(
        "/api/ingest/generation",
        headers={"Authorization": f"Bearer {TENANT_A_TOKEN}"},
        json={
            "zone": "DE",
            "start": "2026-03-01T00:00:00Z",
            "end": "2026-03-01T01:00:00Z",
            "overwrite": False,
        },
    )

    assert response.status_code == 200
    assert captured["tenant_id"] == TENANT_A


def test_dev_auth_uses_seed_tenant(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BYPASS_DEV", "true")
    request = StarletteRequest({"type": "http", "headers": []})

    token = auth_dev.get_dev_token(request)

    assert token is not None
    assert token.tenant_id == SEED_TENANT_ID
    assert request.state.tenant_id == SEED_TENANT_ID
