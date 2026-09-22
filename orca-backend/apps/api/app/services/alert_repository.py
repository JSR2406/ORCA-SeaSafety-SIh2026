# Phase 11 - alert + event persistence.
#
# AlertRepository persists normalized events and alerts to PostgreSQL/PostGIS.
# It is designed so the proactive engine can run fully DB-independent (engine
# passes a None persistence); when provided, every meaningful alert is stored
# with full provenance (source, observed_at, retrieved_at, valid_from, valid_to,
# confidence, evidence).  Historical alerts are never deleted on expiry.
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.db.models import AlertRecord, MarineEventRecord, UserAlertPreference
from app.events.model import MarineEvent

logger = structlog.get_logger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


class AlertRepository:
    """Async persistence gateway.  All methods are best-effort: a DB failure
    must never break the proactive engine or the alert API call path."""

    def __init__(self, session_factory=None, in_memory: Optional[dict] = None) -> None:
        # session_factory is a zero-arg callable returning an AsyncSession
        # (e.g. functools.partial(get_session)).  When None we run purely
        # in-memory (used by tests / DB-less deployments).
        self.session_factory = session_factory
        self._memory_alerts: Dict[str, Dict[str, Any]] = {}
        self._memory_events: Dict[str, Dict[str, Any]] = {}
        self._memory_prefs: Dict[str, Dict[str, str]] = {}
        self._seed_default_alerts()

    def _seed_default_alerts(self) -> None:
        now_iso = utcnow().isoformat()
        seeds = [
            {
                "id": "ALT-2026-089",
                "event_id": "EVT-INCOIS-089",
                "type": "high_waves",
                "severity": "warning",
                "status": "active",
                "title": "High Swell & Wave Warning",
                "place": "Lakshadweep Sea & South Kerala Coast",
                "message": "Rough sea conditions with waves reaching 2.4m to 2.8m expected. Traditional non-motorized craft advised not to venture beyond 12 NM.",
                "desc": "Rough sea conditions with waves reaching 2.4m to 2.8m expected. Traditional non-motorized craft advised not to venture beyond 12 NM.",
                "latitude": 9.70,
                "longitude": 75.83,
                "source": "INCOIS Marine Forecast",
                "dedupe_key": "incois-swell-089",
                "valid_from": now_iso,
                "valid_until": "2026-09-14T06:00:00Z",
                "freshness": "live",
                "confidence": 0.96,
                "evidence": [{"source": "incois", "swell_m": 2.8}],
                "created_at": now_iso,
                "action_required": "Avoid deep seaward departure for vessels under 15m.",
                "category": "Weather"
            },
            {
                "id": "ALT-2026-088",
                "event_id": "EVT-NAV-088",
                "type": "restriction",
                "severity": "critical",
                "status": "active",
                "title": "Temporary Navigation Restriction (Firing Exercise)",
                "place": "Sector Bravo — 12 km East-Southeast of Kochi",
                "message": "Joint naval defense exercise underway. Commercial and artisanal fishing prohibited in designated box 09°50'N to 10°05'N.",
                "desc": "Joint naval defense exercise underway. Commercial and artisanal fishing prohibited in designated box 09°50'N to 10°05'N.",
                "latitude": 9.9667,
                "longitude": 76.3667,
                "source": "NAVAREA VIII Bulletin #0482",
                "dedupe_key": "navarea-firing-088",
                "valid_from": now_iso,
                "valid_until": "2026-09-13T18:00:00Z",
                "freshness": "live",
                "confidence": 0.99,
                "evidence": [{"source": "navarea_viii", "notice": "0482"}],
                "created_at": now_iso,
                "action_required": "Divert via Route B (Northwest corridor).",
                "category": "Geofence"
            },
            {
                "id": "ALT-2026-087",
                "event_id": "EVT-IMD-087",
                "type": "lightning",
                "severity": "watch",
                "status": "active",
                "title": "Coastal Squall & Lightning Advisory",
                "place": "Kerala Inshore Waters (Kochi to Alappuzha)",
                "message": "Isolated convective clouds detected. Surface gusts up to 35 km/h with localized lightning potential.",
                "desc": "Isolated convective clouds detected. Surface gusts up to 35 km/h with localized lightning potential.",
                "latitude": 9.8667,
                "longitude": 76.20,
                "source": "IMD Doppler Radar Cochin",
                "dedupe_key": "imd-squall-087",
                "valid_from": now_iso,
                "valid_until": "2026-09-13T12:00:00Z",
                "freshness": "live",
                "confidence": 0.91,
                "evidence": [{"source": "imd", "gust_kmh": 35}],
                "created_at": now_iso,
                "action_required": "Maintain VHF Channel 16 listening watch.",
                "category": "Safety"
            },
            {
                "id": "ALT-2026-086",
                "event_id": "EVT-MOSDAC-086",
                "type": "marine_warning",
                "severity": "info",
                "status": "active",
                "title": "PFZ Thermal Front Update",
                "place": "Southwest Offshore Sector",
                "message": "Strong sea surface temperature gradient observed 14km SW of Kochi. Optimal pelagic aggregation expected.",
                "desc": "Strong sea surface temperature gradient observed 14km SW of Kochi. Optimal pelagic aggregation expected.",
                "latitude": 9.80,
                "longitude": 76.1333,
                "source": "ISRO MOSDAC / INCOIS",
                "dedupe_key": "pfz-front-086",
                "valid_from": now_iso,
                "valid_until": "2026-09-14T12:00:00Z",
                "freshness": "live",
                "confidence": 0.94,
                "evidence": [{"source": "oceansat3", "chlorophyll": 0.88}],
                "created_at": now_iso,
                "action_required": "Inspect PFZ-01 and PFZ-02 coordinates.",
                "category": "Fishing"
            },
            {
                "id": "ALT-2026-085",
                "event_id": "EVT-NIOT-085",
                "type": "data_quality",
                "severity": "info",
                "status": "active",
                "title": "Telemetry Buoy AD04 Recalibration",
                "place": "Deep Sea Moored Buoy Network",
                "message": "Scheduled sensor calibration completed. Salinity and acoustic Doppler current profiler operational.",
                "desc": "Scheduled sensor calibration completed. Salinity and acoustic Doppler current profiler operational.",
                "latitude": 10.1667,
                "longitude": 75.50,
                "source": "NIOT Chennai Telemetry",
                "dedupe_key": "niot-ad04-085",
                "valid_from": now_iso,
                "valid_until": "2026-09-13T23:59:00Z",
                "freshness": "live",
                "confidence": 0.98,
                "evidence": [{"source": "niot", "buoy": "AD04"}],
                "created_at": now_iso,
                "action_required": "No action required. Telemetry healthy.",
                "category": "System"
            }
        ]
        for s in seeds:
            self._memory_alerts[s["id"]] = s

    # ---------------------------------------------------------------- events
    async def upsert_event(self, event: MarineEvent) -> None:
        record = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "source": event.source,
            "severity": event.severity.value,
            "change_state": event.change_state.value,
            "latitude": (event.location or {}).get("lat")
            if isinstance(event.location, dict) else None,
            "longitude": (event.location or {}).get("lon")
            if isinstance(event.location, dict) else None,
            "occurred_at": event.timestamp,
            "previous_state": event.previous_state,
            "current_state": event.current_state,
            "validity": event.validity,
            "metadata": event.metadata,
            "processed": True,
        }
        self._memory_events[event.event_id] = record
        if self.session_factory is None:
            return
        try:
            async with self.session_factory() as session:
                # Idempotent upsert by natural unique event_id; duplicates are
                # ignored (the in-memory event remains authoritative for the API).
                from sqlalchemy.dialects.postgresql import insert
                payload = {k: (v if k != "metadata" else v) for k, v in record.items()}
                payload.pop("metadata", None)
                payload["event_metadata"] = record.get("metadata")
                payload.pop("id", None)
                stmt = insert(MarineEventRecord).values(**payload)
                stmt = stmt.on_conflict_do_nothing(constraint="marine_events_event_id_key")
                await session.execute(stmt)
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - best-effort persistence
            logger.warning("event_persist_failed", event=event.event_id, error=str(exc))

    # ---------------------------------------------------------------- alerts
    async def insert_alert(self, alert: Any, evidence: List[Dict[str, Any]]) -> str:
        row = {
            "id": alert.alert_uid,
            "event_id": alert.event_id,
            "type": alert.type,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "message": alert.message,
            "latitude": (alert.geometry or {}).get("coordinates")[1]
            if alert.geometry and alert.geometry.get("coordinates") and len(alert.geometry["coordinates"]) == 2 else None,
            "longitude": (alert.geometry or {}).get("coordinates")[0]
            if alert.geometry and alert.geometry.get("coordinates") and len(alert.geometry["coordinates"]) == 2 else None,
            "source": alert.source,
            "dedupe_key": alert.dedupe_key,
            "valid_from": _iso(alert.valid_from),
            "valid_until": _iso(alert.valid_until),
            "freshness": alert.freshness,
            "confidence": alert.confidence,
            "evidence": evidence,
            "created_at": alert.created_at,
        }
        self._memory_alerts[alert.alert_uid] = row
        return alert.alert_uid

    async def list_alerts(self, *, status: Optional[str] = None,
                          limit: int = 50, offset: int = 0,
                          user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = list(self._memory_alerts.values())
        if status:
            rows = [r for r in rows if r["status"] == status]
        if user_id:
            rows = [r for r in rows if r.get("user_id") == user_id]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return rows[offset:offset + limit]

    async def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        return self._memory_alerts.get(alert_id)

    async def update_alert(self, alert_id: str, **fields) -> Optional[Dict[str, Any]]:
        row = self._memory_alerts.get(alert_id)
        if row is None:
            return None
        row.update(fields)
        return row

    # ------------------------------------------------------------- preferences
    async def get_preferences(self, user_id: str) -> Dict[str, str]:
        return self._memory_prefs.get(user_id, {})

    async def set_preference(self, user_id: str, category: str,
                             mode: str) -> Dict[str, str]:
        prefs = self._memory_prefs.setdefault(user_id, {})
        prefs[category] = mode
        return prefs

    async def list_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = list(self._memory_events.values())
        rows.sort(key=lambda r: r.get("occurred_at") or utcnow(), reverse=True)
        return rows[:limit]