import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from common import config
from common.models import TelemetryInput

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=config.TIMEOUT_SECONDS)
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="Grupo 8 — API Gateway IoT",
    version="1.0.0",
    description="Middleware que autentica clientes, registra requisições e roteia chamadas para os microsserviços.",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_log_and_correlation(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_id=%s method=%s path=%s unhandled_error", request_id, request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Erro interno no gateway", "request_id": request_id})
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%s", request_id, request.method, request.url.path, response.status_code, elapsed_ms)
    return response


def require_client_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != config.CLIENT_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key inválida ou ausente")


async def forward(request: Request, method: str, base_url: str, path: str, payload: dict | None = None) -> Response:
    try:
        result = await request.app.state.client.request(
            method,
            f"{base_url}{path}",
            json=payload,
            headers={"X-Internal-API-Key": config.INTERNAL_API_KEY, "X-Request-ID": request.state.request_id},
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao comunicar com o microsserviço", headers={"Retry-After": "5"})
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Microsserviço indisponível", headers={"Retry-After": "5"})
    return Response(content=result.content, status_code=result.status_code, media_type="application/json")


@app.get("/health", tags=["Operação"])
async def health():
    return {"status": "ok", "service": "api-gateway"}


@app.post("/api/v1/telemetry", status_code=201, tags=["Telemetria"])
async def create_telemetry(payload: TelemetryInput, request: Request, _: None = Depends(require_client_key)):
    return await forward(request, "POST", config.TELEMETRY_URL, "/telemetry", payload.model_dump())


@app.get("/api/v1/telemetry", tags=["Telemetria"])
async def list_telemetry(request: Request, limit: int = 50, _: None = Depends(require_client_key)):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit deve estar entre 1 e 100")
    return await forward(request, "GET", config.TELEMETRY_URL, f"/telemetry?limit={limit}")


@app.get("/api/v1/alerts", tags=["Alertas"])
async def list_alerts(request: Request, only_open: bool = True, _: None = Depends(require_client_key)):
    return await forward(request, "GET", config.ALERT_URL, f"/alerts?only_open={str(only_open).lower()}")


@app.patch("/api/v1/alerts/{alert_id}/acknowledge", tags=["Alertas"])
async def acknowledge(alert_id: int, request: Request, _: None = Depends(require_client_key)):
    return await forward(request, "PATCH", config.ALERT_URL, f"/alerts/{alert_id}/acknowledge")
