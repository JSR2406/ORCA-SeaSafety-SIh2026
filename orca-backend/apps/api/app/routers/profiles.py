# Profiles Router
# Direct profile search endpoint

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID

from app.db.client import get_db_session
from app.db.models import ArgoProfile, ArgoObservation
from app.schemas.query import QualityFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.post("/search")
async def search_profiles(
    region: dict,
    time_range: dict = None,
    depth_range_m: dict = None,
    variables: list = None,
    quality_filter: str = "recommended",
    limit: int = 200,
    session: AsyncSession = Depends(get_db_session),
):
    """Search ARGO profiles by region, time, depth."""
    # Build query
    stmt = select(ArgoProfile).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)
    
    # Region filter
    if region.get("type") == "bbox":
        stmt = stmt.where(
            and_(
                ArgoProfile.latitude >= region["min_lat"],
                ArgoProfile.latitude <= region["max_lat"],
                ArgoProfile.longitude >= region["min_lon"],
                ArgoProfile.longitude <= region["max_lon"],
            )
        )
    elif region.get("type") == "radius":
        point = ST_SetSRID(ST_MakePoint(region["lon"], region["lat"]), 4326)
        stmt = stmt.where(ST_DWithin(ArgoProfile.geom, point, region["radius_km"] * 1000))
    elif region.get("type") == "named_region":
        # Use predefined bboxes
        named_regions = {
            "arabian_sea": {"min_lat": 8.0, "max_lat": 25.0, "min_lon": 60.0, "max_lon": 78.0},
            "bay_of_bengal": {"min_lat": 5.0, "max_lat": 22.0, "min_lon": 80.0, "max_lon": 100.0},
            "kerala_coast": {"min_lat": 8.0, "max_lat": 13.0, "min_lon": 74.0, "max_lon": 77.0},
        }
        bbox = named_regions.get(region["name"])
        if bbox:
            stmt = stmt.where(
                and_(
                    ArgoProfile.latitude >= bbox["min_lat"],
                    ArgoProfile.latitude <= bbox["max_lat"],
                    ArgoProfile.longitude >= bbox["min_lon"],
                    ArgoProfile.longitude <= bbox["max_lon"],
                )
            )
    
    # Time filter
    if time_range:
        stmt = stmt.where(
            and_(
                ArgoProfile.profile_time >= time_range["start"],
                ArgoProfile.profile_time <= time_range["end"],
            )
        )
    
    # Depth filter
    if depth_range_m:
        stmt = stmt.where(
            and_(
                ArgoObservation.depth_m >= depth_range_m["min"],
                ArgoObservation.depth_m <= depth_range_m["max"],
            )
        )
    
    # QC filter
    qc_conditions = {
        "recommended": "temperature_qc IN (1, 2) AND salinity_qc IN (1, 2)",
        "good_only": "temperature_qc = 1 AND salinity_qc = 1",
        "all": "1=1",
    }
    stmt = stmt.where(text(qc_conditions.get(quality_filter, "1=1")))
    
    # Distinct profiles
    stmt = stmt.distinct(ArgoProfile.id).limit(limit)
    
    result = await session.execute(stmt)
    profiles = result.scalars().all()
    
    # Get observations
    profile_ids = [p.id for p in profiles]
    if not profile_ids:
        return {"profiles": [], "metadata": {"float_count": 0, "profile_count": 0, "observation_count": 0}}
    
    obs_stmt = select(ArgoObservation).where(ArgoObservation.profile_id.in_(profile_ids))
    obs_stmt = obs_stmt.where(text(qc_conditions.get(quality_filter, "1=1")))
    obs_result = await session.execute(obs_stmt)
    observations = obs_result.scalars().all()
    
    # Format response
    obs_by_profile = {}
    for obs in observations:
        if obs.profile_id not in obs_by_profile:
            obs_by_profile[obs.profile_id] = []
        obs_by_profile[obs.profile_id].append({
            "depth_m": obs.depth_m,
            "pressure_dbar": obs.pressure_dbar,
            "temperature_c": obs.temperature_c,
            "salinity_psu": obs.salinity_psu,
            "oxygen_umol_kg": obs.oxygen_umol_kg,
            "chlorophyll": obs.chlorophyll,
            "temperature_qc": obs.temperature_qc,
            "salinity_qc": obs.salinity_qc,
            "oxygen_qc": obs.oxygen_qc,
        })
    
    profile_data = []
    for p in profiles:
        profile_data.append({
            "profile_id": p.id,
            "platform_number": p.platform_number,
            "cycle_number": p.cycle_number,
            "profile_time": p.profile_time.isoformat() if p.profile_time else None,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "observations": obs_by_profile.get(p.id, []),
        })
    
    float_ids = list(set(p.platform_number for p in profiles))
    obs_count = len(observations)
    times = [p.profile_time for p in profiles if p.profile_time]
    depths = [o.depth_m for o in observations if o.depth_m is not None]
    
    return {
        "profiles": profile_data,
        "metadata": {
            "float_count": len(float_ids),
            "profile_count": len(profiles),
            "observation_count": obs_count,
            "float_ids": float_ids,
            "time_range": {
                "start": min(times).isoformat() if times else None,
                "end": max(times).isoformat() if times else None,
            } if times else None,
            "depth_range_m": {
                "min": min(depths) if depths else None,
                "max": max(depths) if depths else None,
            } if depths else None,
            "region": region,
        }
    }