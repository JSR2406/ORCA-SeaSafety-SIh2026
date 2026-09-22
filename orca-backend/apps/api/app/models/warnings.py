# Canonical Marine Warnings + Restricted Areas contracts.
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.common import utcnow


class WarningSeverity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class WarningType(str, Enum):
    CYCLONE = "cyclone"
    STORM_WARNING = "storm_warning"
    FISHING_WARNING = "fishing_warning"
    NAVIGATIONAL_WARNING = "navigational_warning"
    RESTRICTION = "restriction"
    OTHER = "other"


class RestrictionKind(str, Enum):
    """Permanent vs temporary maritime restrictions."""
    PERMANENT = "permanent"
    TEMPORARY = "temporary"


class RestrictionType(str, Enum):
    EEZ = "eez"
    IMBL = "imbl"
    MPA = "mpa"                        # Marine Protected Area
    ECOLOGICAL_ZONE = "ecological_zone"
    NAVAL_EXERCISE = "naval_exercise"
    FIRING_EXERCISE = "firing_exercise"
    SUBMARINE_OP = "submarine_operation"
    DANGER_AREA = "danger_area"
    BOUNDARY = "marine_boundary"
    OTHER = "other"


class WarningStatus(str, Enum):
    ACTIVE = "active"
    UPCOMING = "upcoming"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


# Statuses that never bind a route / query.  Expired and cancelled advisories
# are authoritative *closures* that must not remain in the active view.
NON_BINDING_STATUSES = frozenset({
    WarningStatus.EXPIRED,
    WarningStatus.CANCELLED,
    WarningStatus.UNKNOWN,
})


def evaluate_window_status(valid_from: Optional[datetime],
                           valid_until: Optional[datetime],
                           at: Optional[datetime] = None) -> WarningStatus:
    """Evaluate a validity window against a reference time.

    A restriction/warning is ACTIVE at time T if T is inside [valid_from, valid_until).
    UPCOMING if the window starts in the future; EXPIRED if it ended in the past.
    If no window is given, UNKNOWN (assume active is *not* proven).
    """
    t = at or utcnow()
    if valid_from is None and valid_until is None:
        return WarningStatus.UNKNOWN
    if valid_from is not None and t < valid_from:
        return WarningStatus.UPCOMING
    if valid_until is not None and t >= valid_until:
        return WarningStatus.EXPIRED
    return WarningStatus.ACTIVE


class MarineWarning(BaseModel):
    """A temporary maritime warning (cyclone, storm, nav warning, ...)."""
    warning_id: str
    warning_type: WarningType
    severity: WarningSeverity
    geometry: Dict  # GeoJSON geometry
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    description: str = ""
    status: Optional[WarningStatus] = None  # evaluated at query time
    source: str
    source_record_id: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=utcnow)


class RestrictedArea(BaseModel):
    """Permanent or temporary restricted marine area (EEZ, MPA, exercise zone...)."""
    area_id: str
    area_name: str
    restriction_kind: RestrictionKind
    restriction_type: RestrictionType
    severity: WarningSeverity = WarningSeverity.MODERATE
    geometry: Dict  # GeoJSON geometry
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: Optional[WarningStatus] = None  # evaluated at query time
    description: str = ""
    source: str
    source_record_id: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=utcnow)