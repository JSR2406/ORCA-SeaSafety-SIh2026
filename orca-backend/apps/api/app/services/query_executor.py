# Query Executor
# Deterministic services for executing structured queries against ARGO data

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from app.db.models import ArgoProfile, ArgoObservation, DatasetSnapshot
from app.schemas.query import (
    StructuredQuery,
    Intent,
    Region,
    BBoxRegion,
    RadiusRegion,
    NamedRegion,
    RouteRegion,
    TimeRange,
    Variable,
    QualityFilter,
)
from app.config import settings

logger = logging.getLogger(__name__)


class QueryExecutor:
    """Executes structured queries deterministically against the database."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- QC Filter Helpers ---

    def _get_qc_condition(self, quality_filter: QualityFilter) -> str:
        """Get SQL condition for QC filtering."""
        if quality_filter == QualityFilter.GOOD_ONLY:
            return "temperature_qc = 1 AND salinity_qc = 1"
        elif quality_filter == QualityFilter.RECOMMENDED:
            return "temperature_qc IN (1, 2) AND salinity_qc IN (1, 2)"
        return "1=1"  # all

    def _apply_region_filter(self, query, region: Region):
        """Apply spatial region filter to query."""
        if isinstance(region, BBoxRegion):
            query = query.where(
                and_(
                    ArgoProfile.latitude >= region.min_lat,
                    ArgoProfile.latitude <= region.max_lat,
                    ArgoProfile.longitude >= region.min_lon,
                    ArgoProfile.longitude <= region.max_lon,
                )
            )
        elif isinstance(region, RadiusRegion):
            # Use PostGIS ST_DWithin for radius search
            point = ST_SetSRID(ST_MakePoint(region.lon, region.lat), 4326)
            query = query.where(ST_DWithin(ArgoProfile.geom, point, region.radius_km * 1000))
        elif isinstance(region, NamedRegion):
            bbox = self.NAMED_REGIONS.get(region.name)
            if bbox:
                query = self._apply_region_filter(query, bbox)
        # Route and Polygon not implemented in MVP
        return query

    def _apply_time_filter(self, query, time_range: Optional[TimeRange]):
        if time_range:
            query = query.where(
                and_(
                    ArgoProfile.profile_time >= time_range.start,
                    ArgoProfile.profile_time <= time_range.end,
                )
            )
        return query

    def _apply_depth_filter(self, query, depth_range: Optional[Dict[str, float]]):
        if depth_range:
            query = query.where(
                and_(
                    ArgoObservation.depth_m >= depth_range["min"],
                    ArgoObservation.depth_m <= depth_range["max"],
                )
            )
        return query

    # --- Tool Implementations ---

    async def search_profiles(self, query: StructuredQuery) -> Dict[str, Any]:
        """Search for profiles matching criteria."""
        # Build base query
        stmt = select(ArgoProfile).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)

        # Apply filters
        if query.region:
            stmt = self._apply_region_filter(stmt, query.region)
        if query.time_range:
            stmt = self._apply_time_filter(stmt, query.time_range)
        if query.depth_range_m:
            stmt = self._apply_depth_filter(stmt, query.depth_range_m.model_dump())

        # QC filter on observations
        qc_cond = self._get_qc_condition(query.quality_filter)
        stmt = stmt.where(text(qc_cond))

        # Distinct profiles
        stmt = stmt.distinct(ArgoProfile.id).limit(query.limit)

        result = await self.session.execute(stmt)
        profiles = result.scalars().all()

        # Get observations for these profiles
        profile_ids = [p.id for p in profiles]
        if not profile_ids:
            return self._empty_result(query)

        obs_stmt = select(ArgoObservation).where(ArgoObservation.profile_id.in_(profile_ids))
        qc_cond = self._get_qc_condition(query.quality_filter)
        obs_stmt = obs_stmt.where(text(qc_cond))
        obs_result = await self.session.execute(obs_stmt)
        observations = obs_result.scalars().all()

        return self._format_profile_result(profiles, observations, query)

    async def aggregate_timeseries(self, query: StructuredQuery) -> Dict[str, Any]:
        """Aggregate measurements into time series."""
        variable = query.variables[0] if query.variables else Variable.TEMPERATURE
        var_col = getattr(ArgoObservation, f"{variable.value}_c" if variable == Variable.TEMPERATURE else variable.value)

        stmt = select(
            func.date_trunc('day', ArgoProfile.profile_time).label('date'),
            func.count(var_col).label('count'),
            func.avg(var_col).label('mean'),
            func.min(var_col).label('min'),
            func.max(var_col).label('max'),
            func.stddev(var_col).label('std'),
        ).join(ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id)

        if query.region:
            stmt = self._apply_region_filter(stmt, query.region)
        if query.time_range:
            stmt = self._apply_time_filter(stmt, query.time_range)
        if query.depth_range_m:
            stmt = self._apply_depth_filter(stmt, query.depth_range_m.model_dump())

        qc_cond = self._get_qc_condition(query.quality_filter)
        stmt = stmt.where(text(qc_cond))
        stmt = stmt.where(var_col.isnot(None))
        stmt = stmt.group_by('date').order_by('date')

        result = await self.session.execute(stmt)
        rows = result.all()

        return {
            "type": "timeseries",
            "variable": variable.value,
            "aggregation": query.aggregation.value,
            "data": [
                {
                    "date": row.date.isoformat() if row.date else None,
                    "count": row.count,
                    "mean": float(row.mean) if row.mean else None,
                    "min": float(row.min) if row.min else None,
                    "max": float(row.max) if row.max else None,
                    "std": float(row.std) if row.std else None,
                }
                for row in rows
            ],
        }

    async def depth_profile_summary(self, query: StructuredQuery) -> Dict[str, Any]:
        """Get depth-binned statistics."""
        variable = query.variables[0] if query.variables else Variable.TEMPERATURE
        var_col = getattr(ArgoObservation, f"{variable.value}_c" if variable == Variable.TEMPERATURE else variable.value)

        # Define depth bins (0-10, 10-20, ..., 1990-2000)
        bin_size = 10
        max_depth = query.depth_range_m.max if query.depth_range_m else 2000
        bins = list(range(0, int(max_depth) + bin_size, bin_size))

        stmt = select(
            func.floor(ArgoObservation.depth_m / bin_size).label('depth_bin'),
            func.count(var_col).label('count'),
            func.avg(var_col).label('mean'),
            func.min(var_col).label('min'),
            func.max(var_col).label('max'),
            func.stddev(var_col).label('std'),
        ).join(ArgoProfile, ArgoProfile.id == ArgoObservation.profile_id)

        if query.region:
            stmt = self._apply_region_filter(stmt, query.region)
        if query.time_range:
            stmt = self._apply_time_filter(stmt, query.time_range)
        if query.depth_range_m:
            stmt = self._apply_depth_filter(stmt, query.depth_range_m.model_dump())

        qc_cond = self._get_qc_condition(query.quality_filter)
        stmt = stmt.where(text(qc_cond))
        stmt = stmt.where(var_col.isnot(None))
        stmt = stmt.group_by('depth_bin').order_by('depth_bin')

        result = await self.session.execute(stmt)
        rows = result.all()

        return {
            "type": "depth_profile",
            "variable": variable.value,
            "bin_size_m": bin_size,
            "data": [
                {
                    "depth_min": float(row.depth_bin) * bin_size,
                    "depth_max": float(row.depth_bin) * bin_size + bin_size,
                    "count": row.count,
                    "mean": float(row.mean) if row.mean else None,
                    "min": float(row.min) if row.min else None,
                    "max": float(row.max) if row.max else None,
                    "std": float(row.std) if row.std else None,
                }
                for row in rows
            ],
        }

    async def compare_baseline(self, query: StructuredQuery) -> Dict[str, Any]:
        """Compare analysis period against baseline period."""
        return {"error": "compare_baseline not yet implemented"}

    async def detect_anomaly(self, query: StructuredQuery) -> Dict[str, Any]:
        """Detect anomalies against baseline."""
        return {"error": "detect_anomaly not yet implemented"}

    async def project_scenario(self, query: StructuredQuery) -> Dict[str, Any]:
        """Project scenario."""
        return {"error": "project_scenario not yet implemented"}

    async def marine_condition_briefing(self, query: StructuredQuery) -> Dict[str, Any]:
        """Generate marine condition briefing."""
        return {"error": "marine_condition_briefing not yet implemented"}

    # --- Result Formatting ---

    def _empty_result(self, query: StructuredQuery) -> Dict[str, Any]:
        return {
            "profiles": [],
            "metadata": {
                "float_count": 0,
                "profile_count": 0,
                "observation_count": 0,
                "time_range": None,
                "depth_range_m": query.depth_range_m.model_dump() if query.depth_range_m else None,
                "region": query.region.model_dump() if query.region else None,
            }
        }

    def _format_profile_result(
        self,
        profiles: List[ArgoProfile],
        observations: List[ArgoObservation],
        query: StructuredQuery,
    ) -> Dict[str, Any]:
        # Group observations by profile
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

        # Compute metadata
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
                "region": query.region.model_dump() if query.region else None,
            }
        }

    # Named regions
    NAMED_REGIONS = {
        "arabian_sea": BBoxRegion(min_lat=8.0, max_lat=25.0, min_lon=60.0, max_lon=78.0),
        "bay_of_bengal": BBoxRegion(min_lat=5.0, max_lat=22.0, min_lon=80.0, max_lon=100.0),
        "kerala_coast": BBoxRegion(min_lat=8.0, max_lat=13.0, min_lon=74.0, max_lon=77.0),
        "indian_ocean": BBoxRegion(min_lat=-30.0, max_lat=30.0, min_lon=30.0, max_lon=120.0),
        "equatorial_indian_ocean": BBoxRegion(min_lat=-10.0, max_lat=10.0, min_lon=40.0, max_lon=110.0),
    }

    async def execute(self, query: StructuredQuery) -> Dict[str, Any]:
        """Route to appropriate tool based on intent."""
        if query.intent == Intent.PROFILE_SEARCH:
            return await self.search_profiles(query)
        elif query.intent == Intent.TIMESERIES_SUMMARY:
            return await self.aggregate_timeseries(query)
        elif query.intent == Intent.DEPTH_PROFILE_SUMMARY:
            return await self.depth_profile_summary(query)
        elif query.intent == Intent.ANOMALY_DETECTION:
            return await self.detect_anomaly(query)
        elif query.intent == Intent.SCENARIO_PROJECTION:
            return await self.project_scenario(query)
        elif query.intent == Intent.MARINE_CONDITION_BRIEFING:
            return await self.marine_condition_briefing(query)
        else:
            return {"error": f"Intent {query.intent} not implemented"}