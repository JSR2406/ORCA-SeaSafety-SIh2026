# Canonical Tide contract.
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.models.common import QualityStatus, utcnow


class TideType(str, Enum):
    HIGH = "high"
    LOW = "low"


class TidePrediction(BaseModel):
    """Predicted or observed tide event at a location.

    Prediction is the norm for tide products; observed confirms actuals.
    """
    location_name: Optional[str] = None
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    event_time: datetime  # when the tide event occurs
    tide_height_m: Optional[float] = None
    tide_type: TideType
    is_prediction: bool = True
    source_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=utcnow)

    source: str
    source_record_id: Optional[str] = None
    quality: QualityStatus = QualityStatus.VALID
    raw_payload: Optional[dict] = None