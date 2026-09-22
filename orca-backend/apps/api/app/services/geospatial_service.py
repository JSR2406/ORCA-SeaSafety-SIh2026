# GeospatialService - spatial reasoning over stored marine geometries.
# Thin layer over the MarineDataService + shapely for containment, distance and
# route-intersection checks.  Pure geometry helpers are unit-testable without
# a database; DB-backed queries go through the marine service (no fabrication).
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import structlog
from shapely.geometry import LineString, Point, shape

from app.config import Settings
from app.models.common import DataStatus
from app.models.result import MarineDataResult
from app.services.marine_data_service import MarineDataService
from app.models.warnings import WarningStatus, evaluate_window_status

logger = structlog.get_logger(__name__)

_KM_PER_DEG_LAT = 111.32


def point_to_polygon_distance_m(
    lat: float, lon: float, geojson: Dict, max_km: float = 100.0
) -> Optional[float]:
    """Distance (m) from a point to a GeoJSON polygon (approximate geodesic).

    Uses equirectangular scaling so distances are sensible at working latitudes.
    Returns None when the geometry is not parseable or the point is within the
    requested max_km search radius (inside -> distance 0).
    """
    try:
        geom = shape(geojson)
    except Exception:
        return None
    pt = Point(lon, lat)
    if geom.is_empty:
        return None
    if geom.contains(pt) or geom.distance(pt) == 0:
        return 0.0
    deg_dist = geom.distance(pt)
    # equirectangular approximation: convert degree distance to metres
    lat_factor = _KM_PER_DEG_LAT
    lon_factor = _KM_PER_DEG_LAT * math.cos(math.radians(lat))
    km = math.hypot(deg_dist * lon_factor, deg_dist * lat_factor)
    if km > max_km:
        return None
    return round(km * 1000.0, 1)


def point_in_polygon(lat: float, lon: float, geojson: Dict) -> bool:
    """Pure shapely containment check (no DB)."""
    try:
        geom = shape(geojson)
    except Exception:
        return False
    return geom.contains(Point(lon, lat))


class GeospatialService:
    """Spatial queries over stored marine geometries (PFZ / restrictions)."""

    def __init__(self, settings: Settings, marine_service: MarineDataService):
        self.settings = settings
        self.marine = marine_service

    async def check_point_in_pfz(
        self, lat: float, lon: float, date: Optional[datetime] = None
    ) -> MarineDataResult:
        result = await self.marine.get_pfz(lat=lat, lon=lon, date=date, limit=50)
        if result.status not in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return result
        zones = result.data or []
        inside = [z for z in zones if point_in_polygon(lat, lon, z.get("geometry") or {})]
        result.data = {
            "inside_pfz": bool(inside),
            "containing_zones": inside,
            "nearby_zones": len(zones),
        }
        if not zones:
            result.status = DataStatus.UNAVAILABLE
        return result

    async def check_point_in_restricted_area(
        self, lat: float, lon: float, time: Optional[datetime] = None
    ) -> MarineDataResult:
        result = await self.marine.get_restricted_areas(lat=lat, lon=lon, time=time)
        if result.status not in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return result
        areas = result.data or []
        now = time or result.timestamps.requested_at
        inside = [a for a in areas if point_in_polygon(lat, lon, a.get("geometry") or {})]
        for area in inside:
            area.setdefault("status", evaluate_window_status(
                area.get("valid_from"), area.get("valid_until"), now))
        active_inside = [a for a in inside if a.get("status") == WarningStatus.ACTIVE]
        result.data = {
            "inside_restricted_area": bool(active_inside),
            "inside_areas": inside,
            "active_restrictions": active_inside,
        }
        return result

    async def distance_to_nearest_restricted_area(
        self, lat: float, lon: float, time: Optional[datetime] = None
    ) -> MarineDataResult:
        result = await self.marine.get_restricted_areas(lat=lat, lon=lon, time=time)
        if result.status not in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return result
        areas = result.data or []
        best = None  # (name, distance_m)
        for area in areas:
            dist = point_to_polygon_distance_m(lat, lon, area.get("geometry") or {})
            if dist is None:
                continue
            if best is None or dist < best[1]:
                best = (area.get("area_name"), dist)
        result.data = {
            "nearest_restricted_area": best[0] if best else None,
            "distance_m": best[1] if best else None,
            "searched_areas": len(areas),
        }
        return result

    async def restrictions_near_route(
        self, route: Sequence[Tuple[float, float]], time: Optional[datetime] = None
    ) -> MarineDataResult:
        if not route:
            raise ValueError("route must contain at least one point")
        for lat, lon in route:
            self.marine._validate_point(lat, lon)
        all_areas = await self.marine.get_restricted_areas(time=time)
        if all_areas.status not in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return all_areas
        areas = all_areas.data or []
        try:
            line = LineString([(lon, lat) for lat, lon in route])
        except Exception:
            return MarineDataResult(status=DataStatus.ERROR,
                                    error="route could not be built as a geometry")
        now = time or all_areas.timestamps.requested_at
        intersections: List[Dict[str, Any]] = []
        for area in areas:
            try:
                geom = shape(area.get("geometry") or {})
            except Exception:
                continue
            if geom.is_empty or not geom.intersects(line):
                continue
            status = evaluate_window_status(area.get("valid_from"), area.get("valid_until"), now)
            intersections.append({
                "area_id": area.get("area_id"),
                "area_name": area.get("area_name"),
                "restriction_type": area.get("restriction_type"),
                "restriction_kind": area.get("restriction_kind"),
                "status": status,
            })
        all_areas.data = {
            "route_intersects_restricted_count": len(intersections),
            "intersections": intersections,
        }
        return all_areas

    async def warnings_near_route(
        self, route: Sequence[Tuple[float, float]], time: Optional[datetime] = None
    ) -> MarineDataResult:
        """Active/windowed marine warnings intersected by a route."""
        if not route:
            raise ValueError("route must contain at least one point")
        for lat, lon in route:
            self.marine._validate_point(lat, lon)
        all_warnings = await self.marine.get_marine_warnings(active_at=time)
        if all_warnings.status not in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return all_warnings
        warnings = all_warnings.data or []
        try:
            line = LineString([(lon, lat) for lat, lon in route])
        except Exception:
            return MarineDataResult(status=DataStatus.ERROR,
                                    error="route could not be built as a geometry")
        now = time or all_warnings.timestamps.requested_at
        intersections: List[Dict[str, Any]] = []
        for warning in warnings:
            try:
                geom = shape(warning.get("geometry") or {})
            except Exception:
                continue
            if geom.is_empty or not geom.intersects(line):
                continue
            status = evaluate_window_status(warning.get("valid_from"), warning.get("valid_until"), now)
            intersections.append({
                "warning_id": warning.get("warning_id"),
                "warning_type": warning.get("warning_type"),
                "severity": warning.get("severity"),
                "status": status,
                "description": warning.get("description"),
            })
        all_warnings.data = {
            "warnings_intersecting": len(intersections),
            "warning_intersections": intersections,
        }
        return all_warnings