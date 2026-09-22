# Anomalies Router
# Anomaly detection endpoint

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID

from app.db.client import get_db_session
from app.db.models import ArgoProfile, ArgoObservation
from app.schemas.query import QualityFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/anomalies", tags=["anomalies"])


@router.post("/detect")
async def detect_anomaly(
    variable: str,
    region: dict,
    depth_m: float,
    reference_period: dict,
    analysis_period: dict,
    threshold_std: float = 2.0,
    quality_filter: str = "recommended",
    session: AsyncSession = Depends(get_db_session),
):
    """Detect anomalies by comparing analysis period against reference period."""
    # This is a simplified implementation for MVP
    # In production, would do proper statistical anomaly detection
    
    var_col_map = {
        "temperature": ArgoObservation.temperature_c,
        "salinity": ArgoObservation.salinity_psu,
        "oxygen": ArgoObservation.oxygen_umol_kg,
        "chlorophyll": ArgoObservation.chlorophyll,
    }
    var_col = var_col_map.get(variable)
    if not var_col:
        raise HTTPException(status_code=400, detail=f"Unsupported variable: {variable}")
    
    qc_conditions = {
        "recommended": "temperature_qc IN (1, 2) AND salinity_qc IN (1, 2)",
        "good_only": "temperature_qc = 1 AND salinity_qc = 1",
        "all": "1=1",
    }
    qc_cond = qc_conditions.get(quality_filter, "1=1")
    
    # Build region filter
    def apply_region(stmt, region_dict):
        if region_dict.get("type") == "named_region":
            named_regions = {
                "arabian_sea": {"min_lat": 8.0, "max_lat": 25.0, "min_lon": 60.0, "max_lon": 78.0},
                "bay_of_bengal": {"min_lat": 5.0, "max_lat": 22.0, "min_lon": 80.0, "max_lon": 100.0},
                "kerala_coast": {"min_lat": 8.0, "max_lat": 13.0, "min_lon": 74.0, "max_lon": 77.0},
            }
            bbox = named_regions.get(region_dict["name"])
            if bbox:
                stmt = stmt.where(
                    and_(
                        ArgoProfile.latitude >= bbox["min_lat"],
                        ArgoProfile.latitude <= bbox["max_lat"],
                        ArgoProfile.longitude >= bbox["min_lon"],
                        ArgoProfile.longitude <= bbox["max_lon"],
                    )
                )
        elif region_dict.get("type") == "bbox":
            stmt = stmt.where(
                and_(
                    ArgoProfile.latitude >= region_dict["min_lat"],
                    ArgoProfile.latitude <= region_dict["max_lat"],
                    ArgoProfile.longitude >= region_dict["min_lon"],
                    ArgoProfile.longitude <= region_dict["max_lon"],
                )
            )
        return stmt
    
    # Reference period query
    ref_stmt = select(
        func.count(var_col).label("count"),
        func.avg(var_col).label("mean"),
        func.stddev(var_col).label("std"),
        func.min(var_col).label("min"),
        func.max(var_col).label("max"),
    ).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)
    ref_stmt = apply_region(ref_stmt, region)
    ref_stmt = ref_stmt.where(
        and_(
            ArgoProfile.profile_time >= reference_period["start"],
            ArgoProfile.profile_time <= reference_period["end"],
            ArgoObservation.depth_m >= depth_m - 5,
            ArgoObservation.depth_m <= depth_m + 5,
            var_col.isnot(None),
        )
    )
    ref_stmt = ref_stmt.where(text(qc_cond))
    ref_result = await session.execute(ref_stmt)
    ref_row = ref_result.first()
    
    # Analysis period query
    ana_stmt = select(
        func.count(var_col).label("count"),
        func.avg(var_col).label("mean"),
        func.stddev(var_col).label("std"),
        func.min(var_col).label("min"),
        func.max(var_col).label("max"),
    ).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)
    ana_stmt = apply_region(ana_stmt, region)
    ana_stmt = ana_stmt.where(
        and_(
            ArgoProfile.profile_time >= analysis_period["start"],
            ArgoProfile.profile_time <= analysis_period["end"],
            ArgoObservation.depth_m >= depth_m - 5,
            ArgoObservation.depth_m <= depth_m + 5,
            var_col.isnot(None),
        )
    )
    ana_stmt = ana_stmt.where(text(qc_cond))
    ana_result = await session.execute(ana_stmt)
    ana_row = ana_result.first()
    
    # Compute anomaly
    if not ref_row or not ref_row.mean or not ana_row or not ana_row.mean:
        return {
            "anomaly_detected": False,
            "error": "Insufficient data for comparison",
            "variable": variable,
            "depth_m": depth_m,
        }
    
    ref_mean = float(ref_row.mean)
    ref_std = float(ref_row.std) if ref_row.std else 0.5
    ana_mean = float(ana_row.mean)
    difference = ana_mean - ref_mean
    difference_std = difference / ref_std if ref_std > 0 else 0
    threshold_exceeded = abs(difference_std) > threshold_std
    
    return {
        "anomaly_detected": threshold_exceeded,
        "variable": variable,
        "depth_m": depth_m,
        "region": region,
        "reference_baseline": {
            "mean": ref_mean,
            "std": ref_std,
            "count": ref_row.count,
            "min": float(ref_row.min) if ref_row.min else None,
            "max": float(ref_row.max) if ref_row.max else None,
        },
        "analysis_period": {
            "mean": ana_mean,
            "std": float(ana_row.std) if ana_row.std else None,
            "count": ana_row.count,
            "min": float(ana_row.min) if ana_row.min else None,
            "max": float(ana_row.max) if ana_row.max else None,
        },
        "difference": difference,
        "difference_std": difference_std,
        "threshold_exceeded": threshold_exceeded,
        "threshold_std": threshold_std,
        "affected_locations": [],  # Would need spatial aggregation
        "confidence": {"label": "medium", "score": 0.6},
        "limitations": ["Simplified anomaly detection", "No spatial clustering", "Assumes normal distribution"],
    }