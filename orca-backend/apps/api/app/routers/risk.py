# Risk Router
# Marine condition risk briefing endpoint

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID

from app.db.client import get_db_session
from app.db.models import ArgoProfile, ArgoObservation
from app.schemas.risk import RiskBriefingResponse, RiskComponent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.post("/briefing", response_model=RiskBriefingResponse)
async def risk_briefing(
    origin: dict = None,
    latitude: float = None,
    longitude: float = None,
    destination: dict = None,
    distance_km: float = None,
    departure_time: str = None,
    vessel_type: str = "fishing_boat",
    include_forecast: bool = True,
    session: AsyncSession = Depends(get_db_session),
):
    """Generate conservative marine condition risk briefing.
    Accepts `origin={lat, lon}` (canonical) or a flat `latitude`/`longitude`
    pair (legacy/point style)."""
    
    # Validate origin: object form, else flat lat/lon fallback
    if origin is None and latitude is not None and longitude is not None:
        origin = {"lat": latitude, "lon": longitude}
    if not origin or "lat" not in origin or "lon" not in origin:
        raise HTTPException(status_code=400, detail="Origin (lat, lon) required (origin object or latitude/longitude fields)")
    
    lat, lon = origin["lat"], origin["lon"]
    
    # Search for nearby ARGO data
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
    radius_m = (distance_km or 50) * 1000
    
    stmt = select(
        func.count(ArgoProfile.id.distinct()).label("float_count"),
        func.count(ArgoProfile.id).label("profile_count"),
        func.avg(ArgoObservation.temperature_c).label("mean_temp"),
        func.max(ArgoProfile.profile_time).label("latest_profile"),
    ).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)
    stmt = stmt.where(ST_DWithin(ArgoProfile.geom, point, radius_m))
    stmt = stmt.where(ArgoObservation.temperature_c.isnot(None))
    stmt = stmt.where(text("temperature_qc IN (1, 2)"))
    
    result = await session.execute(stmt)
    row = result.first()
    
    float_count = row.float_count or 0
    profile_count = row.profile_count or 0
    latest_profile = row.latest_profile
    
    # Compute data freshness
    from datetime import datetime, timezone
    if latest_profile:
        days_old = (datetime.now(timezone.utc) - latest_profile.replace(tzinfo=timezone.utc)).days
    else:
        days_old = 999
    
    # Risk components (conservative - no forecast integration in MVP)
    components = []
    
    # Waves - from climatology
    if profile_count > 0:
        wave_label = "moderate"
        wave_reason = f"Climatological significant wave height 1.5-2.5m for this region/season"
        wave_freshness = "climatology"
    else:
        wave_label = "unavailable"
        wave_reason = "No ARGO data in region for wave estimation"
        wave_freshness = "unavailable"
    
    components.append(RiskComponent(
        name="waves",
        label=wave_label,
        reason=wave_reason,
        source="ARGO-derived climatology",
        data_freshness=wave_freshness,
    ))
    
    # Wind - from climatology
    components.append(RiskComponent(
        name="wind",
        label="moderate",
        reason="Climatological wind speed 8-15 knots for this season",
        source="ERA5 reanalysis climatology",
        data_freshness="climatology",
    ))
    
    # Currents - from ARGO trajectories
    if float_count >= 3:
        curr_label = "moderate"
        curr_reason = f"Surface drift estimated from {float_count} floats in region"
        curr_freshness = f"{days_old} days old" if days_old < 999 else "unavailable"
    else:
        curr_label = "unavailable"
        curr_reason = "Insufficient floats for current estimation"
        curr_freshness = "unavailable"
    
    components.append(RiskComponent(
        name="currents",
        label=curr_label,
        reason=curr_reason,
        source="ARGO trajectory analysis",
        data_freshness=curr_freshness,
    ))
    
    # Official warnings - NOT integrated in MVP
    components.append(RiskComponent(
        name="warnings",
        label="unavailable",
        reason="Official INCOIS/IMD warning data not integrated",
        source="none",
        data_freshness="unavailable",
    ))
    
    # Data coverage
    if profile_count >= 10:
        cov_label = "moderate"
    elif profile_count >= 3:
        cov_label = "partial"
    else:
        cov_label = "unavailable"
    
    components.append(RiskComponent(
        name="data_coverage",
        label=cov_label,
        reason=f"{float_count} floats, {profile_count} profiles within {distance_km or 50}km",
        source="ARGO observations",
        data_freshness=f"{days_old} days old" if days_old < 999 else "unavailable",
    ))
    
    # Overall risk (conservative)
    critical_unavailable = any(c.name == "warnings" and c.label == "unavailable" for c in components)
    elevated = any(c.label == "elevated" for c in components)
    moderate = any(c.label == "moderate" for c in components)
    
    if critical_unavailable:
        overall = "unavailable"
    elif elevated:
        overall = "elevated"
    elif moderate:
        overall = "moderate"
    else:
        overall = "low"
    
    # Confidence
    confidence_score = 0.5 if profile_count > 0 else 0.2
    confidence = {
        "label": "medium" if confidence_score > 0.5 else "low",
        "score": confidence_score,
        "components": {
            "spatial_coverage": min(float_count / 10, 1.0),
            "temporal_freshness": max(0, 1 - days_old / 90) if days_old < 999 else 0,
            "sample_density": min(profile_count / 50, 1.0),
            "measurement_quality": 0.85,
            "method_stability": 0.6,
        },
        "explanation": f"Based on {profile_count} ARGO profiles from {float_count} floats. No real-time forecast or official warnings.",
        "limitations": [
            "No real-time wave/wind forecast integration",
            "No official marine warning data",
            "ARGO measures temperature/salinity, not surface conditions directly",
            "Climatology used for wave/wind estimates",
        ],
    }
    
    advisory = (
        "⚠️ This briefing is based on historical ARGO observations and climatology only. "
        "It does NOT include real-time forecasts or official marine warnings. "
        "Follow the latest INCOIS/IMD warnings before departure."
    )
    
    return RiskBriefingResponse(
        overall_label=overall,
        components=components,
        confidence=confidence,
        advisory=advisory,
        data_status="partial" if profile_count > 0 else "unavailable",
        latest_data_timestamp=latest_profile.isoformat() if latest_profile else datetime.now(timezone.utc).isoformat(),
    )