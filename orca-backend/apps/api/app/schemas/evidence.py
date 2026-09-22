# API Schemas - Evidence/Provenance
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceComponents(BaseModel):
    spatial_coverage: float = Field(ge=0, le=1)
    temporal_freshness: float = Field(ge=0, le=1)
    sample_density: float = Field(ge=0, le=1)
    measurement_quality: float = Field(ge=0, le=1)
    method_stability: float = Field(ge=0, le=1)


class ConfidenceScore(BaseModel):
    label: ConfidenceLabel
    score: float = Field(ge=0, le=1)
    components: ConfidenceComponents
    explanation: str
    limitations: List[str] = Field(default_factory=list)


class DataFreshness(BaseModel):
    latest_profile: str  # ISO 8601
    days_old: int = Field(ge=0)
    source: Literal["argo_realtime", "argo_delayed", "climatology", "reanalysis", "demo"]


class RegionInfo(BaseModel):
    type: str
    name: Optional[str] = None
    min_lat: Optional[float] = None
    max_lat: Optional[float] = None
    min_lon: Optional[float] = None
    max_lon: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: Optional[float] = None


class DepthRangeInfo(BaseModel):
    min: float
    max: float


class TimeRangeInfo(BaseModel):
    start: str
    end: str


class QualityFiltersInfo(BaseModel):
    filters: List[str]
    description: str


class SourceIdentifiers(BaseModel):
    dataset: str
    snapshot: str
    doi: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)


class QueryStep(BaseModel):
    step: int
    tool: str
    params: Dict[str, Any]
    result_count: int
    duration_ms: Optional[int] = None


class EvidenceRecord(BaseModel):
    float_ids: List[int] = Field(default_factory=list)
    profile_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    region: RegionInfo
    depth_range_m: Optional[DepthRangeInfo] = None
    time_range: TimeRangeInfo
    quality_filters: QualityFiltersInfo
    data_freshness: DataFreshness
    confidence: ConfidenceScore
    query_steps: List[QueryStep] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    source_identifiers: SourceIdentifiers
    verified: bool = False
    verification_errors: Optional[List[str]] = None


class NumericClaim(BaseModel):
    claim: str
    value: float | str
    unit: str
    claim_id: str
    source: Literal["measurement", "aggregation", "comparison", "projection", "climatology"]
    verified: bool


class VerificationResult(BaseModel):
    all_verified: bool
    claims: List[NumericClaim]
    failed_claims: List[NumericClaim]
    summary: str