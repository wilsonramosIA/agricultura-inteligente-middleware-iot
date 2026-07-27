from fastapi.testclient import TestClient

from common import config
from gateway.main import app


def test_gateway_requires_client_api_key():
    with TestClient(app) as client:
        health = client.get("/health", headers={"X-Request-ID": "demo-123"})
        assert health.status_code == 200
        assert health.headers["X-Request-ID"] == "demo-123"
        denied = client.get("/api/v1/alerts")
        assert denied.status_code == 401
        assert client.get("/api/v1/alerts", headers={"X-API-Key": config.CLIENT_API_KEY}).status_code in {503, 504}

