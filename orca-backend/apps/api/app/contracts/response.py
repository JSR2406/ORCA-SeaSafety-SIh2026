# Canonical OrchestrationResponse contract (Phase 10 - Parts 4, 8-16).
#
# This is the single, versioned, frontend-friendly response shape.  Every field
# is domain-neutral; the frontend never reconstructs meaning from agent/tool
# names or internal messages.
#
# The response is produced by normalizing the internal orchestrator result
# (see normalize.py).  Confidence, risk, restrictions, route blocking and
# safety verdicts all originate from the backend and are only visualized by the
# frontend.
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.contracts.versions import contract_meta


# --- Status contract (Part 5) -------------------------------------------------
class RunStatus(str, Enum):
    ACCEPTED = "accepted"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    FAILED = "failed"
    TIMEOUT = "timeout"


# --- Risk contract (Part 16) ---------------------------------------------------
class RiskClassification(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class RiskContract(BaseModel):
    classification: RiskClassification
    reason: str = ""
    hard_constraint: bool = False
    assessed: bool = True


# --- Confidence contract (Part 15) --------------------------------------------
class ConfidenceLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ConfidenceContract(BaseModel):
    score: float = Field(ge=0, le=1)
    level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    basis: List[str] = Field(default_factory=list)


# --- Evidence contract (Part 13) -----------------------------------------------
class EvidenceType(str, Enum):
    OBSERVATION = "OBSERVATION"
    FORECAST = "FORECAST"
    ADVISORY = "ADVISORY"
    RESTRICTION = "RESTRICTION"
    MODEL = "MODEL"
    DOCUMENT = "DOCUMENT"
    DERIVED = "DERIVED"


class EvidenceItem(BaseModel):
    id: str = ""
    type: EvidenceType = EvidenceType.DERIVED
    source: str = ""
    source_reference: str = ""
    timestamp: Optional[str] = None
    validity: Optional[str] = None
    claim: str = ""
    value: Optional[Any] = None
    unit: Optional[str] = None
    confidence: Optional[float] = None


# --- Provenance contract (Part 14) ---------------------------------------------
class ProvenanceItem(BaseModel):
    source: str = ""
    source_reference: str = ""
    retrieved_at: Optional[str] = None
    observed_at: Optional[str] = None
    freshness: Literal["fresh", "stale", "unknown", "unavailable"] = "unknown"


# --- Map / layer contract (Parts 8-9) ------------------------------------------
class MapGeometry(BaseModel):
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]] = Field(default_factory=list)


class MapContract(BaseModel):
    features: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None


# --- Chart contract (Part 10) ---------------------------------------------------
class ChartSeries(BaseModel):
    id: str
    name: str
    unit: str = ""
    source: str = ""
    timestamps: List[str] = Field(default_factory=list)
    values: List[Any] = Field(default_factory=list)
    validity: Optional[str] = None
    quality: Optional[str] = None
    confidence: Optional[float] = None


# --- Alert contract (Part 11) ---------------------------------------------------
class AlertType(str, Enum):
    WEATHER = "WEATHER"
    CYCLONE = "CYCLONE"
    LIGHTNING = "LIGHTNING"
    WAVE = "WAVE"
    RESTRICTION = "RESTRICTION"
    GEOFENCE = "GEOFENCE"
    ROUTE = "ROUTE"
    DATA_QUALITY = "DATA_QUALITY"


class AlertItem(BaseModel):
    id: str = ""
    type: AlertType = AlertType.DATA_QUALITY
    severity: str = "info"
    title: str = ""
    message: str = ""
    location: Optional[Dict[str, float]] = None
    geometry: Optional[Dict[str, Any]] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    source: str = ""
    confidence: Optional[float] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "active"


# --- Route contract (Part 12) ---------------------------------------------------
class RouteContract(BaseModel):
    status: str = "none"  # none | selected | blocked | unavailable
    selected_geometry: Optional[Dict[str, Any]] = None
    distance_km: Optional[float] = None
    risk: Optional[str] = None
    blocked: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


# --- Needs input (Part 6) -------------------------------------------------------
class Question(BaseModel):
    id: str
    type: Literal["location", "time", "choice", "text"] = "text"
    question: str


class NeedsInputContract(BaseModel):
    questions: List[Question] = Field(default_factory=list)


# --- Canonical response ---------------------------------------------------------
class OrchestrationResponse(BaseModel):
    request_id: str = ""
    run_id: str = ""
    session_id: Optional[str] = None
    status: RunStatus = RunStatus.COMPLETED
    schema_version: str = contract_meta()["response_schema_version"]
    api_version: str = contract_meta()["api_version"]

    language: str = "en"
    answer: str = ""

    confidence: ConfidenceContract = Field(default_factory=ConfidenceContract)
    risk: RiskContract = Field(default_factory=RiskContract)

    needs_input: NeedsInputContract = Field(default_factory=NeedsInputContract)

    evidence: List[EvidenceItem] = Field(default_factory=list)
    provenance: List[ProvenanceItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    map: MapContract = Field(default_factory=MapContract)
    charts: List[ChartSeries] = Field(default_factory=list)
    alerts: List[AlertItem] = Field(default_factory=list)
    route: RouteContract = Field(default_factory=RouteContract)

    execution: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
