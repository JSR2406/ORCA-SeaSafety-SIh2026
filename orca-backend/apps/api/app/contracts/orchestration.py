# Orchestration request contract (Phase 10 - Part 3).
#
# The frontend sends intent-neutral natural language plus optional structured
# context.  It must NOT send planner/task/agent structures - the backend owns
# intent -> planning -> agent selection -> tool selection -> execution.
from enum import Enum
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings


class LocationSource(str, Enum):
    """How a location was established.  Authoritative resolution is backend-side."""
    USER = "USER"
    GPS = "GPS"
    MAP = "MAP"
    RESOLVED_PLACE = "RESOLVED_PLACE"
    SYSTEM = "SYSTEM"


class UserLocation(BaseModel):
    """Structured location the frontend may attach to a request."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: Optional[float] = Field(default=None, ge=0)
    timestamp: Optional[str] = None
    source: LocationSource = LocationSource.USER


class RouteRequest(BaseModel):
    """Optional structured route request (additive convenience)."""
    origin_latitude: float = Field(ge=-90, le=90)
    origin_longitude: float = Field(ge=-180, le=180)
    destination_latitude: float = Field(ge=-90, le=90)
    destination_longitude: float = Field(ge=-180, le=180)
    waypoints: Optional[List[Dict[str, float]]] = None

    @field_validator("waypoints")
    @classmethod
    def _cap_waypoints(cls, v):
        if v is not None and len(v) > 50:
            raise ValueError("too many waypoints (max 50)")
        return v


class ScenarioRequest(BaseModel):
    """Optional structured scenario request (additive convenience)."""
    description: str = ""
    options: Optional[List[str]] = None
    max_options: int = Field(default=5, ge=1, le=10)


class OrchestrationRequest(BaseModel):
    """Canonical request body for POST /api/v1/orchestrate.

    All fields are optional except `query` (or legacy `message`).  The backend
    detects language and resolves locations when they are not supplied.
    """
    query: Optional[str] = None
    message: Optional[str] = None
    language: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    user_location: Optional[UserLocation] = None
    context: Optional[Dict[str, Any]] = None
    requested_outputs: Optional[List[str]] = None
    route_request: Optional[RouteRequest] = None
    scenario_request: Optional[ScenarioRequest] = None
    request_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coalesce_query_and_message(cls, data):
        if isinstance(data, dict):
            q = data.get("query") or data.get("message")
            if q:
                data["query"] = q
                data["message"] = q
        return data

    @model_validator(mode="after")
    def _require_query_or_message(self):
        if not self.query and not self.message:
            raise ValueError("query is required (or legacy alias 'message')")
        return self

    @field_validator("query")
    @classmethod
    def _validate_query(cls, v):
        if v is None or not str(v).strip():
            raise ValueError("query is required")
        if len(v) > settings.orchestrator_max_message_chars:
            raise ValueError(
                f"query exceeds {settings.orchestrator_max_message_chars} characters")
        return v

    @field_validator("requested_outputs")
    @classmethod
    def _validate_outputs(cls, v):
        allowed = {"text", "map", "charts", "alerts", "route", "evidence",
                   "history"}
        if v is None:
            return v
        bad = [o for o in v if o not in allowed]
        if bad:
            raise ValueError(f"unsupported requested_outputs: {bad}")
        return v
