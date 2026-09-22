# Canonical Weather contract (observations + forecasts).
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.common import QualityStatus, utcnow


class WeatherObservation(BaseModel):
    """Observed weather at a location and valid time."""
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    valid_time: datetime  # when the observation represents
    source_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=utcnow)

    temperature_c: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    precipitation_mm: Optional[float] = None
    pressure_hpa: Optional[float] = None
    humidity_pct: Optional[float] = None
    visibility_m: Optional[float] = None
    lightning: Optional[bool] = None
    condition: Optional[str] = None

    source: str
    source_record_id: Optional[str] = None
    quality: QualityStatus = QualityStatus.VALID
    raw_payload: Optional[dict] = None


class WeatherForecast(BaseModel):
    """Weather forecast valid over [valid_from, valid_until).

    Temporal semantics:
    - issue_time: when the forecast was issued
    - valid_from/valid_until: validity window of the forecast
    """
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    issue_time: datetime
    valid_from: datetime
    valid_until: datetime
    forecast_horizon_h: Optional[float] = None
    source_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=utcnow)

    temperature_c: Optional[float] = None
    temperature_min_c: Optional[float] = None
    temperature_max_c: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    precipitation_mm: Optional[float] = None
    pressure_hpa: Optional[float] = None
    humidity_pct: Optional[float] = None
    visibility_m: Optional[float] = None
    lightning: Optional[bool] = None
    condition: Optional[str] = None

    source: str
    source_record_id: Optional[str] = None
    quality: QualityStatus = QualityStatus.VALID
    raw_payload: Optional[dict] = None