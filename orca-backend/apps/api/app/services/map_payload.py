# Phase 6 - map payload builder.
#
# A single GeoJSON FeatureCollection derived from the same evidence synthesis
# renders.  Features carry explicit provenance (source), validity windows,
# deterministic confidence and the official/derived flag, so the front end can
# render official layers (warnings, restrictions, geofences) distinctly from
# model-derived layers (potential, risk) without the backend guessing a style.
from datetime import datetime, timezone
from math import cos, pi, sin
from typing import Any, Dict, List, Optional, Tuple

from app.orchestration.models import Intent, IntentName
from app.services.evidence_helpers import find, find_list, fused_freshness

CONFIDENCE_BY_FRESHNESS = {
    "fresh": 1.0,
    "recent": 0.9,
    "aging": 0.8,
    "stale": 0.5,
    "expired": 0.3,
    "unknown": 0.4,
}

_RISK_SEVERITY = {
    "critical": "critical",
    "elevated": "high",
    "high": "high",
    "moderate": "moderate",
    "low": "low",
}


def confidence_from_freshness(overall: str) -> float:
    return CONFIDENCE_BY_FRESHNESS.get(str(overall or "unknown").lower(), 0.4)


def _feature(feature_id: str, geometry: Dict[str, Any],
             properties: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "Feature", "id": feature_id, "geometry": geometry,
            "properties": properties or {}}


def _point(lat: float, lon: float) -> Dict[str, Any]:
    return {"type": "Point", "coordinates": [lon, lat]}


def _line(coords: List[Tuple[float, float]]) -> Dict[str, Any]:
    return {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coords]}


def _circle(lat: float, lon: float, radius_km: float,
            steps: int = 32) -> Optional[Dict[str, Any]]:
    if radius_km is None or radius_km <= 0:
        return None
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * max(cos(lat * pi / 180.0), 0.05)
    ring = []
    for step in range(steps):
        angle = 2.0 * pi * step / steps
        dlat = (radius_km * 1000.0 * sin(angle)) / m_per_deg_lat
        dlon = (radius_km * 1000.0 * cos(angle)) / m_per_deg_lon
        ring.append([lon + dlon, lat + dlat])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _base_props(kind: str, data_class: str, source: str, at: datetime,
                official: bool = False, severity: str = "",
                status: str = "live", confidence: Optional[float] = None,
                name: str = "") -> Dict[str, Any]:
    props: Dict[str, Any] = {
        "kind": kind,
        "data_class": data_class,
        "source": source,
        "timestamp": at.isoformat(),
        "official": official,
        "status": status,
    }
    if official:
        props["official"] = True
    if severity:
        props["severity"] = severity
    if confidence is not None:
        props["confidence"] = confidence
    if name:
        props["name"] = name
    return props


def _query_point_feature(intent: Intent, at: datetime) -> Optional[Dict[str, Any]]:
    location = intent.location
    if not location:
        return None
    props = _base_props("query_point", "query", "user", at, name="query point")
    if intent.offset:
        props["offset"] = intent.offset
    return _feature(
        f"point:{location['lat']}:{location['lon']}",
        _point(location["lat"], location["lon"]), props)


def _pfz_features(intent: Intent, evidence: Dict[str, Any], at: datetime,
                  confidence: float, overall: str) -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    pfz = find(evidence, "pfz_nearest", "marine.pfz_nearest")
    point = pfz.get("point")
    if isinstance(point, dict) and point.get("radius_km"):
        props = _base_props("search_area", "query", "marine.pfz_nearest", at,
                            name="Nearest PFZ search radius")
        props["confidence"] = confidence
        circle = _circle(point["lat"], point["lon"], point["radius_km"])
        if circle:
            features.append(_feature(
                f"search:{point['lat']}:{point['lon']}", circle, props))
    for candidate in (pfz.get("candidates") or [])[:3]:
        zone = candidate.get("zone_id") or "zone"
        loc = candidate.get("location")
        if not isinstance(loc, dict) or loc.get("lat") is None:
            continue
        props = _base_props(
            "pfz_zone", "advisory", "marine.pfz_nearest", at,
            official=True, name=str(zone),
            confidence=confidence)
        props["zone_id"] = zone
        props["distance_km"] = candidate.get("distance_km")
        props["inside"] = candidate.get("inside", False)
        props["valid_from"] = candidate.get("valid_from")
        props["valid_until"] = candidate.get("valid_until")
        props["generated_at"] = candidate.get("generated_at")
        features.append(_feature(f"pfz:{zone}", _point(loc["lat"], loc["lon"]),
                                 props))
    return features


