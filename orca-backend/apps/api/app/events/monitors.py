# Phase 11 - geofence + restriction lifecycle monitoring.
#
# GeofenceMonitor:
#   GPS/location -> PostGIS spatial query (approx polygons offline via
#   geospatial_service.geofence_catalog) -> distance calc -> state -> event.
#   States: OUTSIDE / APPROACHING / INSIDE / EXITED.
#   No repeated alerts while the state for that (vessel, geofence) is unchanged.
#
# RestrictionMonitor:
#   tracks temporary restrictions / MPAs / IMBL / EEZ / operational geofences
#   and their lifecycle (scheduled -> activated -> updated -> extended ->
#   expired / cancelled).  Every restriction retains source, geometry,
#   valid_from, valid_to, status, description.
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.events.model import EventSeverity, MarineEvent, MarineEventType, utcnow
from app.services.geofence_catalog import get_geofence_catalog
from app.services.geospatial_service import (
    point_in_polygon, point_to_polygon_distance_m,
)


class GeofenceState(str, Enum):
    OUTSIDE = "OUTSIDE"
    APPROACHING = "APPROACHING"
    INSIDE = "INSIDE"
    EXITED = "EXITED"


@dataclass
class VesselGeofenceTrack:
    vessel_id: str
    geofence_id: str
    state: GeofenceState = GeofenceState.OUTSIDE
    last_event: Optional[MarineEvent] = None
    last_emitted_state: Optional[GeofenceState] = None


class GeofenceMonitor:
    """Tracks each (vessel, geofence) transition and emits events only on a
    material state change (no repeat alerts for the same state)."""

    def __init__(self, approach_km: float = 25.0,
                 max_active: int = 64) -> None:
        self.approach_km = approach_km
        self.max_active = max_active
        self.tracks: Dict[tuple, VesselGeofenceTrack] = {}

    def _key(self, vessel_id: str, geofence_id: str) -> tuple:
        return (vessel_id, geofence_id)

    def observe(self, vessel_id: str, lat: float, lon: float,
                *,
                geofence: Optional[Dict[str, Any]] = None,
                at: Optional[datetime] = None) -> Optional[MarineEvent]:
        """Evaluate location vs every geofence; return the FIRST new event, if
        any.  Uses the offline catalog when no explicit geofence is given."""
        at = at or utcnow()
        geofences = [geofence] if geofence else get_geofence_catalog().list_geofences()
        event = None
        for gf in geofences:
            gf_id = gf.get("geofence_id") or gf.get("name") or "geofence"
            key = self._key(vessel_id, gf_id)
            track = self.tracks.setdefault(key, VesselGeofenceTrack(vessel_id, gf_id))
            next_state = self._state_for(lat, lon, gf)
            if next_state != track.state:
                emitted = self._emit(track, next_state, gf, lat, lon, at)
                if emitted is not None and event is None:
                    event = emitted
            track.state = next_state
        # enforce bounded track count
        if len(self.tracks) > self.max_active:
            # drop oldest OLD (OUTSIDE-only) tracks
            for k in list(self.tracks.keys()):
                if len(self.tracks) <= self.max_active:
                    break
                if self.tracks[k].state == GeofenceState.OUTSIDE:
                    del self.tracks[k]
        return event

    def _state_for(self, lat: float, lon: float, geofence: Dict[str, Any]) -> GeofenceState:
        geometry = geofence.get("geometry")
        if not geometry:
            return GeofenceState.OUTSIDE
        if point_in_polygon(lat, lon, geometry):
            return GeofenceState.INSIDE
        distance_m = point_to_polygon_distance_m(lat, lon, geometry)
        if distance_m is None:
            return GeofenceState.OUTSIDE
        if distance_m <= self.approach_km * 1000.0:
            return GeofenceState.APPROACHING
        return GeofenceState.OUTSIDE

    def _emit(self, track: VesselGeofenceTrack, next_state: GeofenceState,
              geofence: Dict[str, Any], lat: float, lon: float,
              at: datetime) -> Optional[MarineEvent]:
        name = geofence.get("name") or track.geofence_id
        mapping = {
            GeofenceState.APPROACHING: (MarineEventType.GEOFENCE_APPROACH,
                                        EventSeverity.CAUTION),
            GeofenceState.INSIDE: (MarineEventType.GEOFENCE_ENTRY,
                                   EventSeverity.WARNING),
            GeofenceState.EXITED: (MarineEventType.GEOFENCE_EXIT,
                                   EventSeverity.INFO),
        }
        if next_state not in mapping:
            return None
        event_type, severity = mapping[next_state]
        ev = MarineEvent(
            event_id="",
            event_type=event_type,
            source="geofence.monitor",
            timestamp=at,
            location={"lat": lat, "lon": lon},
            geometry=geofence.get("geometry"),
            severity=severity,
            current_state={"state": next_state.value},
            validity={"freshness": "live"},
            metadata={
                "stable_key": f"{track.vessel_id}|{track.geofence_id}|{next_state.value}",
                "name": name,
                "vessel_id": track.vessel_id,
            },
        )
        # stable id from the definite transition (avoid per-tick hash churn)
        track.last_event = ev
        return ev


