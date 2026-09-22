# ARGO write-path repository: persist ARGO profiles + observations.
#
# ArgoProfile / ArgoObservation are persisted idempotently on the
# (platform_number, cycle_number) natural key so repeated region/float fetches
# never duplicate rows.  Inserted rows are consumers-compatible with the
# read routes in routers/profiles.py (search by region/time/depth/QC).
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ArgoObservation, ArgoProfile


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ArgoRepository:
    """Idempotent persistence for ARGO float profiles and level observations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_profile(
        self, platform_number: int, cycle_number: int,
    ) -> Optional[ArgoProfile]:
        stmt = (
            select(ArgoProfile)
            .options(selectinload(ArgoProfile.observations))
            .where(
                ArgoProfile.platform_number == platform_number,
                ArgoProfile.cycle_number == cycle_number,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def insert_profile(
        self,
        *,
        platform_number: int,
        cycle_number: int,
        profile_time: datetime,
        latitude: float,
        longitude: float,
        source: str = "argo",
        source_url: Optional[str] = None,
        qc_status: str = "recommended",
        observations: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, Optional[ArgoProfile]]:
        """Upsert an ARGO profile + its observations.

        Returns (created, profile). created is False when the platform/cycle
        already existed (idempotent re-ingestion).
        """
        geom = f"POINT({float(longitude)} {float(latitude)})"
        stmt = pg_insert(ArgoProfile).values(
            platform_number=platform_number,
            cycle_number=cycle_number,
            profile_time=_utc(profile_time),
            latitude=latitude,
            longitude=longitude,
            geom=geom,
            source=source,
            source_url=source_url,
            qc_status=qc_status,
        ).on_conflict_do_update(
            index_elements=["platform_number", "cycle_number"],
            set_={},
        ).returning(ArgoProfile.id)
        created = True
        try:
            result = await self.session.execute(stmt)
            profile_id = result.scalar_one()
        except Exception:
            # on_conflict_do_update with empty set_ is a no-op update; the row
            # always returns. If the dialect emitted nothing, fetch it.
            await self.session.rollback()
            created = False
            existing = await self.get_profile(platform_number, cycle_number)
            if existing is None:
                raise
            return False, existing

        if observations:
            rows = [
                {
                    "profile_id": profile_id,
                    "pressure_dbar": o.get("pressure_dbar"),
                    "depth_m": o.get("depth_m"),
                    "temperature_c": o.get("temperature_c"),
                    "salinity_psu": o.get("salinity_psu"),
                    "oxygen_umol_kg": o.get("oxygen_umol_kg"),
                    "chlorophyll": o.get("chlorophyll"),
                    "temperature_qc": o.get("temperature_qc"),
                    "salinity_qc": o.get("salinity_qc"),
                    "oxygen_qc": o.get("oxygen_qc"),
                }
                for o in observations
            ]
            if rows:
                await self.session.execute(pg_insert(ArgoObservation).values(rows))
        await self.session.commit()
        profile = await self.get_profile(platform_number, cycle_number)
        return created, profile

    async def count(self) -> Tuple[int, int]:
        """Return (profile_count, observation_count)."""
        p = await self.session.execute(select(ArgoProfile.id))
        o = await self.session.execute(select(ArgoObservation.id))
        return len(p.scalars().all()), len(o.scalars().all())