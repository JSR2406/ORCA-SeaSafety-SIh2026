# Phase 11 - ProactiveMarineEngine.
#
# Autonomous, bounded, idempotent engine:
#
#   live data -> change detection -> MarineEvent -> alert policy engine ->
#   risk evaluation -> verification -> alert persistence -> alert lifecycle.
#
# It is deliberately DB-light: it works in-memory (with optional best-effort
# persistence hooks) so it stays testable and does not depend on a reachable
# PostGIS install for the core decision logic.  The ProactiveMarineAgent only
# *produces evidence-backed candidates*; it never overrides the Risk Engine or
# hard constraints.  This engine routes a candidate through the policy engine
# and, when it survives, emits an alert.
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from app.config import settings
from app.events.change import ChangeDetector
from app.events.lifecycle import (
    AlertDeduplicator, classify_lifecycle, lifecycle_transition,
    next_severity, should_escalate,
)
from app.events.model import (
    ChangeState, EventSeverity, MarineEvent, MarineEventType, utcnow,
)
from app.events.policy import AlertCandidate, AlertPolicyConfig, AlertPolicyEngine
from app.services.risk_engine import get_risk_engine  # authoritative risk evaluation

logger = structlog.get_logger(__name__)

# Freshness labels exposed to the frontend (Phase 15).
FRESHNESS = {"live", "fresh", "recent", "stale", "unavailable"}


@dataclass
class ActiveAlert:
    """A live, not-yet-expired alert held in memory (mirrors AlertRecord)."""
    alert_uid: str
    event_id: str
    type: str
    severity: str
    status: str = "created"
    title: str = ""
    message: str = ""
    source: str = ""
    dedupe_key: str = ""
    geometry: Optional[Dict[str, Any]] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    freshness: str = "live"
    confidence: Optional[float] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    escalated_level: int = 0
    escalated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.alert_uid,
            "event_id": self.event_id,
            "type": self.type,
            "severity": self.severity,
            "status": self.status,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "geometry": self.geometry,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "freshness": self.freshness,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
            "escalated_level": self.escalated_level,
        }


class ProactiveMarineEngine:
    """Bounded proactive alert engine (restart-safe by rehydrating state)."""

    def __init__(
        self,
        config: Optional[AlertPolicyConfig] = None,
        preferences: Optional[Dict[str, str]] = None,
        detector: Optional[ChangeDetector] = None,
        persistence=None,  # optional AlertRepository
        policy_engine: Optional[AlertPolicyEngine] = None,
    ) -> None:
        self.config = config or AlertPolicyConfig(
            dedupe_window_seconds=settings.alert_dedupe_window_seconds,
            ml_material_change=settings.alert_ml_material_change,
            geofence_approach_km=settings.geofence_approach_km,
        )
        self.detector = detector or ChangeDetector(
            failure_threshold=settings.source_failure_threshold,
            recovery_ticks=settings.source_recovery_ticks,
        )
        self.policy = policy_engine or AlertPolicyEngine(self.config, preferences)
        self.deduplicator = AlertDeduplicator(self.config.dedupe_window_seconds)
        self.persistence = persistence
        self.alerts: Dict[str, ActiveAlert] = {}   # uid -> active alert
        self.events: List[Dict[str, Any]] = []     # recent events (ring)
        self.event_log: Dict[str, Dict[str, Any]] = {}  # event_id -> event
        self._material_last: Dict[str, float] = {}
        self.observed = 0
        self.duplicates = 0
        self.alert_created = 0
        self.gate_new = asyncio.Event()

    # ------------------------------------------------------------ observation
    def ingest(self, event: MarineEvent) -> Optional[ActiveAlert]:
        """Push a normalized event through the alert policy engine.

        Returns an ActiveAlert if the event gated into a new alert, else None.
        Idempotent + deduplicated at the event layer and the alert layer.
        """
        self.observed += 1
        # Persist the normalized event (idempotent by unique event_id).
        if self.persistence is not None:
            self._store_event(event)

        # Track every meaningful event (failures/recoveries/gated events appear
        # in recent_events) even when no alert is raised.
        if event.change_state != ChangeState.UNCHANGED:
            self._record_event(event.event_id, event)

        if event.change_state == ChangeState.UNCHANGED:
            self.duplicates += 1
            return None

        candidate = self.policy.evaluate(event)
        if candidate is None:
            return None

        # Deduplicate against recently-created alerts.
        if self.deduplicator.is_duplicate(candidate.dedupe_key):
            self.duplicates += 1
            return None

        alert = ActiveAlert(
            alert_uid=f"alrt-{uuid.uuid4().hex[:12]}",
            event_id=event.event_id,
            type=event.event_type.value,
            severity=candidate.severity.value,
            status="created",
            title=candidate.title,
            message=candidate.message,
            source=event.source,
            dedupe_key=candidate.dedupe_key,
            geometry=event.geometry,
            valid_from=self._iso((event.validity or {}).get("valid_from")),
            valid_until=self._iso((event.validity or {}).get("valid_until")),
            freshness=self._freshness_label(event),
            confidence=self._confidence(event),
            evidence=candidate.evidence,
        )
        self.alerts[alert.alert_uid] = alert
        self.alert_created += 1
        if self.persistence is not None:
            self._store_alert(alert, candidate)
        self.gate_new.set()
        return alert

    # --------------------------------------------------------- ML integration
    def ingest_ml_score(self, key: str, score: float,
                        at: Optional[datetime] = None) -> bool:
        """Record an ML score for material-change gating (Phase 12 integration).

        Returns True only when the score moved by >= the material threshold,
        so slight score noise never raises an alert.
        """
        at = at or utcnow()
        previous = self._material_last.get(key)
        if previous is None:
            self._material_last[key] = score
            return False
        if abs(score - previous) >= self.config.ml_material_change:
            self._material_last[key] = score
            return True
        return False

    # ------------------------------------------------------------- lifecycle
    def escalate(self, alert_uid: str) -> Optional[ActiveAlert]:
        alert = self.alerts.get(alert_uid)
        if alert is None:
            return None
        info = should_escalate(
            EventSeverity(alert.severity),
            settings.alert_max_escalations,
            utcnow(), alert.escalated_at, alert.escalated_level,
            min_step_seconds=settings.alert_escalation_step_seconds,
        )
        if info is None:
            return alert
        alert.severity = info["to"]
        alert.escalated_level = info["level"]
        alert.escalated_at = info["at"]
        alert.status = "escalated"
        # A materially-changed severity is a NEW event (per contract).
        new_event = MarineEvent(
            event_id=f"esc-{alert_uid}",
            event_type=MarineEventType.DATA_CHANGED,
            source="alert.escalation",
            timestamp=utcnow(),
            severity=info["from"],
            metadata={"description": f"Escalated to {info['to']}"},
        )
        self._record_event(new_event.event_id, new_event)
        return alert

    def acknowledge(self, alert_uid: str) -> Optional[ActiveAlert]:
        alert = self.alerts.get(alert_uid)
        if alert is None:
            return None
        status, extra = lifecycle_transition(alert.status, "acknowledge")
        alert.status = status
        return alert

    def dismiss(self, alert_uid: str) -> Optional[ActiveAlert]:
        alert = self.alerts.get(alert_uid)
        if alert is None:
            return None
        alert.status = "dismissed"
        return alert

    def resolve(self, alert_uid: str) -> Optional[ActiveAlert]:
        alert = self.alerts.get(alert_uid)
        if alert is None:
            return None
        alert.status = "resolved"
        return alert

    def expire(self, now: Optional[datetime] = None) -> int:
        """Expire any alert whose validity window has ended.  Never deletes."""
        now = now or utcnow()
        expired = 0
        for uid in list(self.alerts.keys()):
            alert = self.alerts[uid]
            until = alert.valid_until
            if until and _parse(until) is not None and _parse(until) < now:
                if alert.status not in ("resolved", "dismissed", "expired"):
                    alert.status = "expired"
                    expired += 1
        return expired

    # ------------------------------------------------------------ source health
    def observe_source(self, source: str, ok: bool) -> MarineEvent:
        state, _ = self.detector.observe_source(source, ok=ok)
        if state == ChangeState.FAILED:
            event = self.detector.build_event(
                MarineEventType.SOURCE_FAILURE, source, "__source__",
                {"status": "failed"}, state,
                severity=EventSeverity.CAUTION,
                validity={"freshness": "unavailable"},
                metadata={"description": f"{source} unavailable; verification is limited."},
            )
            self.ingest(event)
            return event
        if state == ChangeState.RECOVERED:
            event = self.detector.build_event(
                MarineEventType.SOURCE_RECOVERY, source, "__source__",
                {"status": "available"}, state,
                severity=EventSeverity.INFO,
                validity={"freshness": "live"},
                metadata={"description": f"{source} recovered."},
            )
            self.ingest(event)
            return event
        # build a no-op event for UNCHANGED so callers get a value
        return self.detector.build_event(
            MarineEventType.NEW_OBSERVATION, source, "__noop__",
            {"status": state.value}, state,
            severity=EventSeverity.INFO,
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _iso(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return value.isoformat()
        except AttributeError:
            return str(value)

    @staticmethod
    def _freshness_label(event: MarineEvent) -> str:
        f = (event.validity or {}).get("freshness")
        if not f:
            return "live"
        return f if f in FRESHNESS else "live"

    @staticmethod
    def _confidence(event: MarineEvent) -> Optional[float]:
        return event.metadata.get("confidence")

    def _record_event(self, event_id: str, event: MarineEvent) -> None:
        self.event_log[event_id] = {
            "event_id": event_id,
            "event_type": event.event_type.value,
            "source": event.source,
            "timestamp": event.timestamp.isoformat(),
            "severity": event.severity.value,
        }

    def recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        ordered = sorted(self.event_log.values(),
                         key=lambda e: e["timestamp"], reverse=True)
        return ordered[:limit]

    def _store_event(self, event: MarineEvent) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(self.persistence.upsert_event(event))
        else:
            asyncio.run(self.persistence.upsert_event(event))

    def _store_alert(self, alert: ActiveAlert, candidate: AlertCandidate) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(self.persistence.insert_alert(alert, candidate.evidence))
        else:
            asyncio.run(self.persistence.insert_alert(alert, candidate.evidence))

    # ------------------------------------------------------------ stats / probe
    def stats(self) -> Dict[str, Any]:
        return {
            "observed": self.observed,
            "duplicates": self.duplicates,
            "alert_created": self.alert_created,
            "active_alerts": len(self.alerts),
            "events_tracked": len(self.event_log),
            "freshness_map": {a.alert_uid: a.freshness for a in self.alerts.values()},
        }


def _parse(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None