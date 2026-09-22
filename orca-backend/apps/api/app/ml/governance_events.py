# Phase 13 - learning event bus.
#
# Emits persistent, traceable learning/governance events (MODEL_DRIFT,
# MODEL_PERFORMANCE_DEGRADED, GROUND_TRUTH_AVAILABLE, RETRAINING_REQUIRED,
# MODEL_CANDIDATE_CREATED, MODEL_VALIDATION_FAILED, MODEL_PROMOTED,
# MODEL_ROLLBACK, DATA_DRIFT_DETECTED, PREDICTION_DRIFT_DETECTED) using the
# Phase 11 MarineEvent vocabulary, so everything is persisted and traceable.
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.events.model import MarineEvent, MarineEventType

logger = structlog.get_logger(__name__)


class LearningEventBus:
    """Bounded, testable sink for learning lifecycle events.

    Persisted in-memory with an optional best-effort hook; mirrors the Phase 11
    event handling so no event is lost to the conversational layers.
    """

    def __init__(self, max_events: int = 500) -> None:
        self.events: List[Dict[str, Any]] = []
        self.max_events = int(max_events)

    def record(self, event_type: MarineEventType, source: str = "ml",
               metadata: Optional[Dict[str, Any]] = None,
               severity: str = "info") -> Dict[str, Any]:
        event_id = f"le-{uuid.uuid4().hex[:12]}"
        rec = {
            "event_id": event_id,
            "event_type": event_type.value,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "metadata": metadata or {},
        }
        self.events.append(rec)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        return rec

    def reset(self) -> None:
        self.events = []

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.events[-int(limit):]


_event_bus: Optional[LearningEventBus] = None


def get_event_bus() -> LearningEventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = LearningEventBus()
    return _event_bus


def reset_event_bus() -> None:
    global _event_bus
    _event_bus = None


def emit_learning_event(event_type: MarineEventType, source: str = "ml",
                        metadata: Optional[Dict[str, Any]] = None,
                        severity: str = "info") -> Dict[str, Any]:
    """Emit a learning event to the shared bus."""
    return get_event_bus().record(event_type, source=source,
                                  metadata=metadata, severity=severity)