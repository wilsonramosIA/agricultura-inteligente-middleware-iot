import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
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
        db.execute("""
            CREATE TABLE IF NOT EXISTS pending_alert_evaluations (
                telemetry_id INTEGER PRIMARY KEY,
                event_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                queued_at TEXT NOT NULL,
                last_attempt_at TEXT
            )
        """)


async def send_to_alert_service(event: dict) -> str:
    response = await app.state.client.post(
        f"{config.ALERT_URL}/alerts/evaluate",
        json=event,
        headers={"X-Internal-API-Key": config.INTERNAL_API_KEY},
    )
    response.raise_for_status()
    return response.json()["result"]


def queue_alert_evaluation(event: dict, error: Exception) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(config.TELEMETRY_DB_PATH) as db:
        db.execute(
            """INSERT OR IGNORE INTO pending_alert_evaluations
               (telemetry_id, event_json, last_error, queued_at)
               VALUES (?, ?, ?, ?)""",
            (event["telemetry_id"], json.dumps(event), type(error).__name__, now),
        )


async def retry_pending_alert_evaluations(limit: int | None = None) -> dict:
    """Reenvia eventos persistidos quando Alertas volta a ficar disponível."""
    batch_size = limit or config.PENDING_RETRY_BATCH_SIZE
    with connect(config.TELEMETRY_DB_PATH) as db:
        rows = db.execute(
            "SELECT telemetry_id, event_json FROM pending_alert_evaluations ORDER BY queued_at LIMIT ?",
            (batch_size,),
        ).fetchall()

    delivered = 0
    for row in rows:
        telemetry_id = row["telemetry_id"]
        try:
            await send_to_alert_service(json.loads(row["event_json"]))
            with connect(config.TELEMETRY_DB_PATH) as db:
                db.execute("DELETE FROM pending_alert_evaluations WHERE telemetry_id = ?", (telemetry_id,))
            delivered += 1
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
            with connect(config.TELEMETRY_DB_PATH) as db:
                db.execute(
                    """UPDATE pending_alert_evaluations
                       SET attempts = attempts + 1, last_error = ?, last_attempt_at = ?
                       WHERE telemetry_id = ?""",
                    (type(exc).__name__, datetime.now(timezone.utc).isoformat(), telemetry_id),
                )
    if rows:
        logger.info("pending_alerts_processed=%s delivered=%s", len(rows), delivered)
    return {"processed": len(rows), "delivered": delivered, "remaining": len(rows) - delivered}


async def pending_retry_worker() -> None:
    while True:
        await asyncio.sleep(config.RETRY_INTERVAL_SECONDS)
        await retry_pending_alert_evaluations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    app.state.client = httpx.AsyncClient(timeout=config.TIMEOUT_SECONDS)
    retry_task = asyncio.create_task(pending_retry_worker())
    yield
    retry_task.cancel()
    with suppress(asyncio.CancelledError):
        await retry_task
    await app.state.client.aclose()


app = FastAPI(title="Serviço de Telemetria", version="1.0.0", lifespan=lifespan)


@app.get("/health", tags=["Operação"])
async def health():
    with connect(config.TELEMETRY_DB_PATH) as db:
        pending = db.execute("SELECT COUNT(*) FROM pending_alert_evaluations").fetchone()[0]
    return {"status": "ok", "service": "telemetry-service", "pending_alert_evaluations": pending}


@app.post("/telemetry", status_code=201, dependencies=[Depends(require_internal_key)], tags=["Telemetria"])
async def create_telemetry(payload: TelemetryInput):
    retry_summary = await retry_pending_alert_evaluations(limit=5)
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
        notification = await send_to_alert_service(event)
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
        # A telemetria e o evento pendente são persistidos antes de responder ao cliente.
        queue_alert_evaluation(event, exc)
        logger.warning("telemetry_id=%s alert_evaluation_failed=%s", telemetry_id, type(exc).__name__)
        notification = "pending_due_to_alert_service_failure"

    return {
        "id": telemetry_id,
        "received_at": received_at,
        "alert_evaluation": notification,
        "retried_pending_alerts": retry_summary,
    }


@app.get("/telemetry", dependencies=[Depends(require_internal_key)], tags=["Telemetria"])
async def list_telemetry(limit: int = 50):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit deve estar entre 1 e 100")
    with connect(config.TELEMETRY_DB_PATH) as db:
        rows = db.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


@app.get("/pending-alerts", dependencies=[Depends(require_internal_key)], tags=["Operação"])
async def pending_alerts_status():
    with connect(config.TELEMETRY_DB_PATH) as db:
        rows = db.execute(
            "SELECT telemetry_id, attempts, last_error, queued_at, last_attempt_at FROM pending_alert_evaluations ORDER BY queued_at"
        ).fetchall()
    return {"count": len(rows), "items": [dict(row) for row in rows]}


@app.post("/maintenance/retry-pending", dependencies=[Depends(require_internal_key)], tags=["Operação"])
async def retry_pending_alerts():
    return await retry_pending_alert_evaluations()
