# Common canonical contracts shared across the marine data layer.
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Timezone-aware UTC now (single convention used across the data layer)."""
    return datetime.now(timezone.utc)


class QualityStatus(str, Enum):
    """Classification of data quality for a record or individual field."""
    VALID = "valid"
    SUSPICIOUS = "suspicious"
    INVALID = "invalid"
    MISSING = "missing"


class DataStatus(str, Enum):
    """Presentation status for data returned to consumers.

    - LIVE: fetched within freshness threshold
    - RECENT: valid but older than threshold (still usable, flagged)
    - STALE: last valid data present but older than threshold
    - UNAVAILABLE: no data for the query
    - NOT_CONFIGURED: source has no credentials/endpoint configured
    - ERROR: query/ingestion error
    - TEST_MOCK: synthetic/sample data used for evaluation only (never LIVE)
    """
    LIVE = "live"
    RECENT = "recent"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"
    TEST_MOCK = "test_mock"


class GeographicPoint(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class QualityReport(BaseModel):
    """Per-field quality classification with reasons."""
    field: str
    status: QualityStatus
    reason: Optional[str] = None