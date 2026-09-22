# Phase 6 - deterministic alert model.
#
# Warnings, restrictions, geofences and data-quality signals are compiled into
# a MACHINE-CONSUMABLE alert list with stable ids, explicit severity, and a
# validity window.  Severity is derived from source severity levels, hard
# constraint flags and deterministic rules - never from free text.  Alerts are
# deduplicated on a stable id and classified against the current time, so an
# expired restriction can never render as ACTIVE.
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.orchestration.models import Intent, IntentName
from app.services.evidence_helpers import find
from app.services.localization import t


def utcnow() -> datetime:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class AlertType(str, Enum):
    CYCLONE = "cyclone"
    LIGHTNING = "lightning"
    HIGH_WAVES = "high_waves"
    STRONG_WIND = "strong_wind"
    MARINE_WARNING = "marine_warning"
    RESTRICTION = "restriction"
    GEOFENCE = "geofence"
    ROUTE = "route"
    DATA_QUALITY = "data_quality"


class AlertSeverity(str, Enum):
    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    EXPIRED = "expired"


_WARNING_TYPE_HINTS = (
    ("cyclone", AlertType.CYCLONE),
    ("lightn", AlertType.LIGHTNING),
    ("wave", AlertType.HIGH_WAVES),
    ("swell", AlertType.HIGH_WAVES),
    ("wind", AlertType.STRONG_WIND),
    ("gale", AlertType.STRONG_WIND),
)


def warning_type_for(warning_type: str) -> AlertType:
    kind = (warning_type or "").lower()
    for token, alert_type in _WARNING_TYPE_HINTS:
        if token in kind:
            return alert_type
    return AlertType.MARINE_WARNING


_WARNING_SEVERITY = {
    "critical": AlertSeverity.CRITICAL,
    "high": AlertSeverity.WARNING,
    "moderate": AlertSeverity.WATCH,
    "low": AlertSeverity.INFO,
}

_RISK_SEVERITY = {
    "critical": AlertSeverity.CRITICAL,
    "elevated": AlertSeverity.WARNING,
    "high": AlertSeverity.WARNING,
    "moderate": AlertSeverity.WATCH,
    "low": AlertSeverity.INFO,
}


def severity_from_warning(severity: str) -> AlertSeverity:
    return _WARNING_SEVERITY.get((severity or "").lower(), AlertSeverity.WATCH)


def severity_from_risk(level: str, hard_constraint: bool) -> AlertSeverity:
    if hard_constraint:
        return AlertSeverity.CRITICAL
    return _RISK_SEVERITY.get((level or "").lower(), AlertSeverity.WATCH)


