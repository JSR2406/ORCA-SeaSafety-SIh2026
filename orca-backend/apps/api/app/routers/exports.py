# Exports Router
# CSV export endpoint

import logging
import io
import csv
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID

from app.db.client import get_db_session
from app.db.models import ArgoProfile, ArgoObservation, QueryRun, EvidenceRecord
from app.schemas.query import QualityFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.post("/csv")
async def export_csv(
    query_run_id: str,
    format: str = "profiles",
    session: AsyncSession = Depends(get_db_session),
):
    """Export query results as CSV."""
    # Get query run
    stmt = select(QueryRun).where(QueryRun.id == query_run_id)
    result = await session.execute(stmt)
    query_run = result.scalar_one_or_none()
    
    if not query_run:
        raise HTTPException(status_code=404, detail="Query run not found")
    
    # Get evidence for this query run
    ev_stmt = select(EvidenceRecord).where(EvidenceRecord.query_run_id == query_run_id)
    ev_result = await session.execute(ev_stmt)
    evidence = ev_result.scalar_one_or_none()
    
    if not evidence:
        raise HTTPException(status_code=404, detail="No evidence found for query run")
    
    # Reconstruct query from stored structured_query
    query = query_run.structured_query
    
    # Fetch data based on format
    if format == "profiles":
        return await _export_profiles_csv(query, session, query_run_id)
    elif format == "observations":
        return await _export_observations_csv(query, session, query_run_id)
    elif format == "summary":
        return await _export_summary_csv(query, evidence, session, query_run_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")


async def _export_profiles_csv(query: dict, session: AsyncSession, query_run_id: str):
    """Export profile-level data."""
    # Build query same as search
    stmt = select(ArgoProfile).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)
    
    # Apply region
    region = query.get("region", {})
    if region.get("type") == "bbox":
        stmt = stmt.where(
            and_(
                ArgoProfile.latitude >= region["min_lat"],
                ArgoProfile.latitude <= region["max_lat"],
                ArgoProfile.longitude >= region["min_lon"],
                ArgoProfile.longitude <= region["max_lon"],
            )
        )
    elif region.get("type") == "named_region":
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
    
    # Time range
    time_range = query.get("time_range")
    if time_range:
        stmt = stmt.where(
            and_(
                ArgoProfile.profile_time >= time_range["start"],
                ArgoProfile.profile_time <= time_range["end"],
            )
        )
    
    # QC filter
    qc_conditions = {
        "recommended": "temperature_qc IN (1, 2) AND salinity_qc IN (1, 2)",
        "good_only": "temperature_qc = 1 AND salinity_qc = 1",
        "all": "1=1",
    }
    qc = query.get("quality_filter", "recommended")
    stmt = stmt.where(text(qc_conditions.get(qc, "1=1")))
    
    stmt = stmt.distinct(ArgoProfile.id).limit(5000)
    result = await session.execute(stmt)
    profiles = result.scalars().all()
    
    # Get observations
    profile_ids = [p.id for p in profiles]
    if not profile_ids:
        return Response(content="No data", media_type="text/csv")
    
    obs_stmt = select(ArgoObservation).where(ArgoObservation.profile_id.in_(profile_ids))
    obs_stmt = obs_stmt.where(text(qc_conditions.get(qc, "1=1")))
    obs_result = await session.execute(obs_stmt)
    observations = obs_result.scalars().all()
    
    # Group observations by profile
    obs_by_profile = {}
    for obs in observations:
        if obs.profile_id not in obs_by_profile:
            obs_by_profile[obs.profile_id] = []
        obs_by_profile[obs.profile_id].append(obs)
    
    # Write CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "profile_id", "platform_number", "cycle_number", "profile_time",
        "latitude", "longitude", "depth_m", "pressure_dbar",
        "temperature_c", "salinity_psu", "oxygen_umol_kg", "chlorophyll",
        "temperature_qc", "salinity_qc", "oxygen_qc",
    ])
    
    for p in profiles:
        for obs in obs_by_profile.get(p.id, []):
            writer.writerow([
                p.id, p.platform_number, p.cycle_number,
                p.profile_time.isoformat() if p.profile_time else "",
                p.latitude, p.longitude,
                obs.depth_m or "", obs.pressure_dbar or "",
                obs.temperature_c or "", obs.salinity_psu or "",
                obs.oxygen_umol_kg or "", obs.chlorophyll or "",
                obs.temperature_qc or "", obs.salinity_qc or "",
                obs.oxygen_qc or "",
            ])
    
    csv_content = output.getvalue()
    filename = f"floatchat_profiles_{query_run_id[:8]}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


async def _export_observations_csv(query: dict, session: AsyncSession, query_run_id: str):
    """Export observation-level data (same as profiles but different grouping)."""
    return await _export_profiles_csv(query, session, query_run_id)


async def _export_summary_csv(query: dict, evidence, session: AsyncSession, query_run_id: str):
    """Export summary statistics."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Field", "Value"])
    writer.writerow(["Query Run ID", query_run_id])
    writer.writerow(["User Query", query.get("user_input", "")])
    writer.writerow(["Intent", query.get("intent", "")])
    writer.writerow(["Float Count", evidence.float_ids.__len__() if hasattr(evidence, 'float_ids') else "N/A"])
    writer.writerow(["Profile Count", getattr(evidence, 'profile_count', "N/A")])
    writer.writerow(["Observation Count", getattr(evidence, 'observation_count', "N/A")])
    writer.writerow(["Region", str(query.get("region", {}))])
    writer.writerow(["Time Range", f"{query.get('time_range', {}).get('start', '')} to {query.get('time_range', {}).get('end', '')}"])
    writer.writerow(["Depth Range (m)", f"{query.get('depth_range_m', {}).get('min', '')} - {query.get('depth_range_m', {}).get('max', '')}"])
    writer.writerow(["Quality Filter", query.get("quality_filter", "")])
    writer.writerow(["Confidence", getattr(evidence.confidence, 'label', "N/A") if hasattr(evidence, 'confidence') else "N/A"])
    writer.writerow(["Data Freshness (days)", getattr(evidence.data_freshness, 'days_old', "N/A") if hasattr(evidence, 'data_freshness') else "N/A"])
    
    csv_content = output.getvalue()
    filename = f"floatchat_summary_{query_run_id[:8]}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )