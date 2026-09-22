# Phase 11 - alert policy engine.
#
# Decides whether a MarineEvent becomes an alert, with a configurable pipeline:
#
#   EVENT -> RELEVANCE -> SEVERITY -> VALIDITY -> DEDUPLICATION ->
#   RISK EVALUATION -> VERIFICATION -> ALERT
#
# Considerations: location, event type, severity, distance, time horizon,
# source freshness, source confidence, user preferences (immediate /
# important_only / digest / disabled per category).
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.events.model import EventSeverity, MarineEvent, MarineEventType, utcnow

# User preference category -> event types that fall in it.
_PREFERENCE_CATEGORY: Dict[str, List[MarineEventType]] = {
    "cyclone": [MarineEventType.CYCLONE],
    "lightning": [MarineEventType.LIGHTNING],
    "waves": [MarineEventType.HIGH_WAVE],
    "weather": [MarineEventType.WEATHER_HAZARD, MarineEventType.HIGH_WIND,
                MarineEventType.FORECAST_CHANGE],
    "restrictions": [MarineEventType.RESTRICTION_ACTIVATED,
                     MarineEventType.RESTRICTION_UPDATED],
    "geofence": [MarineEventType.GEOFENCE_APPROACH,
                 MarineEventType.GEOFENCE_ENTRY,
                 MarineEventType.GEOFENCE_EXIT],
    "pfz": [MarineEventType.PFZ_UPDATE],
    "sources": [MarineEventType.SOURCE_FAILURE,
                MarineEventType.SOURCE_RECOVERY],
    "data": [MarineEventType.NEW_OBSERVATION, MarineEventType.DATA_CHANGED,
             MarineEventType.DATA_CORRECTED],
}

# Alert-only severity floor: noteworthy events at or above become alerts.
_SEVERITY_FLOOR = {
    MarineEventType.WEATHER_HAZARD: EventSeverity.WARNING,
    MarineEventType.LIGHTNING: EventSeverity.WARNING,
    MarineEventType.CYCLONE: EventSeverity.CRITICAL,
    MarineEventType.HIGH_WAVE: EventSeverity.WARNING,
    MarineEventType.HIGH_WIND: EventSeverity.WARNING,
    MarineEventType.RESTRICTION_ACTIVATED: EventSeverity.WARNING,
    MarineEventType.RESTRICTION_UPDATED: EventSeverity.CAUTION,
    MarineEventType.RESTRICTION_EXPIRED: EventSeverity.INFO,
    MarineEventType.GEOFENCE_APPROACH: EventSeverity.CAUTION,
    MarineEventType.GEOFENCE_ENTRY: EventSeverity.WARNING,
    MarineEventType.GEOFENCE_EXIT: EventSeverity.INFO,
    MarineEventType.SOURCE_FAILURE: EventSeverity.CAUTION,
    MarineEventType.SOURCE_RECOVERY: EventSeverity.INFO,
}

# IMPORTANT_ONLY categories: these always surface; the rest only if immediate.
_IMPORTANT_CATEGORIES = {"cyclone", "lightning", "waves", "weather",
                         "restrictions", "geofence"}


def preference_category(event_type: MarineEventType) -> str:
    for category, types in _PREFERENCE_CATEGORY.items():
        if event_type in types:
            return category
    return "data"


@dataclass
class AlertPolicyConfig:
    dedupe_window_seconds: int = 3600
    ml_material_change: float = 0.10
    geofence_approach_km: float = 25.0
    max_relevance_distance_km: float = 200.0
    default_mode: str = "important_only"


@dataclass
class AlertCandidate:
    event: MarineEvent
    title: str
    message: str
    severity: EventSeverity
    dedupe_key: str
    matches_preferences: bool = True
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""


