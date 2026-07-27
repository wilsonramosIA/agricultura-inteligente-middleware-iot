import os


def value(name: str, default: str) -> str:
    return os.getenv(name, default)


CLIENT_API_KEY = value("CLIENT_API_KEY", "grupo8-demo-key")
INTERNAL_API_KEY = value("INTERNAL_API_KEY", "grupo8-internal-key")
TELEMETRY_URL = value("TELEMETRY_URL", "http://localhost:8001")
ALERT_URL = value("ALERT_URL", "http://localhost:8002")
TIMEOUT_SECONDS = float(value("SERVICE_TIMEOUT_SECONDS", "3"))
TELEMETRY_DB_PATH = value("TELEMETRY_DB_PATH", "data/telemetry.db")
ALERT_DB_PATH = value("ALERT_DB_PATH", "data/alerts.db")

