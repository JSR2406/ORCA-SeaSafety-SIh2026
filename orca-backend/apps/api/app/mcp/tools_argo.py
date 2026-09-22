# Tool group: argo - ARGO float profile ingestion + search across the
# Arabian Sea / Bay of Bengal using the ArgoService facade.
#
# Read tools are READ_ONLY.  Ingest tools persist by fetching from the ARGO
# GDAC via ArgoClient and idempotently storing profiles; they need the argopy
# cache/network path and are intended for operators/orthographers, not for
# unconstrained agent calls.
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.mcp.registry import DECISION_SUPPORT, READ_ONLY, ToolDefinition, ToolRegistry
from app.services.argo_service import ArgoService

_DEFAULT_BBOX_DESC = "Region bounds (default Arabian Sea + Bay of Bengal)"


class ArgoProfileSearchInput(BaseModel):
    min_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="West longitude")
    max_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="East longitude")
    min_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="South latitude")
    max_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="North latitude")
    start: Optional[datetime] = Field(None, description="Earliest profile time (ISO-8601)")
    end: Optional[datetime] = Field(None, description="Latest profile time (ISO-8601)")
    quality_filter: str = Field("all", description="recommended | good_only | all")
    limit: int = Field(50, ge=1, le=500)


class ArgoIngestRegionInput(BaseModel):
    min_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description=_DEFAULT_BBOX_DESC)
    max_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description=_DEFAULT_BBOX_DESC)
    min_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description=_DEFAULT_BBOX_DESC)
    max_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description=_DEFAULT_BBOX_DESC)
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    max_profiles: Optional[int] = Field(None, ge=1, le=1000)


class ArgoIngestFloatInput(BaseModel):
    platform_number: int = Field(..., description="ARGO float WMO platform number")
    cycle_numbers: Optional[List[int]] = Field(None, description="Optional specific cycles")


def register(registry: ToolRegistry, argo: ArgoService) -> None:
    async def profile_search(
        min_lon: Optional[float] = None, max_lon: Optional[float] = None,
        min_lat: Optional[float] = None, max_lat: Optional[float] = None,
        start: Optional[datetime] = None, end: Optional[datetime] = None,
        quality_filter: str = "all", limit: int = 50, ctx=None,
    ):
        return await argo.search_profiles(
            min_lon=min_lon, max_lon=max_lon, min_lat=min_lat, max_lat=max_lat,
            start=start, end=end, quality_filter=quality_filter, limit=limit,
        )

    async def stats(ctx=None):
        return await argo.stats()

    async def ingest_region(
        min_lon: Optional[float] = None, max_lon: Optional[float] = None,
        min_lat: Optional[float] = None, max_lat: Optional[float] = None,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
        max_profiles: Optional[int] = None, ctx=None,
    ):
        return await argo.ingest_region(
            min_lon=min_lon, max_lon=max_lon, min_lat=min_lat, max_lat=max_lat,
            start_date=start_date, end_date=end_date, max_profiles=max_profiles,
        )

    async def ingest_float(
        platform_number: int, cycle_numbers: Optional[List[int]] = None, ctx=None,
    ):
        return await argo.ingest_float(platform_number, cycle_numbers=cycle_numbers)

    registry.register(ToolDefinition(
        name="argo.profile_search",
        fn=profile_search,
        title="Search ARGO profiles",
        description="Query persisted ARGO float profiles by region/time/depth-quality.",
        group="argo",
        safety=READ_ONLY,
        input_model=ArgoProfileSearchInput,
    ))
    registry.register(ToolDefinition(
        name="argo.stats",
        fn=stats,
        title="ARGO profile statistics",
        description="Total persisted ARGO profiles and observations.",
        group="argo",
        safety=READ_ONLY,
        input_model=None,
    ))
    registry.register(ToolDefinition(
        name="argo.ingest_region",
        fn=ingest_region,
        title="Ingest ARGO region",
        description="Fetch + idempotently store ARGO profiles for a region (writes DB).",
        group="argo",
        safety=DECISION_SUPPORT,
        input_model=ArgoIngestRegionInput,
    ))
    registry.register(ToolDefinition(
        name="argo.ingest_float",
        fn=ingest_float,
        title="Ingest ARGO float",
        description="Fetch + idempotently store profiles for one ARGO float (writes DB).",
        group="argo",
        safety=DECISION_SUPPORT,
        input_model=ArgoIngestFloatInput,
    ))