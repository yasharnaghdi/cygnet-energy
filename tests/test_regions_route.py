from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import indicators


def test_regions_default_entsoe() -> None:
    client = TestClient(app)

    response = client.get("/v1/regions")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {"region_id": "DE", "region_type": "zone", "source": "entsoe"},
        {"region_id": "FR", "region_type": "zone", "source": "entsoe"},
        {"region_id": "GB", "region_type": "zone", "source": "entsoe"},
        {"region_id": "ES", "region_type": "zone", "source": "entsoe"},
        {"region_id": "IT", "region_type": "zone", "source": "entsoe"},
    ]


def test_regions_eia_from_db(monkeypatch) -> None:
    class DummyCursor:
        def execute(self, query: str) -> None:
            self.query = query

        def fetchall(self):
            return [("CA",), ("TX",), ("NY",)]

        def close(self) -> None:
            return None

    class DummyConnection:
        def cursor(self):
            return DummyCursor()

        def close(self) -> None:
            return None

    monkeypatch.setattr(indicators, "get_connection", lambda: DummyConnection())

    client = TestClient(app)
    response = client.get("/v1/regions", params={"source": "eia"})

    assert response.status_code == 200
    assert response.json() == [
        {"region_id": "CA", "region_type": "state", "source": "eia"},
        {"region_id": "TX", "region_type": "state", "source": "eia"},
        {"region_id": "NY", "region_type": "state", "source": "eia"},
    ]
