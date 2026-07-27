from fastapi.testclient import TestClient

from common import config
from telemetry import main as telemetry


def test_telemetry_persists_and_requires_internal_key(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TELEMETRY_DB_PATH", str(tmp_path / "telemetry.db"))
    monkeypatch.setattr(config, "ALERT_URL", "http://127.0.0.1:1")
    payload = {"sensor_id": "solo-01", "metric": "soil_moisture", "value": 28, "unit": "%", "location": "Talhão Norte"}
    headers = {"X-Internal-API-Key": config.INTERNAL_API_KEY}

    with TestClient(telemetry.app) as client:
        assert client.post("/telemetry", json=payload).status_code == 401
        created = client.post("/telemetry", json=payload, headers=headers)
        assert created.status_code == 201
        assert created.json()["alert_evaluation"] == "pending_due_to_alert_service_failure"
        listing = client.get("/telemetry", headers=headers)
        assert listing.status_code == 200
        assert listing.json()[0]["sensor_id"] == "solo-01"

