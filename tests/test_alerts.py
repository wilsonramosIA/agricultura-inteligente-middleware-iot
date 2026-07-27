from fastapi.testclient import TestClient

from alerts import main as alerts
from common import config


def test_alert_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ALERT_DB_PATH", str(tmp_path / "alerts.db"))
    headers = {"X-Internal-API-Key": config.INTERNAL_API_KEY}
    event = {"telemetry_id": 1, "sensor_id": "solo-01", "metric": "soil_moisture", "value": 18}

    with TestClient(alerts.app) as client:
        assert client.post("/alerts/evaluate", json=event).status_code == 401
        result = client.post("/alerts/evaluate", json=event, headers=headers)
        assert result.status_code == 200
        assert result.json()["severity"] == "warning"

        alert_list = client.get("/alerts", headers=headers)
        assert len(alert_list.json()) == 1
        alert_id = alert_list.json()[0]["id"]
        assert client.patch(f"/alerts/{alert_id}/acknowledge", headers=headers).json()["acknowledged"] is True
        assert client.get("/alerts", headers=headers).json() == []

        offline = {"telemetry_id": -1, "sensor_id": "solo-01", "metric": "sensor_offline", "value": 301}
        offline_result = client.post("/alerts/evaluate", json=offline, headers=headers)
        assert offline_result.json()["severity"] == "critical"
        resolved = client.post("/alerts/sensors/solo-01/online", headers=headers)
        assert resolved.json()["resolved_offline_alerts"] == 1
        assert client.get("/alerts", headers=headers).json() == []
