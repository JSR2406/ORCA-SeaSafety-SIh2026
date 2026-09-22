# Tool group: restriction - decision-useful composition over restricted areas
# and marine warnings.  `restriction.check_point` folds active restrictions and
# warnings into a single advisory (hard constraints surface regardless of any
# ML scoring); `distance` and `near_route` reuse the stored geometries.
from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from app.mcp.registry import READ_ONLY, SPATIAL_ANALYSIS, DECISION_SUPPORT, ToolDefinition, ToolRegistry
from app.models.common import DataStatus
from app.models.warnings import WarningStatus
from app.services.geospatial_service import GeospatialService
from app.services.marine_data_service import MarineDataService


class RestrictionCheckInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


class RestrictionDistanceInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


class RestrictionNearRouteInput(BaseModel):
    route: List[Tuple[float, float]] = Field(
        ..., min_length=1, description="Route as [[lat, lon], ...] in order")
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


class DynamicActiveInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    include_static_geofences: bool = Field(
        True, description="Fold in static geofence (EEZ/MPA) containment hits")


def _live_or_first(*results):
    """Pick the first envelope carrying data; survive wholly-empty queries."""
    for r in results:
        if getattr(r, "status", None) in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return r
    for r in results:
        if r.status != DataStatus.NOT_CONFIGURED:
            return r
    return results[0]


def register(
    registry: ToolRegistry,
    marine: MarineDataService,
    geo: GeospatialService,
    dynamic=None,
) -> None:

    async def check_point(lat: float, lon: float, time: Optional[datetime] = None, ctx=None):
        res_area = await geo.check_point_in_restricted_area(lat, lon, time=time)
        warn = await marine.get_marine_warnings(lat=lat, lon=lon, active_at=time)
        if res_area.status in (DataStatus.NOT_CONFIGURED, DataStatus.ERROR):
            return res_area

        inside = (res_area.data or {}).get("active_restrictions") or []
        active_warnings = []
        if warn.data:
            active_warnings = [w for w in warn.data if w.get("status") == WarningStatus.ACTIVE]
        elif warn.status == DataStatus.NOT_CONFIGURED:
            res_area.warnings = (res_area.warnings or []) + [
                "Marine warnings source not configured; advisory covers restrictions only."
            ]

        restricted = bool(inside) or bool(active_warnings)
        reasons = [f"Inside {a.get('area_name')}" for a in inside]
        reasons += [
            f"{w.get('warning_type')} warning ({w.get('severity')}): {w.get('description')}"
            for w in active_warnings
        ]

        if not restricted and res_area.status in (
            DataStatus.UNAVAILABLE, DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE
        ):
            res_area.status = DataStatus.LIVE
        res_area.data = {
            "restricted": restricted,
            "inside_restricted_area": bool(inside),
            "inside_areas": inside,
            "active_warnings": active_warnings,
            "warning_count": len(active_warnings),
            "reasons": reasons,
        }
        return res_area

    async def distance(lat: float, lon: float, time: Optional[datetime] = None, ctx=None):
        return await geo.distance_to_nearest_restricted_area(lat, lon, time=time)

    async def near_route(route: List[Tuple[float, float]], time: Optional[datetime] = None, ctx=None):
        res_areas = await geo.restrictions_near_route(route, time=time)
        res_warn = await geo.warnings_near_route(route, time=time)
        base = _live_or_first(res_areas, res_warn)

        area_data = (res_areas.data or {}) if isinstance(res_areas.data, dict) else {}
        warn_data = (res_warn.data or {}) if isinstance(res_warn.data, dict) else {}
        merged = {
            "restricted": bool(area_data.get("route_intersects_restricted_count")),
            **area_data,
            **warn_data,
        }
        if base.data is None:
            base.status = DataStatus.LIVE
        base.data = merged
        return base

    async def dynamic_active(
        lat: float, lon: float, include_static_geofences: bool = True,
        ctx=None,
    ):
        if dynamic is None:
            return {
                "status": "unavailable",
                "code": "source_unavailable",
                "message": "Dynamic restriction service not wired into this registry.",
                "active_dynamic": [],
                "static_geofence_hits": [],
                "restricted": False,
            }
        await dynamic.refresh()
        active = await dynamic.active_at(lat, lon)
        entries = [r.to_dict() for r in active]
        per_item = []
        for item in active:
            distance_m = item.distance_to(lat, lon)
            per_item.append({
                "restriction_id": item.restriction_id,
                "name": item.name,
                "severity": item.severity,
                "restriction_type": item.restriction_type,
                "source": item.source,
                "official": item.official,
                "valid_from": item.valid_from.isoformat() if item.valid_from else None,
                "valid_until": item.valid_until.isoformat() if item.valid_until else None,
                "issued_at": item.issued_at.isoformat() if item.issued_at else None,
                "refreshed_at": item.refreshed_at.isoformat() if item.refreshed_at else None,
                "geometry": item.geometry,
                "distance_km": (round(distance_m / 1000.0, 2)
                                if distance_m is not None else None),
                "inside": bool(distance_m == 0.0),
            })
        if not entries:
            await dynamic.refresh()
        hits = []
        if include_static_geofences:
            hits = dynamic.static_geofence_hits(lat, lon)
        restricted = bool(per_item)
        return {
            "status": "live",
            "code": None,
            "point": {"lat": lat, "lon": lon},
            "restricted": restricted,
            "active_dynamic": per_item,
            "static_geofence_hits": hits,
            "note": ("Dynamic restrictions are official, time-windowed advisories "
                     "refreshed from authoritative feeds; static geofences are "
                     "documented permanent boundaries."),
        }

    registry.register(ToolDefinition(
        name="restriction.check_point",
        fn=check_point,
        title="Check restrictions at a point",
        description=(
            "Decision-useful restriction check: is the point inside an active restricted "
            "area or covered by an active marine warning? Returns structured reasons."
        ),
        group="restriction",
        safety=DECISION_SUPPORT,
        input_model=RestrictionCheckInput,
    ))
    registry.register(ToolDefinition(
        name="restriction.distance",
        fn=distance,
        title="Distance to nearest restriction",
        description="Approximate distance (metres) from a point to the nearest restricted area.",
        group="restriction",
        safety=READ_ONLY,
        input_model=RestrictionDistanceInput,
    ))
    registry.register(ToolDefinition(
        name="restriction.near_route",
        fn=near_route,
        title="Restrictions along a route",
        description=(
            "Restricted areas and active marine warnings intersected by a route "
            "([[lat, lon], ...])."
        ),
        group="restriction",
        safety=SPATIAL_ANALYSIS,
        input_model=RestrictionNearRouteInput,
    ))
    registry.register(ToolDefinition(
        name="restriction.dynamic_active",
        fn=dynamic_active,
        title="Active dynamic restrictions at a point",
        description=(
            "Live, official, time-windowed restrictions (NAVAREA/NAVTEX advisories, "
            "naval/firing exercises, temporary closures) active at a point, plus static "
            "EEZ/MPA geofence containment.  First-class layer over static restricted "
            "areas; refreshed from official feeds."
        ),
        group="restriction",
        safety=DECISION_SUPPORT,
        input_model=DynamicActiveInput,
    ))