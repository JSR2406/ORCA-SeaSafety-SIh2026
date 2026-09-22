# Standard structured result envelope returned by the marine data layer.
# Used by both the API routers and the Phase 2 MCP tools so consumers see a
# consistent shape: status / data / source / timestamps / freshness / provenance.
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.common import DataStatus, utcnow
from app.models.source import SourceStatus


class ProvenanceEntry(BaseModel):
    """Provenance for a single data element (source + primary key)."""
    source: str
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    observation_time: Optional[datetime] = None


class Freshness(BaseModel):
    """Freshness evaluation for the returned data."""
    threshold_seconds: Optional[int] = None
    age_seconds: Optional[float] = None
    latest_data_timestamp: Optional[datetime] = None
    is_within_threshold: bool = True


class QueryTimes(BaseModel):
    """Timestamps describing the request and the data returned."""
    requested_at: datetime = Field(default_factory=utcnow)
    data_timestamp: Optional[datetime] = None
    source_timestamp: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None


class MarineDataResult(BaseModel):
    """Uniform envelope for all marine data queries.

    status semantics:
    - LIVE             data within freshness threshold
    - RECENT           data present but older than threshold
    - STALE            data present well beyond threshold (flagged)
    - UNAVAILABLE      query valid but no data exists
    - NOT_CONFIGURED   source not configured (no credentials/endpoint)
    - ERROR            query failed (invalid input / dependency failure)
    """
    status: DataStatus = DataStatus.UNAVAILABLE
    data: Any = None
    sources: List[str] = Field(default_factory=list)
    timestamps: QueryTimes = Field(default_factory=QueryTimes)
    freshness: Optional[Freshness] = None
    provenance: List[ProvenanceEntry] = Field(default_factory=list)
    source_status: Optional[List[SourceStatus]] = None
    warnings: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    error: Optional[str] = None


def unavailable_result(
    reason: str = "No data available for the requested parameters.",
    sources: Optional[List[str]] = None,
) -> MarineDataResult:
    return MarineDataResult(
        status=DataStatus.UNAVAILABLE,
        data=None,
        sources=sources or [],
        warnings=[reason],
    )


def not_configured_result(source: str) -> MarineDataResult:
    return MarineDataResult(
        status=DataStatus.NOT_CONFIGURED,
        data=None,
        sources=[source],
        warnings=[f"Source '{source}' is not configured (no credentials/endpoint provided)."],
    )


def error_result(error: str, sources: Optional[List[str]] = None) -> MarineDataResult:
    return MarineDataResult(
        status=DataStatus.ERROR,
        data=None,
        sources=sources or [],
        error=error,
    )