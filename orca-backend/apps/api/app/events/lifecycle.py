# Phase 11 - alert lifecycle (status machine) + deduplication.
#
# Lifecycle: CREATED -> ACTIVE -> [ACKNOWLEDGED / ESCALATED] -> EXPIRED /
# RESOLVED / DISMISSED.  Historical alerts are NEVER deleted when they expire;
# they are transitioned to EXPIRED.
#
# Deduplication: an identical event (same dedupe_key) within the configured
# window does NOT emit a second alert.  Escalation creates a NEW event only
# when the severity materially increases (CAUTION -> WARNING -> HIGH -> CRITICAL).
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from app.events.model import EventSeverity, utcnow


class AlertLifecycle(Enum):
    CREATED = "created"
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# Ordered severity ladder for material-change escalation.
_SEVERITY_LADDER = [
    EventSeverity.INFO,
    EventSeverity.CAUTION,
    EventSeverity.WARNING,
    EventSeverity.HIGH,
    EventSeverity.CRITICAL,
]


class AlertDeduplicator:
    """Bounded in-memory seen-set for dedupe keys within a time window."""

    def __init__(self, window_seconds: int = 3600) -> None:
        self.window = timedelta(seconds=window_seconds)
        self._seen: Dict[str, datetime] = {}

    def is_duplicate(self, dedupe_key: str, now: Optional[datetime] = None) -> bool:
        now = now or utcnow()
        last = self._seen.get(dedupe_key)
        if last is not None and (now - last) <= self.window:
            return True
        self._seen[dedupe_key] = now
        return False

    def reset(self) -> None:
        self._seen.clear()


def next_severity(severity: EventSeverity) -> Optional[EventSeverity]:
    """Materially escalated severity, or None at the top of the ladder."""
    severity = severity if isinstance(severity, EventSeverity) else EventSeverity(severity)
    idx = _SEVERITY_LADDER.index(severity)
    if idx + 1 >= len(_SEVERITY_LADDER):
        return None
    return _SEVERITY_LADDER[idx + 1]


def should_escalate(current_severity, limit: int, now: datetime,
                    escalated_at: Optional[datetime],
                    escalated_level: int,
                    min_step_seconds: int = 3600) -> Optional[Dict[str, Any]]:
    """Return escalation info when the severity should materially rise.

    Rules:
      * never beyond limit (max_escalations);
      * require >= min_step_seconds since the previous escalation;
      * only material jumps (at least one ladder step) escalate.
    """
    next_sev = next_severity(current_severity)
    if next_sev is None:
        return None
    if escalated_level >= limit:
        return None
    if escalated_at is not None and (now - escalated_at).total_seconds() < min_step_seconds:
        return None
    return {
        "from": current_severity.value if isinstance(current_severity, EventSeverity)
                else current_severity,
        "to": next_sev.value,
        "level": escalated_level + 1,
        "at": now.isoformat(),
    }


def classify_lifecycle(valid_from: Optional[datetime],
                       valid_until: Optional[datetime],
                       status: str,
                       now: Optional[datetime] = None) -> str:
    """Re-derive lifecycle from the validity window without deleting history."""
    if status in ("acknowledged", "resolved", "dismissed", "escaped"):
        return status
    now = now or utcnow()
    if valid_until is not None and now > valid_until:
        return "expired"
    if status in ("escalated", "active"):
        return status
    return "active"


def lifecycle_transition(current: str, action: str,
                         now: Optional[datetime] = None) -> Dict[str, Any]:
    """Apply a lifecycle transition; returns (new_status, fields dict).
    Invalid transitions are rejected."""
    now = now or utcnow()
    if action == "acknowledge":
        if current in ("acknowledged", "resolved", "dismissed"):
            return current, {}
        return "acknowledged", {"acknowledged_at": now}
    if action == "dismiss":
        return "dismissed", {}
    if action == "resolve":
        return "resolved", {"resolved_at": now}
    return current, {}