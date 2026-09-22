# Schemas Package
from app.schemas.query import (
    StructuredQuery,
    Intent,
    Region,
    BBoxRegion,
    RadiusRegion,
    NamedRegion,
    SupportedLanguage,
    QualityFilter,
    Aggregation,
    Variable,
    QueryPlanRequest,
    QueryPlanResponse,
)

from app.schemas.evidence import (
    EvidenceRecord,
    ConfidenceScore,
    ConfidenceComponents,
    NumericClaim,
    VerificationResult,
)

from app.schemas.provenance import (
    EvidenceBundle,
    DataFreshness,
)

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatMode,
    Visualizations,
    ChartVisualizationData,
    MapVisualizationData,
    VoiceTranscribeRequest,
    VoiceTranscribeResponse,
    VoiceSynthesizeRequest,
    VoiceSynthesizeResponse,
)

from app.schemas.risk import (
    RiskComponent,
    RiskBriefingResponse,
)

from app.schemas.scenario import (
    ScenarioType,
    ScenarioParameter,
    ScenarioRequest,
    ScenarioResult,
    ScenarioComparison,
    AlertSeverity,
    AlertStatus,
    AlertRule,
    AlertEvent,
)

from app.schemas.provenance import (
    EvidenceBundle,
    ProvenanceRecord,
    SourceType,
    DataFreshness,
    SourceHealth,
    ProvenanceQuery,
    GeoJSONGeometry,
    EvidenceBundle as ProvenanceEvidenceBundle,
)

from app.schemas.route import (
    RouteAnalysisRequest,
    RouteAnalysisResponse,
    RouteMode,
    VesselType,
    EnvironmentalConditions,
    HazardIntersection,
    GeofenceIntersection,
    RouteSegment,
    RiskAssessment,
)

from app.schemas.marine import (
    MarineConditionRequest,
    MarineConditionResponse,
    MarineConditionType,
    MarineHazard,
    MarineForecast,
    MarineConditions,
)

from app.schemas.hazard import (
    HazardType,
    HazardSeverity,
    HazardArea,
    HazardWarning,
    HazardComparison,
    HazardReport,
)

__all__ = [
    # Query
    "StructuredQuery",
    "Intent",
    "Region",
    "BBoxRegion",
    "RadiusRegion",
    "NamedRegion",
    "SupportedLanguage",
    "QualityFilter",
    "Aggregation",
    "Variable",
    "QueryPlanRequest",
    "QueryPlanResponse",
    # Evidence
    "EvidenceRecord",
    "ConfidenceScore",
    "ConfidenceComponents",
    "NumericClaim",
    "VerificationResult",
    "EvidenceBundle",
    "DataFreshness",
    # Chat
    "ChatRequest",
    "ChatResponse",
    "ChatMode",
    "Visualizations",
    "ChartVisualizationData",
    "MapVisualizationData",
    "VoiceTranscribeRequest",
    "VoiceTranscribeResponse",
    "VoiceSynthesizeRequest",
    "VoiceSynthesizeResponse",
    # Risk
    "RiskComponent",
    "RiskBriefingResponse",
    # Scenario
    "ScenarioType",
    "ScenarioParameter",
    "ScenarioRequest",
    "ScenarioResult",
    "ScenarioComparison",
    "AlertSeverity",
    "AlertStatus",
    "AlertRule",
    "AlertEvent",
    # Provenance
    "ProvenanceEvidenceBundle",
    "ProvenanceRecord",
    "SourceType",
    "DataFreshness",
    "SourceHealth",
    "ProvenanceQuery",
    "GeoJSONGeometry",
    # Route
    "RouteAnalysisRequest",
    "RouteAnalysisResponse",
    "RouteMode",
    "VesselType",
    "EnvironmentalConditions",
    "HazardIntersection",
    "GeofenceIntersection",
    "RouteSegment",
    "RiskAssessment",
    # Marine
    "MarineConditionRequest",
    "MarineConditionResponse",
    "MarineConditionType",
    "MarineHazard",
    "MarineForecast",
    "MarineConditions",
    # Hazard
    "HazardType",
    "HazardSeverity",
    "HazardArea",
    "HazardWarning",
    "HazardComparison",
    "HazardReport",
]