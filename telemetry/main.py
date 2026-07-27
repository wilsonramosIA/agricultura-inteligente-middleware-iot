import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, HTTPException

from common import config
from common.database import connect
from common.models import TelemetryInput
from common.security import require_internal_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("telemetry-service")


def initialize_database() -> None:
    with connect(config.TELEMETRY_DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL,
                unit TEXT NOT NULL, location TEXT NOT NULL, received_at TEXT NOT NULL
            )
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    app.state.client = httpx.AsyncClient(timeout=config.TIMEOUT_SECONDS)
    yield
    await app.state.client.aclose()


app = FastAPI(title="Serviço de Telemetria", version="1.0.0", lifespan=lifespan)


@app.get("/health", tags=["Operação"])
async def health():
    return {"status": "ok", "service": "telemetry-service"}


@app.post("/telemetry", status_code=201, dependencies=[Depends(require_internal_key)], tags=["Telemetria"])
async def create_telemetry(payload: TelemetryInput):
    received_at = datetime.now(timezone.utc).isoformat()
    with connect(config.TELEMETRY_DB_PATH) as db:
        cursor = db.execute(
            "INSERT INTO telemetry (sensor_id, metric, value, unit, location, received_at) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.sensor_id, payload.metric, payload.value, payload.unit, payload.location, received_at),
        )
        telemetry_id = cursor.lastrowid

    event = {"telemetry_id": telemetry_id, **payload.model_dump(), "received_at": received_at}
    notification = "not_evaluated"
    try:
        response = await app.state.client.post(
            f"{config.ALERT_URL}/alerts/evaluate",
            json=event,
            headers={"X-Internal-API-Key": config.INTERNAL_API_KEY},
        )
        response.raise_for_status()
        notification = response.json()["result"]
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
        # A persistência da telemetria não é perdida se o serviço de alertas falhar.
        logger.warning("telemetry_id=%s alert_evaluation_failed=%s", telemetry_id, type(exc).__name__)
        notification = "pending_due_to_alert_service_failure"

    return {"id": telemetry_id, "received_at": received_at, "alert_evaluation": notification}


@app.get("/telemetry", dependencies=[Depends(require_internal_key)], tags=["Telemetria"])
async def list_telemetry(limit: int = 50):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit deve estar entre 1 e 100")
    with connect(config.TELEMETRY_DB_PATH) as db:
        rows = db.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]

