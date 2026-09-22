# Provenance Schemas
# Canonical EvidenceBundle and source traceability contracts

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


class SourceType(str, Enum):
    ARGO = "argo"
    WEATHER = "weather"
    WAVE = "wave"
    CURRENT = "current"
    SATELLITE = "satellite"
    HAZARD = "hazard"
    GEOFENCE = "geofence"
    FORECAST = "forecast"
    CLIMATOLOGY = "climatology"
    REANALYSIS = "reanalysis"
    DEMO = "demo"


class DataFreshness(BaseModel):
    latest_profile: Optional[datetime] = None
    days_old: Optional[int] = None
    source: Literal["argo_realtime", "argo_delayed", "climatology", "reanalysis", "demo", "forecast", "live"]


class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "LineString", "Polygon", "MultiPolygon", "Feature", "FeatureCollection"]
    coordinates: Any = None
    geometry: Any = None  # For nested geometries
    properties: Optional[Dict[str, Any]] = None
    features: Optional[List["GeoJSONGeometry"]] = None  # For FeatureCollection


class EvidenceBundle(BaseModel):
    """Canonical internal structure for all evidence from any source."""
    
    source_id: str
    source_type: SourceType
    source_name: str
    source_url: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    geographic_scope: Optional[GeoJSONGeometry] = None
    variables: List[str] = Field(default_factory=list)
    measurements: Dict[str, Any] = Field(default_factory=dict)
    units: Dict[str, str] = Field(default_factory=dict)
    quality_flags: Dict[str, Any] = Field(default_factory=dict)
    freshness: Optional[DataFreshness] = None
    confidence: float = Field(ge=0, le=1, default=0.5)
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Processing trace
    processing_steps: List[str] = Field(default_factory=list)
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None


class ProvenanceRecord(BaseModel):
    """Immutable record of data lineage for audit."""
    
    id: str
    source_bundle: EvidenceBundle
    transformation: Optional[str] = None  # e.g., "spatial_join", "temporal_aggregation"
    parent_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str  # agent or service name
    checksum: Optional[str] = None


class SourceHealth(BaseModel):
    """Health status of a data provider."""
    
    source_id: str
    source_type: SourceType
    status: Literal["healthy", "degraded", "unavailable", "unknown"]
    last_successful_fetch: Optional[datetime] = None
    last_error: Optional[str] = None
    latency_ms: Optional[int] = None
    data_freshness_hours: Optional[float] = None
    rate_limit_remaining: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ProvenanceQuery(BaseModel):
    """Query for retrieving provenance information."""
    
    query_run_id: Optional[str] = None
    source_ids: Optional[List[str]] = None
    source_types: Optional[List[SourceType]] = None
    time_range: Optional[Dict[str, datetime]] = None
    geographic_scope: Optional[GeoJSONGeometry] = None


# Update forward references
GeoJSONGeometry.model_rebuild()