def _safety_features(intent: Intent, evidence: Dict[str, Any], at: datetime,
                     confidence: float) -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    safety = find(evidence, "marine_safety_check", "safety.marine_safety_check")
    for warning in (safety.get("active_warnings") or []):
        geometry = warning.get("geometry")
        if not isinstance(geometry, dict):
            continue
        severity = warning.get("severity") or "moderate"
        props = _base_props(
            "warning", "advisory", "safety.marine_safety_check", at,
            official=True, severity=severity,
            status=str(warning.get("status") or "active"),
            confidence=confidence,
            name=warning.get("warning_type") or warning.get("description") or "")
        props["warning_id"] = warning.get("warning_id")
        props["valid_from"] = warning.get("valid_from")
        props["valid_until"] = warning.get("valid_until")
        features.append(_feature(
            f"warning:{warning.get('warning_id') or 'w'}",
            _as_polygon_if_needed(geometry), props))

    risk = find(evidence, "risk_profile", "analytics.risk_profile")
    if risk.get("point"):
        level = str(risk.get("level") or "unknown").lower()
        props = _base_props(
            "risk_point", "model_prediction", "analytics.risk_profile", at,
            severity=_RISK_SEVERITY.get(level, "unknown"),
            confidence=confidence,
            name="risk point")
        props["risk_level"] = level
        props["hard_constraint"] = risk.get("hard_constraint", False)
        features.append(_feature(
            f"risk:{risk['point']['lat']}:{risk['point']['lon']}",
            _point(risk["point"]["lat"], risk["point"]["lon"]), props))

    for dynamic in find_list(evidence, "dynamic_restrictions"):
        for item in dynamic.get("active_dynamic") or []:
            geometry = item.get("geometry")
            if not isinstance(geometry, dict):
                continue
            severity = item.get("severity") or "moderate"
            props = _base_props(
                "dynamic_restriction", "advisory",
                item.get("source") or "restriction.dynamic_active", at,
                official=bool(item.get("official", True)),
                severity=severity, status="active", confidence=confidence,
                name=item.get("name") or item.get("restriction_id"))
            props["restriction_id"] = item.get("restriction_id")
            props["valid_from"] = item.get("valid_from")
            props["valid_until"] = item.get("valid_until")
            features.append(_feature(
                f"restriction:{item.get('restriction_id') or 'r'}",
                _as_polygon_if_needed(geometry), props))
        for geofence in dynamic.get("static_geofence_hits") or []:
            geometry = geofence.get("geometry")
            if not isinstance(geometry, dict):
                continue
            props = _base_props(
                "geofence", "observation", "geofence_catalog", at,
                official=True, severity=geofence.get("severity") or "moderate",
                status="permanent", confidence=confidence,
                name=geofence.get("name") or geofence.get("geofence_id"))
            props["geofence_id"] = geofence.get("geofence_id")
            features.append(_feature(
                f"geofence:{geofence.get('geofence_id') or 'g'}",
                _as_polygon_if_needed(geometry), props))
    return features


def _route_features(intent: Intent, evidence: Dict[str, Any], at: datetime,
                    confidence: float) -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    if not intent.route:
        return features
    restrictions = find(evidence, "restrictions_near_route",
                        "geospatial.restrictions_near_route")
    data = restrictions.get("data") if isinstance(restrictions.get("data"), dict) \
        else restrictions
    count = int(data.get("route_intersects_restricted_count") or 0) \
        if isinstance(data, dict) else 0
    props = _base_props(
        "route", "query", "user", at, name="requested route",
        confidence=confidence)
    props["blocked"] = count > 0
    props["intersections"] = count
    features.append(_feature("route:primary", _line(intent.route), props))
    for index, intersection in enumerate(data.get("intersections") or []):
        props = _base_props(
            "route_intersection", "advisory", "geospatial.restrictions_near_route",
            at, official=True, severity="moderate",
            status=str(intersection.get("status") or "active"),
            confidence=confidence,
            name=intersection.get("area_name"))
        props["area_id"] = intersection.get("area_id")
        props["restriction_type"] = intersection.get("restriction_type")
        features.append(_feature(
            f"intersection:{index}", None, props))
    return features


def _as_polygon_if_needed(geometry: Dict[str, Any]) -> Dict[str, Any]:
    if geometry.get("type") in ("Point", "LineString"):
        return _expand_to_polygon(geometry)
    return geometry


def _expand_to_polygon(geometry: Dict[str, Any]) -> Dict[str, Any]:
    coords = geometry.get("coordinates")
    if geometry.get("type") == "Point" and isinstance(coords, list) \
            and len(coords) >= 2:
        lon, lat = coords[0], coords[1]
        return _circle(lat, lon, 5.0) or geometry
    return geometry


def build_map_payload(intent: Intent, evidence: Dict[str, Any],
                      language: str = "en-IN",
                      at: datetime = None) -> Dict[str, Any]:
    from datetime import datetime, timezone
    at = at or datetime.now(timezone.utc)
    features: List[Dict[str, Any]] = []

    freshness = fused_freshness(evidence)
    overall = str(freshness.get("overall") or "unknown")
    confidence = confidence_from_freshness(overall)

    point = _query_point_feature(intent, at)
    if point:
        features.append(point)

    if intent.name == IntentName.PFZ:
        features += _pfz_features(intent, evidence, at, confidence, overall)
    if intent.name in (IntentName.SAFETY, IntentName.BRIEFING,
                       IntentName.FISHING, IntentName.PRODUCTIVITY,
                       IntentName.ROUTE):
        features += _safety_features(intent, evidence, at, confidence)
    if intent.name == IntentName.ROUTE:
        features += _route_features(intent, evidence, at, confidence)

    return {
        "type": "FeatureCollection",
        "features": features,
        "generated_at": at.isoformat(),
        "meta": {
            "confidence": confidence,
            "freshness": overall,
            "language": language,
        },
    }