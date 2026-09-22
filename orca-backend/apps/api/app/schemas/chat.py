# API Schemas - Chat
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from app.schemas.evidence import EvidenceRecord
from app.schemas.query import StructuredQuery, Intent


class ChatMode(str, Enum):
    FISHERFOLK = "fisherfolk"
    RESEARCHER = "researcher"


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    language: Optional[str] = None
    mode: ChatMode = ChatMode.RESEARCHER
    context: Dict[str, Any] = Field(default_factory=dict)


class ChartType(str, Enum):
    DEPTH_PROFILE = "depth_profile"
    TIME_SERIES = "time_series"
    ANOMALY = "anomaly"
    SCENARIO = "scenario"
    COMPARISON = "comparison"
    HISTOGRAM = "histogram"


class ChartSeries(BaseModel):
    key: str
    label: str
    color: Optional[str] = None


class ChartConfig(BaseModel):
    xAxis: Dict[str, Any]
    yAxis: Dict[str, Any]
    series: Optional[List[ChartSeries]] = None


class ChartMetadata(BaseModel):
    variable: str
    region: str
    time_range: str
    depth_range: Optional[str] = None
    sample_count: int
    float_count: int
    data_source: str


class ChartDataPoint(BaseModel):
    x: float | str
    y: float
    label: Optional[str] = None
    group: Optional[str] = None
    sample_count: Optional[int] = None
    claim_id: Optional[str] = None


class ChartVisualizationData(BaseModel):
    type: ChartType
    title: str
    data: List[ChartDataPoint]
    config: ChartConfig
    metadata: ChartMetadata


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class MapVisualizationData(BaseModel):
    type: Literal["geojson"] = "geojson"
    features: List[GeoJSONFeature]
    center: List[float]  # [lon, lat]
    zoom: int


class Visualizations(BaseModel):
    map: Optional[MapVisualizationData] = None
    charts: List[ChartVisualizationData] = Field(default_factory=list)


class ChatResponse(BaseModel):
    query_run_id: str
    answer: str
    language: str
    structured_query: Optional[StructuredQuery] = None
    visualizations: Optional[Visualizations] = None
    evidence: Optional[EvidenceRecord] = None
    audio_url: Optional[str] = None
    status: Literal["success", "needs_clarification", "unavailable", "error"] = "success"
    clarification_question: Optional[str] = None
    partial_query: Optional[StructuredQuery] = None


class VoiceTranscribeRequest(BaseModel):
    language_hint: Optional[str] = None


class VoiceTranscribeResponse(BaseModel):
    transcript: str
    language: str
    confidence: float
    duration_seconds: float


class VoiceSynthesizeRequest(BaseModel):
    text: str
    language: str
    voice: Optional[str] = None


class VoiceSynthesizeResponse(BaseModel):
    audio_url: str
    duration_seconds: float
    format: str = "mp3"


class ProfileSearchRequest(BaseModel):
    region: Dict[str, Any]
    time_range: Optional[Dict[str, str]] = None
    depth_range_m: Optional[Dict[str, float]] = None
    variables: Optional[List[str]] = None
    quality_filter: str = "recommended"
    limit: int = 200


class ProfileSearchResponse(BaseModel):
    profiles: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class AnomalyDetectRequest(BaseModel):
    variable: str
    region: Dict[str, Any]
    depth_m: float
    reference_period: Dict[str, str]
    analysis_period: Dict[str, str]
    threshold_std: float = 2.0


class AnomalyDetectResponse(BaseModel):
    anomaly_detected: bool
    variable: str
    depth_m: float
    region: Dict[str, Any]
    reference_baseline: Dict[str, Any]
    analysis_period: Dict[str, Any]
    difference: float
    difference_std: float
    threshold_exceeded: bool
    affected_locations: List[Dict[str, Any]]
    confidence: Dict[str, Any]
    limitations: List[str]


class ScenarioProjectRequest(BaseModel):
    variable: str
    region: Dict[str, Any]
    depth_m: float
    trend_window: Dict[str, str]
    projection_years: int
    model: str = "linear_trend"
    assumptions: List[str] = Field(default_factory=list)


class ScenarioProjectResponse(BaseModel):
    scenario: Dict[str, Any]


class RiskBriefingRequest(BaseModel):
    origin: Dict[str, float]
    destination: Optional[Dict[str, float]] = None
    distance_km: Optional[float] = None
    departure_time: str
    vessel_type: str
    include_forecast: bool = True


class RiskComponent(BaseModel):
    name: str
    label: Literal["low", "moderate", "elevated", "unavailable"]
    reason: str
    source: str
    data_freshness: str


class RiskBriefingResponse(BaseModel):
    overall_label: Literal["low", "moderate", "elevated", "unavailable"]
    components: List[RiskComponent]
    confidence: Dict[str, Any]
    advisory: str
    data_status: Literal["complete", "partial", "unavailable"]
    latest_data_timestamp: str


class CSVExportRequest(BaseModel):
    query_run_id: str
    format: Literal["profiles", "observations", "summary"] = "profiles"


class DatasetStatusResponse(BaseModel):
    datasets: List[Dict[str, Any]]


class QueryRunDetailResponse(BaseModel):
    id: str
    session_id: str
    user_input: str
    detected_language: Optional[str]
    normalized_intent: Optional[str]
    structured_query: StructuredQuery
    tool_calls: List[Dict[str, Any]]
    execution_status: str
    created_at: str
    evidence: Optional[EvidenceRecord] = None
    narratives: List[Dict[str, Any]] = Field(default_factory=list)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    database: Literal["connected", "disconnected"]
    timestamp: str