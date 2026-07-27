from datetime import datetime

from pydantic import BaseModel, Field


class TelemetryInput(BaseModel):
    sensor_id: str = Field(min_length=2, max_length=80, examples=["solo-talhao-01"])
    metric: str = Field(min_length=2, max_length=40, examples=["soil_moisture"])
    value: float = Field(examples=[18.0])
    unit: str = Field(min_length=1, max_length=12, examples=["%"])
    location: str = Field(min_length=2, max_length=100, examples=["Talhão Norte"])


class TelemetryRecord(TelemetryInput):
    id: int
    received_at: datetime


class AlertRecord(BaseModel):
    id: int
    telemetry_id: int
    sensor_id: str
    metric: str
    value: float
    severity: str
    message: str
    created_at: datetime
    acknowledged: bool
