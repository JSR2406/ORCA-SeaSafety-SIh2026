# Tool group: geospatial - spatial reasoning over PFZ and restricted-area
# geometries.  Pure shapely analysis on geometries already stored in PostGIS.
from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from app.mcp.registry import READ_ONLY, SPATIAL_ANALYSIS, ToolDefinition, ToolRegistry
from app.services.geospatial_service import GeospatialService


class PfzContainsInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    date: Optional[datetime] = Field(None, description="Advisory date (ISO-8601)")


class PointInRestrictedInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


class DistanceToRestrictedInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


class RestrictionsNearRouteInput(BaseModel):
    route: List[Tuple[float, float]] = Field(
        ..., min_length=1, description="Route as [[lat, lon], ...] in order")
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


def register(registry: ToolRegistry, geo: GeospatialService) -> None:
    async def pfz_contains(lat: float, lon: float, date: Optional[datetime] = None, ctx=None):
        return await geo.check_point_in_pfz(lat, lon, date=date)

    async def point_in_restricted_area(
        lat: float, lon: float, time: Optional[datetime] = None, ctx=None
    ):
        return await geo.check_point_in_restricted_area(lat, lon, time=time)

    async def distance_to_restricted_area(
        lat: float, lon: float, time: Optional[datetime] = None, ctx=None
    ):
        return await geo.distance_to_nearest_restricted_area(lat, lon, time=time)

    async def restrictions_near_route(
        route: List[Tuple[float, float]], time: Optional[datetime] = None, ctx=None
    ):
        return await geo.restrictions_near_route([(lat, lon) for lat, lon in route], time=time)

    registry.register(ToolDefinition(
        name="geospatial.pfz_contains",
        fn=pfz_contains,
        title="Check point in PFZ",
        description="Test whether a point lies inside any PFZ advisory zone for the date.",
        group="geospatial",
        safety=READ_ONLY,
        input_model=PfzContainsInput,
    ))
    registry.register(ToolDefinition(
        name="geospatial.point_in_restricted_area",
        fn=point_in_restricted_area,
        title="Check point in restricted area",
        description="Test whether a point lies inside any restricted area, active at the reference time.",
        group="geospatial",
        safety=READ_ONLY,
        input_model=PointInRestrictedInput,
    ))
    registry.register(ToolDefinition(
        name="geospatial.distance_to_restricted_area",
        fn=distance_to_restricted_area,
        title="Distance to nearest restricted area",
        description="Approximate distance (metres) from a point to the nearest restricted area.",
        group="geospatial",
        safety=READ_ONLY,
        input_model=DistanceToRestrictedInput,
    ))
    registry.register(ToolDefinition(
        name="geospatial.restrictions_near_route",
        fn=restrictions_near_route,
        title="Restrictions along a route",
        description="List restricted areas intersected by a route ([[lat,lon], ...]).",
        group="geospatial",
        safety=SPATIAL_ANALYSIS,
        input_model=RestrictionsNearRouteInput,
    ))