# ---------------------------------------------------------------------------
# Restriction lifecycle
# ---------------------------------------------------------------------------
class RestrictionLifecycleState(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVATED = "activated"
    UPDATED = "updated"
    EXTENDED = "extended"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class TrackedRestriction:
    restriction_id: str
    source: str
    name: str
    geometry: Optional[Dict[str, Any]] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    status: str = "scheduled"
    description: str = ""
    lifecycle: RestrictionLifecycleState = RestrictionLifecycleState.SCHEDULED


class RestrictionMonitor:
    """Tracks restriction lifecycle transitions and emits normalized events."""

    def __init__(self, max_active: int = 256) -> None:
        self.max_active = max_active
        self.restrictions: Dict[str, TrackedRestriction] = {}

    def upsert(self, restriction: Dict[str, Any],
               at: Optional[datetime] = None) -> Optional[MarineEvent]:
        at = at or utcnow()
        rid = restriction.get("restriction_id") or restriction.get("area_id") \
            or restriction.get("name") or "restriction"
        previous = self.restrictions.get(rid)
        now_state = self._state_for(restriction, at)

        if previous is None:
            track = TrackedRestriction(
                restriction_id=rid,
                source=restriction.get("source") or "restriction",
                name=restriction.get("name") or rid,
                geometry=restriction.get("geometry"),
                valid_from=self._iso(restriction.get("valid_from")),
                valid_until=self._iso(restriction.get("valid_until")),
                status=now_state,
                description=restriction.get("description") or "",
                lifecycle=self._lifecycle_for(now_state, previous_state=None),
            )
            self.restrictions[rid] = track
            return self._event(track, MarineEventType.RESTRICTION_ACTIVATED,
                               EventSeverity.WARNING, at) \
                if now_state in ("activated", "active") else None

        # transition
        changed = (now_state != previous.status)
        lifecycle = self._lifecycle_for(now_state, previous.lifecycle)
        previous.status = now_state
        previous.lifecycle = lifecycle
        previous.valid_from = self._iso(restriction.get("valid_from")) or previous.valid_from
        previous.valid_until = self._iso(restriction.get("valid_until")) or previous.valid_until
        previous.description = restriction.get("description") or previous.description

        if not changed:
            return None

        mapping = {
            "activated": (MarineEventType.RESTRICTION_ACTIVATED, EventSeverity.WARNING),
            "active": (MarineEventType.RESTRICTION_ACTIVATED, EventSeverity.WARNING),
            "updated": (MarineEventType.RESTRICTION_UPDATED, EventSeverity.CAUTION),
            "cancelled": (MarineEventType.RESTRICTION_EXPIRED, EventSeverity.INFO),
            "expired": (MarineEventType.RESTRICTION_EXPIRED, EventSeverity.INFO),
            "scheduled": (MarineEventType.RESTRICTION_UPDATED, EventSeverity.INFO),
        }
        event_type, severity = mapping.get(now_state)
        if event_type is None:
            return None
        return self._event(previous, event_type, severity, at)

    def expire_due(self, at: Optional[datetime] = None) -> List[MarineEvent]:
        at = at or utcnow()
        events = []
        for rid, track in list(self.restrictions.items()):
            until = _parse(track.valid_until)
            if until is not None and until < at and track.status != "expired":
                track.status = "expired"
                track.lifecycle = RestrictionLifecycleState.EXPIRED
                events.append(self._event(track, MarineEventType.RESTRICTION_EXPIRED,
                                          EventSeverity.INFO, at))
        return events

    @staticmethod
    def _lifecycle_for(status: str,
                       previous_state: Optional[RestrictionLifecycleState]) -> RestrictionLifecycleState:
        mapping = {
            "scheduled": RestrictionLifecycleState.SCHEDULED,
            "activated": RestrictionLifecycleState.ACTIVATED,
            "active": RestrictionLifecycleState.ACTIVATED,
            "updated": RestrictionLifecycleState.UPDATED,
            "expired": RestrictionLifecycleState.EXPIRED,
            "cancelled": RestrictionLifecycleState.CANCELLED,
        }
        return mapping.get(status, RestrictionLifecycleState.SCHEDULED)

    @staticmethod
    def _state_for(restriction: Dict[str, Any], at: datetime) -> str:
        status = (restriction.get("status") or "").lower()
        valid_from = _parse(restriction.get("valid_from"))
        valid_until = _parse(restriction.get("valid_until"))
        if status in ("cancelled",):
            return "cancelled"
        if status in ("expired",):
            return "expired"
        if valid_until is not None and at > valid_until:
            return "expired"
        if status in ("active", "activated"):
            return "active"
        if valid_from is not None and at < valid_from:
            return "scheduled"
        if status in ("updated", "extended"):
            return "updated"
        return "active"

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
    def _event(track: TrackedRestriction, event_type: MarineEventType,
               severity: EventSeverity, at: datetime) -> MarineEvent:
        return MarineEvent(
            event_id="",
            event_type=event_type,
            source=track.source,
            timestamp=at,
            geometry=track.geometry,
            severity=severity,
            current_state={"restriction_id": track.restriction_id,
                           "status": track.status},
            validity={"valid_from": track.valid_from,
                      "valid_until": track.valid_until,
                      "freshness": "live"},
            metadata={
                "stable_key": f"{track.source}|{track.restriction_id}|{track.status}",
                "name": track.name,
                "description": track.description,
            },
        )


def _parse(value: str):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None