@dataclass
class Alert:
    alert_id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    location: Optional[Dict[str, Any]] = None
    geometry: Optional[Dict[str, Any]] = None
    issued_at: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    source: str = ""
    status: AlertStatus = AlertStatus.ACTIVE
    confidence: Optional[float] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    official: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def stable_alert_id(source: str, source_id: str, alert_type: Any,
                    area: str, valid_until: str = "") -> str:
    """Deterministic id: the same source record always yields the same alert."""
    raw = f"{source}|{source_id}|{alert_type.value if hasattr(alert_type, 'value') else alert_type}|{area}|{valid_until}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def classify_status(valid_from: Optional[str], valid_until: Optional[str],
                    at: datetime = None) -> AlertStatus:
    """Time-window classification.  Without a window the alert is ACTIVE; an
    ended window can never be ACTIVE."""
    from datetime import datetime

    def _parse(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    at = at or utcnow()
    until = _parse(valid_until) if valid_until else None
    start = _parse(valid_from) if valid_from else None
    if until is not None and at > until:
        return AlertStatus.EXPIRED
    if start is not None and at < start:
        return AlertStatus.UPCOMING
    return AlertStatus.ACTIVE


def dedupe_alerts(alerts: List[Alert]) -> List[Alert]:
    """Keep the FIRST alert per stable id."""
    seen = set()
    unique = []
    for alert in alerts:
        if alert.alert_id in seen:
            continue
        seen.add(alert.alert_id)
        unique.append(alert)
    return unique


def _geometry_or_none(warning: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    geometry = warning.get("geometry")
    return geometry if isinstance(geometry, dict) else None


# ---------------------------------------------------------------- builders
def _warning_alerts(intent: Intent, evidence: Dict[str, Any], language: str,
                    at: datetime) -> List[Alert]:
    safety = find(evidence, "marine_safety_check", "safety.marine_safety_check")
    active_warnings = safety.get("active_warnings") or []
    alerts = []
    for index, warning in enumerate(active_warnings):
        severity = severity_from_warning(warning.get("severity"))
        warning_type = warning_type_for(warning.get("warning_type"))
        warning_id = warning.get("warning_id") or f"w{index}"
        description = warning.get("description") or warning.get("warning_type") \
            or "active marine warning"
        alerts.append(Alert(
            alert_id=stable_alert_id("safety.marine_safety_check", warning_id,
                                     warning_type, description,
                                     str(warning.get("valid_until") or "")),
            type=warning_type,
            severity=severity,
            title=t(language, "alert.title.restriction"),
            message=description,
            location=warning.get("location") if isinstance(
                warning.get("location"), dict) else None,
            geometry=_geometry_or_none(warning),
            issued_at=warning.get("issued_at"),
            valid_from=warning.get("valid_from"),
            valid_until=warning.get("valid_until"),
            source="safety.marine_safety_check",
            status=classify_status(warning.get("valid_from"),
                                   warning.get("valid_until"), at),
            evidence=[{"claim": description,
                       "source": "safety.marine_safety_check"}],
        ))
    return alerts


def _risk_alert(intent: Intent, evidence: Dict[str, Any], language: str,
                at: datetime) -> List[Alert]:
    risk = find(evidence, "risk_profile", "analytics.risk_profile")
    if not risk or not risk.get("point"):
        return []
    level = str(risk.get("level") or "unknown").lower()
    hard = bool(risk.get("hard_constraint"))
    if not hard and level not in ("elevated", "high", "critical"):
        return []
    severity = severity_from_risk(level, hard)
    point = risk.get("point")
    message = (t(language, "line.risk_hard_constraint") if hard
               else t(language, "line.risk_point", level=level))
    evidence_records = []
    for score in risk.get("scores") or []:
        evidence_records.append({"claim": (
            f"{score.get('variable')}={score.get('value')} "
            f"risk={score.get('risk')}"),
            "source": "analytics.risk_profile"})
    return [Alert(
        alert_id=stable_alert_id("analytics.risk_profile", "point",
                                 AlertType.RESTRICTION,
                                 f"{point.get('lat')},{point.get('lon')}"),
        type=AlertType.RESTRICTION,
        severity=severity,
        title=t(language, "alert.title.restriction"),
        message=message,
        location=point,
        source="analytics.risk_profile",
        status=classify_status(None, None, at),
        evidence=evidence_records,
    )]


def _dynamic_alerts(intent: Intent, evidence: Dict[str, Any], language: str,
                    at: datetime) -> List[Alert]:
    dynamic = find(evidence, "dynamic_restrictions",
                   "restriction.dynamic_active")
    active = dynamic.get("active_dynamic") if isinstance(dynamic, dict) else []
    alerts = []
    for item in active or []:
        restriction_id = item.get("restriction_id") or item.get("name") or "restriction"
        name = item.get("name") or restriction_id
        severity = severity_from_warning(item.get("severity"))
        severity = severity if severity != AlertSeverity.INFO else AlertSeverity.WATCH
        valid_from = item.get("valid_from")
        valid_until = item.get("valid_until")
        status = classify_status(valid_from, valid_until, at)
        if status in (AlertStatus.EXPIRED, AlertStatus.UPCOMING):
            # Never surface time-windowed restrictions as live when inactive.
            continue
        geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) \
            else None
        alerts.append(Alert(
            alert_id=stable_alert_id("restriction.dynamic_active",
                                     restriction_id, AlertType.RESTRICTION,
                                     name, str(valid_until or "")),
            type=AlertType.RESTRICTION,
            severity=severity,
            title=t(language, "alert.title.dynamic_restriction"),
            message=name,
            location=item.get("point") if isinstance(item.get("point"), dict)
            else None,
            geometry=geometry,
            valid_from=valid_from,
            valid_until=valid_until,
            source=item.get("source") or "restriction.dynamic_active",
            official=item.get("official"),
            status=status,
            evidence=[{"claim": name,
                       "source": item.get("source") or "restriction.dynamic_active"}],
        ))
    hits = dynamic.get("static_geofence_hits") if isinstance(dynamic, dict) else []
    for geofence in hits or []:
        geofence_id = geofence.get("geofence_id") or geofence.get("name") or "geofence"
        name = geofence.get("name") or geofence_id
        severity = severity_from_warning(geofence.get("severity"))
        severity = severity if severity != AlertSeverity.INFO else AlertSeverity.WATCH
        alerts.append(Alert(
            alert_id=stable_alert_id("geofence_catalog", geofence_id,
                                     AlertType.GEOFENCE, name),
            type=AlertType.GEOFENCE,
            severity=severity,
            title=t(language, "alert.title.geofence"),
            message=t(language, "alert.msg.geofence", name=name),
            geometry=geofence.get("geometry") if isinstance(
                geofence.get("geometry"), dict) else None,
            source="geofence_catalog",
            status=classify_status(None, None, at),
            evidence=[{"claim": name, "source": "geofence_catalog"}],
        ))
    return alerts


def _route_alerts(intent: Intent, evidence: Dict[str, Any], language: str,
                  at: datetime) -> List[Alert]:
    if intent.name not in (IntentName.ROUTE, IntentName.SAFETY):
        return []
    restrictions = find(evidence, "restrictions_near_route",
                        "geospatial.restrictions_near_route")
    data = restrictions.get("data") if isinstance(restrictions.get("data"), dict) \
        else restrictions
    count = int(data.get("route_intersects_restricted_count") or 0) \
        if isinstance(data, dict) else 0
    if count == 0:
        return []
    return [Alert(
        alert_id=stable_alert_id("geospatial.restrictions_near_route", "route",
                                 AlertType.ROUTE, "route"),
        type=AlertType.ROUTE,
        severity=AlertSeverity.CRITICAL,
        title=t(language, "alert.title.route_restriction"),
        message=t(language, "alert.msg.route_restriction", count=count),
        source="geospatial.restrictions_near_route",
        status=classify_status(None, None, at),
        evidence=[{"claim": f"{count} restricted-area intersection(s)",
                   "source": "geospatial.restrictions_near_route"}],
    )]


def _data_quality_alerts(intent: Intent, evidence: Dict[str, Any], language: str,
                         at: datetime) -> List[Alert]:
    alerts = []

    fused = find(evidence, "fused_state", "marine.get_fused_state")
    missing_sources = []
    if fused:
        missing = fused.get("missing") or []
        if missing:
            missing_sources.append("marine.get_fused_state")
    safety = find(evidence, "marine_safety_check", "safety.marine_safety_check")
    if intent.name in (IntentName.SAFETY,) and not safety:
        missing_sources.append("safety.marine_safety_check")
    if missing_sources and (intent.name in (
            IntentName.SAFETY, IntentName.FISHING, IntentName.PFZ,
            IntentName.BRIEFING)):
        alerts.append(Alert(
            alert_id=stable_alert_id("data_quality", "missing-sources",
                                     AlertType.DATA_QUALITY, "sources"),
            type=AlertType.DATA_QUALITY,
            severity=AlertSeverity.WATCH,
            title=t(language, "alert.title.data_quality"),
            message=f"Source unavailable: {', '.join(missing_sources)}",
            source="fusion",
            status=classify_status(None, None, at),
            evidence=[{"claim": f"missing {len(missing_sources)} source(s)",
                       "source": "marine.get_fused_state"}],
        ))

    freshness = fused.get("freshness") if isinstance(fused, dict) else None
    overall = ""
    if isinstance(freshness, dict):
        overall = str(freshness.get("overall") or "unknown")
    if overall.lower() in ("stale", "expired", "unknown"):
        stale_claim = "ocean observation data is stale or of unknown age"
        alerts.append(Alert(
            alert_id=stable_alert_id("data_quality", "stale", AlertType.DATA_QUALITY,
                                     "freshness", overall),
            type=AlertType.DATA_QUALITY,
            severity=AlertSeverity.INFO if overall.lower() == "stale"
            else AlertSeverity.WATCH,
            title=t(language, "alert.title.data_quality"),
            message=stale_claim,
            source="fusion",
            status=classify_status(None, None, at),
            evidence=[{"claim": stale_claim, "source": "marine.get_fused_state"}],
        ))
    return alerts


def build_alerts(intent: Intent, evidence: Dict[str, Any], language: str = "en-IN",
                 at: datetime = None) -> List[Dict[str, Any]]:
    """Compile, dedupe and serialize the alert list for this execution."""
    from datetime import datetime, timezone
    at = at or datetime.now(timezone.utc)
    alerts: List[Alert] = []
    alerts += _warning_alerts(intent, evidence, language, at)
    alerts += _risk_alert(intent, evidence, language, at)
    alerts += _dynamic_alerts(intent, evidence, language, at)
    alerts += _route_alerts(intent, evidence, language, at)
    alerts += _data_quality_alerts(intent, evidence, language, at)
    deduped = dedupe_alerts(alerts)
    return [a.to_dict() for a in deduped]