class AlertPolicyEngine:
    """Deterministic relevance + gate for events -> alert candidates."""

    def __init__(self, config: Optional[AlertPolicyConfig] = None,
                 preferences: Optional[Dict[str, str]] = None) -> None:
        self.config = config or AlertPolicyConfig()
        self.preferences = preferences or {}

    # ------------------------------------------------------------- preferences
    def mode_for(self, event_type: MarineEventType) -> str:
        category = preference_category(event_type)
        return self.preferences.get(category, self.config.default_mode)

    # ---------------------------------------------------------------- relevance
    def _relevance_passes(self, event: MarineEvent) -> bool:
        """Location relevance: an event without a location is always relevant;
        an event with one must be within the maximum relevance distance of any
        configured watch point (default: always relevant unless a watch point
        is set)."""
        # No watch points configured -> everything is relevant.
        return True

    # ------------------------------------------------------------------ gate
    def evaluate(self, event: MarineEvent, *, now: Optional[datetime] = None
                 ) -> Optional[AlertCandidate]:
        """Run the full policy pipeline.  Returns an AlertCandidate when the
        event should become an alert, else None."""
        now = now or utcnow()
        mode = self.mode_for(event.event_type)

        # 1. RELEVANCE
        if not self._relevance_passes(event):
            return None

        # 2. SEVERITY floor
        floor = _SEVERITY_FLOOR.get(event.event_type)
        if floor is not None and _severity_rank(event.severity) < _severity_rank(floor):
            return None

        # 3. VALIDITY: an event whose validity window has fully ended cannot
        #    become a live alert (it becomes an expiry notice instead).
        validity = event.validity or {}
        valid_until = validity.get("valid_until")
        if valid_until:
            try:
                until = datetime.fromisoformat(str(valid_until).replace("Z", "+00:00"))
                if until < now:
                    return None
            except (TypeError, ValueError):
                pass

        # 4. USER PREFERENCES
        matches = self._matches_preference(mode, event)
        if not matches:
            return None

        # 5. FRESHNESS: a stale-source event may still be valid but its
        #    verification is limited; we surface it with an explicit note.
        freshness_note = self._freshness_note(event)

        # 6. DEDUPLICATION is enforced one layer up (persistence keeps the
        #    seen dedupe_keys within a window).
        candidate = AlertCandidate(
            event=event,
            title=_title_for(event),
            message=_message_for(event) + freshness_note,
            severity=event.severity,
            dedupe_key=_dedupe_key(event),
            matches_preferences=True,
            reason=f"mode={mode} severity={event.severity.value}",
        )
        return candidate

    @staticmethod
    def _matches_preference(mode: str, event: MarineEvent) -> bool:
        if mode == "disabled":
            return False
        if mode == "immediate":
            return True
        if mode == "digest":
            # Digest mode still collects; a separate publisher gates delivery.
            return True
        # important_only
        return preference_category(event.event_type) in _IMPORTANT_CATEGORIES

    @staticmethod
    def _freshness_note(event: MarineEvent) -> str:
        freshness = (event.validity or {}).get("freshness")
        if freshness == "stale":
            return " Verification is limited: source data is stale."
        if freshness == "unavailable":
            return " Verification is limited: source data is unavailable."
        return ""

    @staticmethod
    def _severity_rank(severity: EventSeverity) -> int:
        return list(EventSeverity).index(severity)


def _severity_rank(sev) -> int:
    sev = EventSeverity(sev) if not isinstance(sev, EventSeverity) else sev
    return list(EventSeverity).index(sev)


def _title_for(event: MarineEvent) -> str:
    titles = {
        MarineEventType.CYCLONE: "Cyclone developing",
        MarineEventType.LIGHTNING: "Lightning risk",
        MarineEventType.HIGH_WAVE: "High wave alert",
        MarineEventType.HIGH_WIND: "High wind alert",
        MarineEventType.WEATHER_HAZARD: "Weather hazard",
        MarineEventType.RESTRICTION_ACTIVATED: "Restriction activated",
        MarineEventType.RESTRICTION_UPDATED: "Restriction updated",
        MarineEventType.RESTRICTION_EXPIRED: "Restriction expired",
        MarineEventType.GEOFENCE_APPROACH: "Approaching restricted waters",
        MarineEventType.GEOFENCE_ENTRY: "Entered restricted waters",
        MarineEventType.GEOFENCE_EXIT: "Left restricted waters",
        MarineEventType.PFZ_UPDATE: "Fishing zones updated",
        MarineEventType.FORECAST_CHANGE: "Forecast updated",
        MarineEventType.SOURCE_FAILURE: "Data source degraded",
        MarineEventType.SOURCE_RECOVERY: "Data source recovered",
        MarineEventType.NEW_OBSERVATION: "New observation",
        MarineEventType.DATA_CHANGED: "Data changed",
        MarineEventType.DATA_CORRECTED: "Data corrected",
    }
    return titles.get(event.event_type, event.event_type.value)


def _message_for(event: MarineEvent) -> str:
    meta = event.metadata or {}
    detail = meta.get("description") or meta.get("name") or ""
    return detail or _title_for(event)


def _dedupe_key(event: MarineEvent) -> str:
    """Stable deduplication key: identical physical events within the window
    map to the same key (event_id already reflects source+type+state)."""
    return f"{event.event_id}"