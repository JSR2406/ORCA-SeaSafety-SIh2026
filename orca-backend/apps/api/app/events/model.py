# Phase 11 - normalized marine event model.
#
# A MarineEvent is the atomic record of a *meaningful change* in the marine /
# weather / safety picture.  Change detection decides whether a new observation
# or source message is new / changed / unchanged / corrected / expired /
# recovered / failed, and only *changed/normalized* conditions emit an event.
# Idempotent by construction: the same physical change always produces the same
# event_id (a stable content hash), so replaying a source never duplicates.
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MarineEventType(str, Enum):
    NEW_OBSERVATION = "NEW_OBSERVATION"
    DATA_CHANGED = "DATA_CHANGED"
    DATA_CORRECTED = "DATA_CORRECTED"
    WEATHER_HAZARD = "WEATHER_HAZARD"
    LIGHTNING = "LIGHTNING"
    CYCLONE = "CYCLONE"
    HIGH_WAVE = "HIGH_WAVE"
    HIGH_WIND = "HIGH_WIND"
    RESTRICTION_ACTIVATED = "RESTRICTION_ACTIVATED"
    RESTRICTION_UPDATED = "RESTRICTION_UPDATED"
    RESTRICTION_EXPIRED = "RESTRICTION_EXPIRED"
    GEOFENCE_APPROACH = "GEOFENCE_APPROACH"
    GEOFENCE_ENTRY = "GEOFENCE_ENTRY"
    GEOFENCE_EXIT = "GEOFENCE_EXIT"
    PFZ_UPDATE = "PFZ_UPDATE"
    FORECAST_CHANGE = "FORECAST_CHANGE"
    SOURCE_FAILURE = "SOURCE_FAILURE"
    SOURCE_RECOVERY = "SOURCE_RECOVERY"
    # Phase 13 - continuous learning / governance lifecycle.
    MODEL_DRIFT = "MODEL_DRIFT"
    MODEL_PERFORMANCE_DEGRADED = "MODEL_PERFORMANCE_DEGRADED"
    GROUND_TRUTH_AVAILABLE = "GROUND_TRUTH_AVAILABLE"
    RETRAINING_REQUIRED = "RETRAINING_REQUIRED"
    MODEL_CANDIDATE_CREATED = "MODEL_CANDIDATE_CREATED"
    MODEL_VALIDATION_FAILED = "MODEL_VALIDATION_FAILED"
    MODEL_PROMOTED = "MODEL_PROMOTED"
    MODEL_ROLLBACK = "MODEL_ROLLBACK"
    DATA_DRIFT_DETECTED = "DATA_DRIFT_DETECTED"
    PREDICTION_DRIFT_DETECTED = "PREDICTION_DRIFT_DETECTED"


# Change-detection result vocabulary.
class ChangeState(str, Enum):
    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    CORRECTED = "corrected"
    EXPIRED = "expired"
    RECOVERED = "recovered"
    FAILED = "failed"


class EventSeverity(str, Enum):
    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


def stable_event_id(event_type: MarineEventType, source: str,
                    stable_key: str, previous_state: Any = None,
                    current_state: Any = None) -> str:
    """Deterministic event id from the physical change.

    The same (type, source, key, current_state) ALWAYS yields the same id, so
    re-emitting an unchanged message is idempotent at the event layer.
    previous_state is excluded from the hash so a re-emit that only touches the
    timestamp/from-value does not fork the event family.
    """
    canonical = __import__("json").dumps(
        current_state, sort_keys=True, default=str) if current_state is not None else ""
    raw = f"{event_type.value}|{source}|{stable_key}|{canonical}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


@dataclass
class MarineEvent:
    event_id: str
    event_type: MarineEventType
    source: str
    timestamp: datetime
    location: Optional[Dict[str, float]] = None     # {"lat", "lon"}
    geometry: Optional[Dict[str, Any]] = None        # GeoJSON geometry
    severity: EventSeverity = EventSeverity.INFO
    previous_state: Any = None
    current_state: Any = None
    validity: Optional[Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    change_state: ChangeState = ChangeState.NEW

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = stable_event_id(
                self.event_type, self.source,
                self.metadata.get("stable_key", "event"),
                current_state=self.current_state)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "location": self.location,
            "geometry": self.geometry,
            "severity": self.severity.value,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "validity": self.validity,
            "change_state": self.change_state.value,
            "metadata": self.metadata,
        }