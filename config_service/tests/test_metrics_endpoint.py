import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from src.api.main import create_app


def test_metrics_endpoint_exists():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "config_service_http_requests_total" in resp.text
