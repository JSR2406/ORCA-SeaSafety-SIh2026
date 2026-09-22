# ArgoService - the read/write facade for ARGO float profile data.
#
# Wires ArgoClient (fetch), dataset_to_profiles (convert) and ArgoRepository
# (persist) into a single service used by MCP tools and routers.  Keeps the
# argopy/xarray dependency isolated: only fetch methods touch it.
import structlog
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.argo_client import ArgoClient, get_argo_client
from app.data.argo_persist import dataset_to_profiles
from app.db.argo_repository import ArgoRepository
from app.db.models import ArgoObservation, ArgoProfile

logger = structlog.get_logger(__name__)

DEFAULT_BBOX = {"min_lon": 60.0, "max_lon": 100.0, "min_lat": 5.0, "max_lat": 25.0}


class ArgoService:
    def __init__(self, session_factory, client: Optional[ArgoClient] = None):
        self.session_factory = session_factory
        self.client = client or get_argo_client()

    # ---------------------------------------------------------------- read
    async def search_profiles(
        self,
        *,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        quality_filter: str = "all",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Query persisted ARGO profiles (region/time) with observations."""
        qc = {
            "recommended": "temperature_qc IN (1, 2) AND salinity_qc IN (1, 2)",
            "good_only": "temperature_qc = 1 AND salinity_qc = 1",
            "all": "1=1",
        }
        quality_clause = qc.get(quality_filter, "1=1")

        async with self.session_factory() as session:
            stmt = select(ArgoProfile).join(
                ArgoObservation, ArgoProfile.id == ArgoObservation.profile_id
            )
            if min_lat is not None and max_lat is not None:
                stmt = stmt.where(
                    ArgoProfile.latitude >= min_lat, ArgoProfile.latitude <= max_lat)
            if min_lon is not None and max_lon is not None:
                stmt = stmt.where(
                    ArgoProfile.longitude >= min_lon, ArgoProfile.longitude <= max_lon)
            if start is not None:
                stmt = stmt.where(ArgoProfile.profile_time >= start)
            if end is not None:
                stmt = stmt.where(ArgoProfile.profile_time <= end)
            stmt = stmt.where(text(quality_clause)).distinct(ArgoProfile.id).limit(limit)

            result = await session.execute(stmt)
            profiles = result.scalars().all()

            profile_ids = [p.id for p in profiles]
            observations: List[ArgoObservation] = []
            if profile_ids:
                obs_result = await session.execute(
                    select(ArgoObservation).where(
                        ArgoObservation.profile_id.in_(profile_ids)
                    ).where(text(quality_clause))
                )
                observations = obs_result.scalars().all()

            obs_by_profile: Dict[int, List[Dict[str, Any]]] = {}
            for obs in observations:
                obs_by_profile.setdefault(obs.profile_id, []).append({
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

            return {
                "profiles": [{
                    "profile_id": p.id,
                    "platform_number": p.platform_number,
                    "cycle_number": p.cycle_number,
                    "profile_time": p.profile_time.isoformat() if p.profile_time else None,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "observations": obs_by_profile.get(p.id, []),
                } for p in profiles],
                "metadata": {
                    "profile_count": len(profiles),
                    "observation_count": len(observations),
                    "float_ids": list({p.platform_number for p in profiles}),
                },
            }

    async def stats(self) -> Dict[str, Any]:
        async with self.session_factory() as session:
            p = await session.execute(select(func.count(ArgoProfile.id)))
            o = await session.execute(select(func.count(ArgoObservation.id)))
            return {"profile_count": p.scalar() or 0, "observation_count": o.scalar() or 0}

    # --------------------------------------------------------------- fetch+persist
    async def ingest_region(
        self,
        *,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_profiles: Optional[int] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Fetch ARGO profiles for a region and persist them idempotently."""
        min_lon = min_lon if min_lon is not None else DEFAULT_BBOX["min_lon"]
        max_lon = max_lon if max_lon is not None else DEFAULT_BBOX["max_lon"]
        min_lat = min_lat if min_lat is not None else DEFAULT_BBOX["min_lat"]
        max_lat = max_lat if max_lat is not None else DEFAULT_BBOX["max_lat"]

        try:
            ds = await self.client.fetch_region(
                min_lon, max_lon, min_lat, max_lat,
                start_date=start_date, end_date=end_date, use_cache=use_cache,
            )
        except Exception as exc:
            return {"ok": False, "fetched": 0, "inserted": 0,
                    "error": f"ARGO fetch failed: {exc}"}

        if ds is None:
            return {"ok": False, "fetched": 0, "inserted": 0,
                    "error": "ARGO returned no data for the requested region."}

        payloads = dataset_to_profiles(ds, source="argo", max_profiles=max_profiles)
        inserted = 0
        async with self.session_factory() as session:
            repo = ArgoRepository(session)
            for payload in payloads:
                if payload.get("profile_time") is None:
                    continue
                created, _ = await repo.insert_profile(**payload)
                if created:
                    inserted += 1
        return {"ok": True, "fetched": len(payloads), "inserted": inserted,
                "region": {"min_lon": min_lon, "max_lon": max_lon,
                           "min_lat": min_lat, "max_lat": max_lat}}

    async def ingest_float(
        self, platform_number: int, cycle_numbers: Optional[List[int]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Fetch profiles for one ARGO float and persist them idempotently."""
        try:
            ds = await self.client.fetch_float(
                platform_number, cycle_numbers=cycle_numbers, use_cache=use_cache)
        except Exception as exc:
            return {"ok": False, "fetched": 0, "inserted": 0,
                    "error": f"ARGO float fetch failed: {exc}"}
        if ds is None:
            return {"ok": False, "fetched": 0, "inserted": 0,
                    "error": f"No ARGO data for float {platform_number}."}
        payloads = dataset_to_profiles(ds, source="argo")
        inserted = 0
        async with self.session_factory() as session:
            repo = ArgoRepository(session)
            for payload in payloads:
                if payload.get("profile_time") is None:
                    continue
                created, _ = await repo.insert_profile(**payload)
                if created:
                    inserted += 1
        return {"ok": True, "fetched": len(payloads), "inserted": inserted,
                "platform_number": platform_number}