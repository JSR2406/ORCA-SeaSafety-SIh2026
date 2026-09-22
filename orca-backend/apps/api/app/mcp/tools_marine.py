# Tool group: marine - ocean conditions, tide predictions and PFZ advisories
# from the Phase 1 MarineDataService.  All tools return the structured envelope.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.mcp.registry import READ_ONLY, ToolDefinition, ToolRegistry
from app.models.common import DataStatus
from app.services.geospatial_service import point_to_polygon_distance_m
from app.services.marine_data_service import MarineDataService


class OceanConditionsInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0, description="Latitude of the point of interest")
    lon: float = Field(ge=-180.0, le=180.0, description="Longitude of the point of interest")
    time: Optional[datetime] = Field(None, description="ISO-8601 observation time (omit for latest)")
    radius_km: float = Field(25.0, gt=0.0, le=500.0, description="Search radius in km")
    limit: int = Field(5, ge=1, le=50, description="Max observations to return")


class TidesInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    start: Optional[datetime] = Field(None, description="Start of the tide window (ISO-8601)")
    end: Optional[datetime] = Field(None, description="End of the tide window (ISO-8601)")
    radius_km: float = Field(50.0, gt=0.0, le=500.0)
    limit: int = Field(100, ge=1, le=500)


class PfzInput(BaseModel):
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude (nearest-zone search)")
    lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude (nearest-zone search)")
    date: Optional[datetime] = Field(None, description="Advisory date (ISO-8601)")
    radius_km: float = Field(50.0, gt=0.0, le=500.0)
    limit: int = Field(20, ge=1, le=100)


class PfzNearestInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0, description="Latitude of the point of interest")
    lon: float = Field(ge=-180.0, le=180.0, description="Longitude of the point of interest")
    date: Optional[datetime] = Field(None, description="Advisory date (ISO-8601)")
    radius_km: float = Field(200.0, gt=0.0, le=1000.0,
                             description="Search radius for candidate zones")
    limit: int = Field(3, ge=1, le=10, description="Max candidate zones to rank")


def _zone_centroid(zone: dict) -> Optional[tuple[float, float]]:
    geom = zone.get("geometry") or {}
    try:
        from shapely.geometry import shape
        centroid = shape(geom).centroid
        return float(centroid.y), float(centroid.x)
    except Exception:
        meta = zone.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("lat") is not None and meta.get("lon") is not None:
            return float(meta["lat"]), float(meta["lon"])
        return None


def register(registry: ToolRegistry, marine: MarineDataService) -> None:
    async def ocean_conditions(
        lat: float, lon: float, time: Optional[datetime] = None,
        radius_km: float = 25.0, limit: int = 5,
        ctx=None,
    ):
        return await marine.get_ocean_conditions(lat, lon, time=time, radius_km=radius_km, limit=limit)

    async def tides(
        lat: float, lon: float, start: Optional[datetime] = None,
        end: Optional[datetime] = None, radius_km: float = 50.0, limit: int = 100,
        ctx=None,
    ):
        return await marine.get_tides(lat, lon, start=start, end=end, radius_km=radius_km, limit=limit)

    async def pfz(
        lat: Optional[float] = None, lon: Optional[float] = None,
        date: Optional[datetime] = None, radius_km: float = 50.0, limit: int = 20,
        ctx=None,
    ):
        return await marine.get_pfz(lat=lat, lon=lon, date=date, radius_km=radius_km, limit=limit)

    async def pfz_nearest(
        lat: float, lon: float, date: Optional[datetime] = None,
        radius_km: float = 200.0, limit: int = 3,
        ctx=None,
    ):
        result = await marine.get_pfz(
            lat=lat, lon=lon, date=date, radius_km=radius_km, limit=limit)
        if result.status not in (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE):
            return {
                "status": result.status.value,
                "code": "data_not_found" if not result.data else "source_stale",
                "candidates": [],
                "warnings": result.warnings,
                "message": "No PFZ advisory zones available for the requested area/time.",
            }
        candidates = []
        for zone in result.data or []:
            centroid = _zone_centroid(zone)
            dist_m = point_to_polygon_distance_m(lat, lon, zone.get("geometry") or {})
            candidates.append({
                "zone_id": zone.get("source_record_id"),
                "source": zone.get("source"),
                "location": {"lat": centroid[0], "lon": centroid[1]} if centroid else None,
                "distance_km": (round(dist_m / 1000.0, 1)
                                if dist_m is not None else None),
                "inside": True if dist_m == 0.0 else False,
                "generated_at": zone.get("generated_at"),
                "valid_until": zone.get("valid_until"),
                "suite": (zone.get("metadata") or {}).get("suite")
                if isinstance(zone.get("metadata"), dict) else None,
            })
        candidates.sort(key=lambda c: (c["inside"] is not True, c["distance_km"] or float("inf")))
        return {
            "status": "live",
            "point": {"lat": lat, "lon": lon},
            "candidate_count": len(candidates),
            "candidates": candidates[:limit],
        }

    registry.register(ToolDefinition(
        name="marine.ocean_conditions",
        fn=ocean_conditions,
        title="Ocean conditions",
        description=("Current ocean surface conditions (SST, wave height, wind, current) "
                     "nearest a point, within the configured freshness window."),
        group="marine",
        safety=READ_ONLY,
        input_model=OceanConditionsInput,
    ))
    registry.register(ToolDefinition(
        name="marine.tides",
        fn=tides,
        title="Tide predictions",
        description="Tide predictions for a location over an optional time window.",
        group="marine",
        safety=READ_ONLY,
        input_model=TidesInput,
    ))
    registry.register(ToolDefinition(
        name="marine.pfz",
        fn=pfz,
        title="Potential Fishing Zones",
        description="PFZ advisory zones near a point or within the storage for a date.",
        group="marine",
        safety=READ_ONLY,
        input_model=PfzInput,
    ))
    registry.register(ToolDefinition(
        name="marine.pfz_nearest",
        fn=pfz_nearest,
        title="Nearest PFZ advisory zone",
        description=("Deterministic rank of the PFZ advisory zones nearest a point, with "
                     "distance (km), inside/outside flag and zone lineage.  Used to steer "
                     "a fishing trip toward the closest INCOIS advisory area."),
        group="marine",
        safety=READ_ONLY,
        input_model=PfzNearestInput,
    ))