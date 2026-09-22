# Marine data API (read-only). All responses use the uniform MarineDataResult
# envelope with status / sources / timestamps / freshness / provenance.
# Sources that are not configured return NOT_CONFIGURED - never mock data.
from datetime import datetime
from typing import Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.datasources.registry import build_registry
from app.db.client import get_session
from app.services.marine_data_service import MarineDataService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/marine", tags=["marine"])


def _service() -> MarineDataService:
    return MarineDataService(settings, build_registry(settings), get_session)


def _as_http(resp, *, not_found: bool = False):
    """Map a MarineDataResult to HTTP response; raise on invalid input."""
    if isinstance(resp, ValueError):
        raise HTTPException(status_code=422, detail=str(resp))
    return resp


@router.get("/ocean")
async def ocean_conditions(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    time: Optional[datetime] = Query(None, description="Observation time (default: latest)"),
    radius_km: float = Query(25.0, gt=0, le=500, description="Search radius"),
    limit: int = Query(5, ge=1, le=50),
):
    try:
        return _as_http(await _service().get_ocean_conditions(lat, lon, time=time, radius_km=radius_km, limit=limit))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/weather-forecast")
async def weather_forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    valid_time: Optional[datetime] = Query(None, description="Time the forecast must cover"),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(5, ge=1, le=50),
):
    try:
        return await _service().get_weather_forecast(lat, lon, valid_time=valid_time, radius_km=radius_km, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/weather-observation")
async def weather_observation(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    time: Optional[datetime] = Query(None),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(5, ge=1, le=50),
):
    try:
        return await _service().get_weather_observation(lat, lon, time=time, radius_km=radius_km, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/tides")
async def tides(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        return await _service().get_tides(lat, lon, start=start, end=end, radius_km=radius_km, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/pfz")
async def pfz(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    date: Optional[datetime] = Query(None),
    radius_km: float = Query(50.0, gt=0, le=500),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        return await _service().get_pfz(lat=lat, lon=lon, date=date, radius_km=radius_km, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/warnings")
async def marine_warnings(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return await _service().get_marine_warnings(lat=lat, lon=lon, start=start, end=end, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/restrictions")
async def restrictions(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    time: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return await _service().get_restricted_areas(lat=lat, lon=lon, time=time, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/check-restriction")
async def check_restriction(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    time: Optional[datetime] = Query(None),
):
    try:
        return await _service().check_marine_restrictions(lat, lon, time=time)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/source-status")
async def source_status():
    return {"sources": await _service().sources_status()}