# Source metadata, capability and freshness contracts.
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.common import DataStatus, utcnow


class SourceType(str, Enum):
    INCOIS = "incois"
    IMD = "imd"
    MOSDAC = "mosdac"
    ARGO = "argo"
    OPEN_METEO = "open_meteo"
    OPEN_WEATHER = "open_weather"
    STORM_GLASS = "storm_glass"
    COASTWATCH = "coastwatch"
    JTWC = "jtwc"
    GDACS = "gdacs"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class SourceCapability(BaseModel):
    """A data product a source can provide."""
    name: str
    description: str
    data_product: str  # e.g. "ocean_waves", "weather_forecast", "pfz", "warnings"
    config_required: bool = False


class SourceInfo(BaseModel):
    """Static description of a marine data source."""
    name: str
    source_type: SourceType
    display_name: str
    base_url: str
    enabled: bool
    capabilities: List[SourceCapability] = Field(default_factory=list)


class SourceAvailability(BaseModel):
    """Runtime availability state of a source (as configured / last fetched)."""
    source: str
    configured: bool
    connected: bool = False
    last_successful_fetch: Optional[datetime] = None
    latest_data_timestamp: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    message: str = ""


class SourceStatus(BaseModel):
    """Freshness-aware source status exposed to consumers."""
    source: str
    source_type: SourceType
    status: DataStatus
    configured: bool
    connected: bool
    last_successful_fetch: Optional[datetime] = None
    latest_data_timestamp: Optional[datetime] = None
    threshold_seconds: Optional[int] = None
    age_seconds: Optional[float] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    message: str = ""
    evaluated_at: datetime = Field(default_factory=utcnow)