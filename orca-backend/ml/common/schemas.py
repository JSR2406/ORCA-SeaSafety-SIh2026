"""Typed contracts for ORCA ML foundation.

Training data = historical rows used to learn patterns.
Real-time data = current/forecast rows used as today's model input.
Feature lists at inference MUST match training exactly (see FISHING_FEATURES / RISK_FEATURES).
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

SourceName = Literal["INCOIS", "IMD", "ISRO", "OPEN_METEO", "GFW", "MOSDAC", "BASELINE"]


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class MarineObservation(BaseModel):
    """Normalized real-time/historical observation. Every record carries source + times."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    valid_time: datetime
    retrieval_time: datetime = Field(default_factory=datetime.utcnow)
    source: SourceName = "BASELINE"
    quality: Literal["ok", "suspect", "missing"] = "ok"
    sst_c: Optional[float] = None
    chlorophyll: Optional[float] = None
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    current_speed_ms: Optional[float] = None
    current_direction_deg: Optional[float] = None
    visibility_km: Optional[float] = None
    rain_mm: Optional[float] = None


class MarineForecast(MarineObservation):
    lead_hours: float = 0.0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


FISHING_FEATURES: List[str] = [
    "lat", "lon", "sst_c", "chlorophyll",
    "wind_speed_ms", "wind_direction_deg",
    "current_speed_ms", "current_direction_deg",
    "wave_height_m", "depth_m", "distance_from_coast_km",
    "month", "season_idx", "hour",
]

RISK_FEATURES: List[str] = [
    "wave_height_m", "wave_period_s", "wind_speed_ms",
    "current_speed_ms", "visibility_km", "rain_mm",
    "sst_c", "cyclone_distance_km", "lightning_flag",
    "month", "hour", "forecast_uncertainty",
]


class FishingFeatureVector(BaseModel):
    lat: float
    lon: float
    sst_c: float
    chlorophyll: float
    wind_speed_ms: float = 0.0
    wind_direction_deg: float = 0.0
    current_speed_ms: float = 0.0
    current_direction_deg: float = 0.0
    wave_height_m: float = 0.0
    depth_m: float = 30.0
    distance_from_coast_km: float = 10.0
    month: int = Field(default=1, ge=1, le=12)
    season_idx: int = Field(default=0, ge=0, le=3)
    hour: int = Field(default=6, ge=0, le=23)

    def ordered(self) -> List[float]:
        return [float(getattr(self, k)) for k in FISHING_FEATURES]


class RiskFeatureVector(BaseModel):
    wave_height_m: float = 0.0
    wave_period_s: float = 8.0
    wind_speed_ms: float = 0.0
    current_speed_ms: float = 0.0
    visibility_km: float = 10.0
    rain_mm: float = 0.0
    sst_c: float = 28.0
    cyclone_distance_km: float = 9999.0
    lightning_flag: int = Field(default=0, ge=0, le=1)
    month: int = Field(default=1, ge=1, le=12)
    hour: int = Field(default=6, ge=0, le=23)
    forecast_uncertainty: float = Field(default=0.2, ge=0.0, le=1.0)

    def ordered(self) -> List[float]:
        return [float(getattr(self, k)) for k in RISK_FEATURES]


class ModelPrediction(BaseModel):
    model: str
    version: str
    probability: float = Field(..., ge=0.0, le=1.0)
    label: Optional[str] = None
    top_positive_features: List[str] = Field(default_factory=list)
    top_negative_features: List[str] = Field(default_factory=list)
    feature_values: Dict[str, Any] = Field(default_factory=dict)
    calibration: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    source: str
    title: str = ""
    content: str = ""
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_time: Optional[datetime] = None
