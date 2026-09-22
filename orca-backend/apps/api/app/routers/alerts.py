# Phase 11 - versioned proactive alert API.
#
# GET  /api/v1/alerts              - list (filter by status/severity/type)
# GET  /api/v1/alerts/{id}         - fetch one alert
# POST /api/v1/alerts/{id}/acknowledge - lifecycle ack
# POST /api/v1/alerts/preferences  - user alert preferences
# GET  /api/v1/events              - recent normalized events (observable)
#
# Realtime delivery rides the existing /api/v1/orchestrate/stream WS surface;
# alert lifecycle events are emitted through it when a frontend is attached.
# This router NEVER exposes chain-of-thought, internal prompts, DB queries,
# credentials, or raw internal tool arguments.
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.agents.proactive_agent import get_proactive_engine
from app.security.operator_auth import require_authority
from app.services.alert_repository import AlertRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["alerts"])


def _repo() -> AlertRepository:
    """Return the alert repository this process exposes.  Prefer the app-bound
    repository; fall back to the proactive engine's own persistence so an
    ingested alert is always visible to the API (single source of truth)."""
    bound = getattr(_app_state, "alert_repository", None)
    if bound is not None:
        return bound
    engine_repo = get_proactive_engine().persistence
    return engine_repo or _default_repo


_default_repo = AlertRepository()
_app_state = None


def bind_alert_state(state: Any) -> None:
    """Wire the app-level alert services (engine + repository) exposed by the
    lifespan/holder so the router and realtime stream share one state."""
    global _app_state
    _app_state = state


@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = Query(None, description="created|active|..."),
    severity: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    try:
        rows = await _repo().list_alerts(status=status, limit=limit,
                                         offset=offset)
    except Exception as exc:  # noqa: BLE001 - never leak internals
        logger.exception("alerts_list_error")
        raise HTTPException(status_code=500,
                            detail="Failed to list alerts")
    if severity:
        rows = [r for r in rows if r.get("severity") == severity]
    if type:
        rows = [r for r in rows if r.get("type") == type]
    return {"alerts": rows, "total": len(rows)}


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str) -> Dict[str, Any]:
    try:
        row = await _repo().get_alert(alert_id)
    except Exception:  # noqa: BLE001
        logger.exception("alerts_get_error")
        raise HTTPException(status_code=500, detail="Failed to get alert")
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"alert": row}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    operator: Dict[str, Any] = Depends(require_authority),
) -> Dict[str, Any]:
    try:
        updated = await _repo().update_alert(
            alert_id, status="acknowledged",
            acknowledged_at=datetime.now(timezone.utc).isoformat())
        # also run the in-memory lifecycle transition on the live engine alert
        engine = get_proactive_engine()
        live = engine.acknowledge(alert_id)
    except Exception:  # noqa: BLE001
        logger.exception("alerts_ack_error")
        raise HTTPException(status_code=500, detail="Failed to acknowledge")
    if updated is None and live is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "acknowledged", "id": alert_id}


class AlertCreateRequest(BaseModel):
    """Validated payload for an authority-published safety notice."""

    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, max_length=64)
    event_id: Optional[str] = Field(default=None, max_length=64)
    type: Optional[str] = Field(default=None, max_length=64)
    severity: Optional[str] = Field(default=None, max_length=32)
    level: Optional[str] = Field(default=None, max_length=32)
    status: Optional[str] = Field(default=None, max_length=32)
    title: Optional[str] = Field(default=None, max_length=200)
    message: Optional[str] = Field(default=None, max_length=2000)
    desc: Optional[str] = Field(default=None, max_length=2000)
    place: Optional[str] = Field(default=None, max_length=200)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    coordinates: Optional[str] = Field(default=None, max_length=64)
    source: Optional[str] = Field(default=None, max_length=120)
    dedupe_key: Optional[str] = Field(default=None, max_length=64)
    valid_from: Optional[str] = Field(default=None, max_length=64)
    valid_until: Optional[str] = Field(default=None, max_length=64)
    validTill: Optional[str] = Field(default=None, max_length=64)
    confidence: float = Field(default=0.98, ge=0, le=1)
    evidence: Optional[List[Dict[str, Any]]] = None
    action_required: Optional[str] = Field(default=None, max_length=500)
    actionRequired: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=64)


@router.post("/alerts")
async def create_alert(
    payload: AlertCreateRequest,
    operator: Dict[str, Any] = Depends(require_authority),
) -> Dict[str, Any]:
    body = payload.model_dump(exclude_none=True)
    alert_id = body.get("id") or f"ALT-DISPATCH-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "id": alert_id,
        "event_id": body.get("event_id", f"EVT-{alert_id}"),
        "type": body.get("type", "marine_warning"),
        "severity": (body.get("severity") or body.get("level") or "warning").lower(),
        "level": (body.get("level") or body.get("severity") or "HIGH").upper(),
        "status": body.get("status", "active"),
        "title": body.get("title", "Emergency Maritime Notice"),
        "message": body.get("message") or body.get("desc", ""),
        "desc": body.get("desc") or body.get("message", ""),
        "place": body.get("place", "Coastal Coverage Sector"),
        "latitude": body.get("latitude") or body.get("lat", 9.9667),
        "longitude": body.get("longitude") or body.get("lon") or body.get("lng", 76.165),
        "coordinates": body.get("coordinates") or f"{body.get('lat', 9.97)}°N, {body.get('lon', 76.16)}°E",
        "source": body.get("source", "Coast Guard MRCC"),
        "dedupe_key": body.get("dedupe_key", alert_id),
        "valid_from": body.get("valid_from", now_iso),
        "valid_until": body.get("valid_until", "2026-09-15T18:00:00Z"),
        "validTill": body.get("validTill") or body.get("valid_until", "24 Hours IST"),
        "freshness": "live",
        "confidence": float(body.get("confidence", 0.98)),
        "evidence": body.get("evidence", [{"source": "broadcast_console"}]),
        "created_at": now_iso,
        "time": "Just now",
        "action_required": body.get("action_required") or body.get("actionRequired", "Maintain VHF Channel 16 continuous listening watch."),
        "actionRequired": body.get("actionRequired") or body.get("action_required", "Maintain VHF Channel 16 continuous listening watch."),
        "category": body.get("category", "Safety")
    }
    row["published_by"] = operator.get("sub")
    repo = _repo()
    repo._memory_alerts[alert_id] = row
    logger.info("alert_created", alert_id=alert_id, title=row["title"],
                published_by=operator.get("sub"))
    return {"status": "created", "alert": row}


@router.get("/events")
async def list_events(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    engine = get_proactive_engine()
    try:
        events = await _repo().list_recent_events(limit=limit)
    except Exception:  # noqa: BLE001
        events = engine.recent_events(limit=limit)
    return {"events": events, "total": len(events)}


@router.post("/alerts/preferences")
async def set_preferences(
    body: Dict[str, str],
    operator: Dict[str, Any] = Depends(require_authority),
) -> Dict[str, Any]:
    user_id = body.get("user_id", "default")
    changes = {k: v for k, v in body.items()
               if k in ("cyclone", "lightning", "waves", "weather",
                        "restrictions", "geofence", "pfz", "forecast",
                        "sources", "data") and v in
               ("immediate", "important_only", "digest", "disabled")}
    prefs = {}
    for category, mode in changes.items():
        prefs = await _repo().set_preference(user_id, category, mode)
    return {"user_id": user_id, "preferences": prefs}


@router.get("/proactive")
async def proactive_status() -> Dict[str, Any]:
    engine = get_proactive_engine()
    return engine.stats()