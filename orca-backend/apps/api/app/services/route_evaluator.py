# Phase 5 - route evaluation with a transparent ROUTE_SCORE cost function.
#
# Pure, deterministic computation over real intersection data.  Hard
# constraints are authoritative: any ACTIVE static restriction, ACTIVE dynamic
# official restriction or ACTIVE high/critical warning intersection forces the
# route to score 0 (blocked) - no distance/optimization score may override it.
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

_KM_PER_DEG_LAT = 111.32

_SEVERITY_PENALTY = {
    "low": 0.05,
    "moderate": 0.15,
    "high": 0.30,
    "critical": 0.50,
    "unknown": 0.10,
}

_HARD_TYPES = {"restricted_area", "naval_exercise", "firing_exercise",
               "submarine_operation", "danger_area"}


@dataclass
class RouteIntersection:
    kind: str                       # static_restriction | dynamic_restriction | warning | geofence
    name: str
    restriction_type: str = ""
    severity: str = "unknown"
    active: bool = False
    source: str = ""
    source_record_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "restriction_type": self.restriction_type,
            "severity": self.severity,
            "active": self.active,
            "source": self.source,
            "source_record_id": self.source_record_id,
        }


@dataclass
class RouteEvaluation:
    route_length_km: float = 0.0
    intersections: List[RouteIntersection] = field(default_factory=list)
    hard_constraint: bool = False
    blocked: bool = False
    score: float = 1.0
    recommended: bool = False
    basis: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_length_km": round(self.route_length_km, 2),
            "intersection_count": len(self.intersections),
            "intersections": [i.to_dict() for i in self.intersections],
            "hard_constraint": self.hard_constraint,
            "blocked": self.blocked,
            "route_score": round(self.score, 3),
            "recommended": self.recommended,
            "basis": self.basis,
        }


def route_length_km(route: Sequence[Tuple[float, float]]) -> float:
    if len(route) < 2:
        return 0.0
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(route, route[1:]):
        dlat = abs(lat2 - lat1)
        dlon = abs(lon2 - lon1)
        lat_factor = _KM_PER_DEG_LAT
        lon_factor = _KM_PER_DEG_LAT * math.cos(math.radians((lat1 + lat2) / 2.0))
        total += math.hypot(dlat * lat_factor, dlon * lon_factor)
    return total


def evaluate_route(
    route: Sequence[Tuple[float, float]],
    restrictions: Optional[List[Dict[str, Any]]] = None,
    dynamic: Optional[List[Dict[str, Any]]] = None,
    geofences: Optional[List[Dict[str, Any]]] = None,
    warnings: Optional[List[Dict[str, Any]]] = None,
    length_km: Optional[float] = None,
) -> RouteEvaluation:
    """Score a route from the intersection evidence supplied by real tools.

    `dynamic` entries may be either already-shaped dicts from the MCP tool or
    DynamicRestriction.to_dict() payloads; both carry name/severity/active.
    """
    total_km = route_length_km(route) if length_km is None else length_km
    eval_ = RouteEvaluation(route_length_km=total_km)
    basis: List[str] = []

    def _ingest(entries: Optional[List[Dict[str, Any]]], kind: str) -> None:
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("area_name") or entry.get("warning_id") \
                or entry.get("restriction_id") or "?"
            active = bool(entry.get("active", False)) or entry.get("status") in ("active",)
            eval_.intersections.append(RouteIntersection(
                kind=kind,
                name=name,
                restriction_type=entry.get("restriction_type", ""),
                severity=entry.get("severity", "unknown"),
                active=active,
                source=entry.get("source", ""),
                source_record_id=entry.get("source_record_id", ""),
            ))

    _ingest(restrictions, "static_restriction")
    _ingest(dynamic, "dynamic_restriction")
    _ingest(geofences, "geofence")
    _ingest(warnings, "warning")

    active_hard = [
        i for i in eval_.intersections
        if i.active and (i.kind in ("static_restriction", "dynamic_restriction")
                         or i.restriction_type in _HARD_TYPES
                         or i.severity in ("high", "critical"))
    ]
    if active_hard:
        eval_.hard_constraint = True
        eval_.blocked = True
        eval_.score = 0.0
        basis.append(
            f"hard constraint: route intersects "
            + "; ".join(sorted({i.name for i in active_hard})[:3]))

    score = 1.0
    if not eval_.blocked:
        for intersection in eval_.intersections:
            if not intersection.active:
                continue
            score -= _SEVERITY_PENALTY.get(
                intersection.severity, _SEVERITY_PENALTY["unknown"])
        if total_km > 300:
            score -= 0.2
        elif total_km > 150:
            score -= 0.1
        score = max(0.0, min(1.0, score))
        eval_.score = round(score, 3)
        if total_km <= 250 and not eval_.intersections:
            basis.append("clear of active restrictions/warnings along the route")
        elif score > 0.5:
            basis.append("passable with caution under present conditions")

    eval_.recommended = not eval_.blocked and eval_.score >= 0.6
    eval_.basis = basis
    return eval_