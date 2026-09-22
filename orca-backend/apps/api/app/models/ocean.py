# Canonical Ocean Conditions contract.
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.common import QualityStatus, utcnow


class OceanConditions(BaseModel):
    """Normalized, source-agnostic ocean condition observation.

    Temporal semantics:
    - observation_time: when the physical condition was observed
    - source_timestamp: timestamp reported by the upstream source
    - ingested_at: when this system received/stored it
    """
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    observation_time: datetime
    source_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=utcnow)

    sst_c: Optional[float] = None
    chlorophyll: Optional[float] = None
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    wave_direction_deg: Optional[float] = None
    current_speed_ms: Optional[float] = None
    current_direction_deg: Optional[float] = None
    salinity_psu: Optional[float] = None

    source: str
    source_record_id: Optional[str] = None
    quality: QualityStatus = QualityStatus.VALID
    raw_payload: Optional[dict] = None