from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException

from common import config
from common.database import connect
from common.security import require_internal_key


def initialize_database() -> None:
    with connect(config.ALERT_DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telemetry_id INTEGER NOT NULL UNIQUE, sensor_id TEXT NOT NULL,
                metric TEXT NOT NULL, value REAL NOT NULL, severity TEXT NOT NULL,
                message TEXT NOT NULL, created_at TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0
            )
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Serviço de Alertas", version="1.0.0", lifespan=lifespan)


def evaluate(metric: str, value: float) -> tuple[str, str] | None:
    """Regras simples e explícitas de negócio para a demonstração."""
    normalized = metric.lower()
    if normalized == "temperature" and value >= 40:
        return "critical", "Temperatura crítica: ação imediata necessária."
    if normalized == "temperature" and value >= 35:
        return "warning", "Temperatura acima do limite recomendado."
    if normalized == "humidity" and value <= 25:
        return "warning", "Umidade abaixo do limite recomendado."
    if normalized == "soil_moisture" and value <= 20:
        return "warning", "Umidade do solo abaixo do limite: irrigação recomendada."
    if normalized == "sensor_offline" and value > 0:
        return "critical", f"Sensor sem comunicação há {int(value)} segundos."
    if normalized == "smoke" and value > 0:
        return "critical", "Fumaça detectada."
    return None


@app.get("/health", tags=["Operação"])
async def health():
    return {"status": "ok", "service": "alert-service"}


@app.post("/alerts/evaluate", dependencies=[Depends(require_internal_key)], tags=["Interno"])
async def evaluate_telemetry(event: dict):
    rule = evaluate(event["metric"], float(event["value"]))
    if rule is None:
        return {"result": "no_alert"}
    severity, message = rule
    created_at = datetime.now(timezone.utc).isoformat()
    with connect(config.ALERT_DB_PATH) as db:
        db.execute(
            """INSERT OR IGNORE INTO alerts
               (telemetry_id, sensor_id, metric, value, severity, message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event["telemetry_id"], event["sensor_id"], event["metric"], event["value"], severity, message, created_at),
        )
    return {"result": "alert_created", "severity": severity}


@app.get("/alerts", dependencies=[Depends(require_internal_key)], tags=["Alertas"])
async def list_alerts(only_open: bool = True):
    query = "SELECT * FROM alerts"
    if only_open:
        query += " WHERE acknowledged = 0"
    query += " ORDER BY id DESC"
    with connect(config.ALERT_DB_PATH) as db:
        rows = db.execute(query).fetchall()
    return [{**dict(row), "acknowledged": bool(row["acknowledged"])} for row in rows]


@app.post("/alerts/sensors/{sensor_id}/online", dependencies=[Depends(require_internal_key)], tags=["Interno"])
async def resolve_sensor_offline_alerts(sensor_id: str):
    """Fecha alertas de indisponibilidade assim que o sensor volta a reportar."""
    with connect(config.ALERT_DB_PATH) as db:
        result = db.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE sensor_id = ? AND metric = 'sensor_offline' AND acknowledged = 0",
            (sensor_id,),
        )
    return {"sensor_id": sensor_id, "resolved_offline_alerts": result.rowcount}


@app.patch("/alerts/{alert_id}/acknowledge", dependencies=[Depends(require_internal_key)], tags=["Alertas"])
async def acknowledge_alert(alert_id: int):
    with connect(config.ALERT_DB_PATH) as db:
        result = db.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return {"id": alert_id, "acknowledged": True}
