# Marine data persistence + PostGIS queries.
# PostGIS-dependent queries run on PostgreSQL; callers that need them on other
# backends should bridge via MarineDataService (which reports UNAVAILABLE /
# errors rather than fabricating data).
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import structlog
from geoalchemy2 import functions as geo
from geoalchemy2 import Geography
from sqlalchemy import and_, cast, or_, select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DataSource,
    IngestionRun,
    MarineWarning,
    OceanObservation,
    PFZZone,
    RestrictedArea,
    SourceCapability,
    TidePrediction,
    WeatherForecast,
    WeatherObservation,
)
from app.geo_utils import wkb_to_geojson

logger = structlog.get_logger(__name__)


def point_geom(lon: float, lat: float, srid: int = 4326):
    """Reference SRID-4326 point geometry built from lon/lat (as geography)."""
    return cast(geo.ST_SetSRID(geo.ST_MakePoint(lon, lat), srid), Geography())


def distance_to(lon: float, lat: float, column):
    """Spherical distance in metres between column geometry and a reference point."""
    return geo.ST_DistanceSphere(cast(column, Geography()), point_geom(lon, lat))


def active_window(valid_from_col, valid_until_col, t: datetime):
    """Window predicate: active (unbounded on either side allowed) at time t."""
    return and_(
        or_(valid_from_col.is_(None), valid_from_col <= t),
        or_(valid_until_col.is_(None), valid_until_col > t),
    )


def _row_to_dict(row, geom_keys: Sequence[str]) -> Dict[str, Any]:
    data = dict(row.__dict__)
    data.pop("_sa_instance_state", None)
    for key in geom_keys:
        data[key] = wkb_to_geojson(data.get(key))
    return data


class MarineRepository:
    """Low-level persistence for marine observations, zones, warnings."""

    def __init__(self, session: AsyncSession, srid: int = 4326):
        self.session = session
        self.srid = srid

    # ------------------------------------------------------------------ sources
    async def upsert_source(self, info: Dict[str, Any]) -> DataSource:
        stmt = pg_insert(DataSource).values(**info)
        stmt = stmt.on_conflict_do_update(
            index_elements=["name"],
            set_={
                "display_name": stmt.excluded.display_name,
                "base_url": stmt.excluded.base_url,
                "enabled": stmt.excluded.enabled,
                "source_type": stmt.excluded.source_type,
            },
        )
        await self.session.execute(stmt)
        return (await self.session.execute(
            select(DataSource).where(DataSource.name == info["name"])
        )).scalars().one()

    async def set_source_success(self, name: str, latest_data_timestamp: Optional[datetime] = None) -> None:
        await self.session.execute(
            update(DataSource)
                .where(DataSource.name == name)
                .values(
                    status="live",
                    last_successful_fetch=datetime.utcnow(),
                    consecutive_failures=0,
                    last_error=None,
                    latest_data_timestamp=latest_data_timestamp,
                )
        )

    async def set_source_failure(self, name: str, error: str, category: str) -> int:
        """Mark a source as degraded; returns the consecutive failure count."""
        current = (await self.session.execute(
            select(DataSource.consecutive_failures, DataSource.status)
                .where(DataSource.name == name)
        )).one_or_none()
        failures = (current[0] + 1) if current else 1
        await self.session.execute(
            update(DataSource)
                .where(DataSource.name == name)
                .values(
                    status=("unavailable" if failures <= 2 else "stale"),
                    last_error=error[:2000] if error else None,
                    consecutive_failures=failures,
                )
        )
        return failures

    async def replace_capabilities(self, source_id: int, capabilities: Sequence[Dict[str, Any]]) -> None:
        await self.session.execute(delete(SourceCapability).where(SourceCapability.source_id == source_id))
        for cap in capabilities:
            self.session.add(SourceCapability(source_id=source_id, **cap))

    async def get_tracked_source(self, name: str) -> Optional[DataSource]:
        return (await self.session.execute(
            select(DataSource).where(DataSource.name == name)
        )).scalars().first()

    async def list_tracked_sources(self) -> List[DataSource]:
        return list((await self.session.execute(
            select(DataSource).order_by(DataSource.name)
        )).scalars())

    # ----------------------------------------------------------- idempotent inserts
    async def insert_ocean(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        """Insert observations; returns (inserted, duplicates) using the
        (source, source_record_id) natural key - idempotent."""
        inserted = await self._exec_insert(OceanObservation, rows, ["source", "source_record_id"],
                                           "uq_ocean_source_record")
        return inserted, max(0, len(rows) - inserted)

    async def insert_weather_observation(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        inserted = await self._exec_insert(WeatherObservation, rows, ["source", "source_record_id"],
                                           "uq_weather_obs_source_record")
        return inserted, max(0, len(rows) - inserted)

    async def insert_weather_forecast(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        inserted = await self._exec_insert(WeatherForecast, rows, ["source", "source_record_id"],
                                           "uq_weather_fc_source_record")
        return inserted, max(0, len(rows) - inserted)

    async def insert_tides(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        inserted = await self._exec_insert(TidePrediction, rows, ["source", "source_record_id"],
                                           "uq_tides_source_record")
        return inserted, max(0, len(rows) - inserted)

    async def insert_pfz(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        inserted = await self._exec_insert(PFZZone, rows, ["source", "source_record_id"],
                                           "uq_pfz_source_record")
        return inserted, max(0, len(rows) - inserted)

    async def insert_warnings(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        inserted = await self._exec_insert(MarineWarning, rows, ["warning_id"], "uq_marine_warning_id")
        return inserted, max(0, len(rows) - inserted)

    async def insert_restricted_areas(self, rows: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
        inserted = await self._exec_insert(RestrictedArea, rows, ["area_id"], "uq_restricted_area_id")
        return inserted, max(0, len(rows) - inserted)

    async def _exec_insert(self, model, rows: Sequence[Dict[str, Any]],
                           index_elements: Sequence[str], constraint: str) -> int:
        if not rows:
            return 0
        injected = [dict(r) for r in rows]
        if self._is_postgres:
            for r in injected:
                if r.get("ingested_at") is None:
                    r["ingested_at"] = datetime.utcnow()
            stmt = pg_insert(model).values(injected)
            try:
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=[*index_elements],
                    index_where=and_(*[getattr(model, c).is_not(None) for c in index_elements]),
                )
            except Exception:
                stmt = stmt.on_conflict_do_nothing(constraint=constraint)
            result = await self.session.execute(stmt)
            return result.rowcount or 0
        # Non-PostgreSQL fallback (test/dev): simple insert, tolerate duplicates.
        inserted = 0
        for r in injected:
            try:
                self.session.add(model(**r))
                inserted += 1
            except Exception:
                continue
        await self.session.flush()
        return inserted

    @property
    def _is_postgres(self) -> bool:
        return bool(self.session.bind) and "postgres" in str(self.session.bind.url).lower()

    # ------------------------------------------------------------ geo queries
    async def ocean_conditions(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        time: Optional[datetime] = None,
        limit: int = 5,
        srid: int = 4326,
    ) -> List[Dict[str, Any]]:
        all_conds: List[Any] = [
            geo.ST_DWithin(cast(OceanObservation.geom, Geography()),
                           point_geom(lon, lat, srid), radius_m) == True  # noqa: E712
        ]
        if time is not None:
            all_conds.append(OceanObservation.observation_time <= time)
        stmt = (
            select(OceanObservation)
                .where(*all_conds)
                .order_by(OceanObservation.observation_time.desc())
                .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        # secondary sort: locational closeness
        sorted_rows = sorted(rows, key=lambda r: abs(r.longitude - lon) + abs(r.latitude - lat))
        return [_row_to_dict(r, ["geom"]) for r in sorted_rows[:limit]]

    async def weather_observations(
        self, lat: float, lon: float, radius_m: float, time: Optional[datetime] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        conds = [geo.ST_DWithin(cast(WeatherObservation.geom, Geography()),
                                point_geom(lon, lat), radius_m) == True]  # noqa: E712
        if time is not None:
            conds.append(WeatherObservation.valid_time <= time)
        stmt = select(WeatherObservation).where(*conds).order_by(WeatherObservation.valid_time.desc()).limit(limit)
        return [_row_to_dict(r, ["geom"]) for r in (await self.session.scalars(stmt)).all()]

    async def weather_forecasts(
        self, lat: float, lon: float, radius_m: float,
        valid_time: Optional[datetime] = None, limit: int = 5,
    ) -> List[Dict[str, Any]]:
        t = valid_time or datetime.utcnow()
        conds = [
            geo.ST_DWithin(cast(WeatherForecast.geom, Geography()), point_geom(lon, lat), radius_m) == True,  # noqa: E712
        ]
        if valid_time is not None:
            conds.append(WeatherForecast.valid_from <= valid_time)
            conds.append(WeatherForecast.valid_until > valid_time)
        stmt = (
            select(WeatherForecast)
                .where(*conds)
                .order_by(WeatherForecast.issue_time.desc(), WeatherForecast.valid_from.asc())
                .limit(limit)
        )
        return [_row_to_dict(r, ["geom"]) for r in (await self.session.scalars(stmt)).all()]

    async def tides(
        self, lat: float, lon: float, start: datetime, end: datetime,
        radius_m: float = 50_000, limit: int = 100, srid: int = 4326,
    ) -> List[Dict[str, Any]]:
        conds = [
            geo.ST_DWithin(cast(TidePrediction.geom, Geography()), point_geom(lon, lat, srid), radius_m) == True,  # noqa: E712
            TidePrediction.event_time >= start,
            TidePrediction.event_time <= end,
        ]
        stmt = select(TidePrediction).where(*conds).order_by(TidePrediction.event_time.asc()).limit(limit)
        return [_row_to_dict(r, ["geom"]) for r in (await self.session.scalars(stmt)).all()]

    async def pfz_zones(
        self, date: Optional[datetime] = None, geometry=None, limit: int = 20, srid: int = 4326
    ) -> List[Dict[str, Any]]:
        conds = []
        if geometry is not None:
            conds.append(geo.ST_Intersects(PFZZone.geometry, geometry) == True)  # noqa: E712
        if date is not None:
            conds.append(or_(
                PFZZone.valid_until.is_(None),
                PFZZone.valid_from.is_(None),
                and_(PFZZone.valid_from <= date, PFZZone.valid_until > date),
            ))
        stmt = select(PFZZone).where(*conds).order_by(PFZZone.generated_at.desc()).limit(limit)
        rows = [_row_to_dict(r, ["geometry"]) for r in (await self.session.scalars(stmt)).all()]
        if geometry is not None:
            rows.sort(key=lambda r: _bbox_distance(r.get("geometry"), geometry))
        return rows

    async def nearest_pfz(
        self, lat: float, lon: float, date: Optional[datetime] = None,
        limit: int = 3, srid: int = 4326,
    ) -> List[Dict[str, Any]]:
        conds = []
        if date is not None:
            conds.append(or_(
                PFZZone.valid_until.is_(None),
                PFZZone.valid_from.is_(None),
                and_(PFZZone.valid_from <= date, PFZZone.valid_until > date),
            ))
        stmt = select(PFZZone).where(*conds).order_by(PFZZone.generated_at.desc()).limit(50)
        rows = [_row_to_dict(r, ["geometry"]) for r in (await self.session.scalars(stmt)).all()]
        scored = []
        for r in rows:
            geom = r.get("geometry") or {}
            dist = _point_geojson_distance(lon, lat, geom)
            scored.append((dist, r))
        scored.sort(key=lambda pair: pair[0])
        return [r for _, r in scored[:limit]]

    async def warnings(
        self,
        geometry=None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        active_at: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        conds = []
        if geometry is not None:
            conds.append(geo.ST_Intersects(MarineWarning.geometry, geometry) == True)  # noqa: E712
        if start is not None:
            conds.append(or_(MarineWarning.valid_until.is_(None), MarineWarning.valid_until > start))
        if end is not None:
            conds.append(or_(MarineWarning.valid_from.is_(None), MarineWarning.valid_from < end))
        if active_at is not None:
            conds.append(active_window(MarineWarning.valid_from, MarineWarning.valid_until, active_at))
        stmt = select(MarineWarning).where(*conds).order_by(MarineWarning.issued_at.desc(), MarineWarning.id.desc()).limit(limit)
        return [_row_to_dict(r, ["geometry"]) for r in (await self.session.scalars(stmt)).all()]

    async def restricted_areas(
        self, geometry=None, active_at: Optional[datetime] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        conds: List[Any] = []
        if geometry is not None:
            conds.append(geo.ST_Intersects(RestrictedArea.geometry, geometry) == True)  # noqa: E712
        if active_at is not None:
            conds.append(active_window(RestrictedArea.valid_from, RestrictedArea.valid_until, active_at))
        stmt = select(RestrictedArea).where(*conds).order_by(RestrictedArea.area_name.asc()).limit(limit)
        return [_row_to_dict(r, ["geometry"]) for r in (await self.session.scalars(stmt)).all()]

    # ------------------------------------------------------------ ingestion runs
    async def start_ingestion_run(self, source: str, product: str) -> IngestionRun:
        run = IngestionRun(source=source, product=product, started_at=datetime.utcnow())
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish_ingestion_run(
        self, run_id: int, *, status: str, fetched=0, valid=0, suspicious=0,
        invalid=0, inserted=0, duplicates=0, error: Optional[str] = None,
        error_category: Optional[str] = None,
    ) -> None:
        await self.session.execute(
            update(IngestionRun)
                .where(IngestionRun.id == run_id)
                .values(
                    finished_at=datetime.utcnow(),
                    status=status,
                    records_fetched=fetched,
                    records_quality_valid=valid,
                    records_quality_suspicious=suspicious,
                    records_quality_invalid=invalid,
                    records_inserted=inserted,
                    records_duplicates=duplicates,
                    error=error,
                    error_category=error_category,
                )
        )

    async def latest_successful_run(self, source: str, product: str) -> Optional[IngestionRun]:
        return (await self.session.execute(
            select(IngestionRun)
                .where(IngestionRun.source == source,
                       IngestionRun.product == product,
                       IngestionRun.status == "success")
                .order_by(IngestionRun.finished_at.desc())
                .limit(1)
        )).scalars().first()


def _point_geojson_distance(lon: float, lat: float, geom: Optional[Dict]) -> float:
    """Approximate distance in degrees between a point and a GeoJSON geometry
    (centroid fallback).  Used only for client-side sort on non-PostGIS runs."""
    if not geom:
        return float("inf")
    try:
        from shapely.geometry import shape as to_shape
        geom_obj = to_shape(geom)
        from shapely.geometry import Point
        return float(geom_obj.distance(Point(lon, lat).buffer(0)))
    except Exception:
        return float("inf")


def _bbox_distance(geom: Optional[Dict], ref_geom: Dict) -> float:
    """Client-side approximate sort key for intersections."""
    if not geom:
        return float("inf")
    try:
        from shapely.geometry import shape as to_shape
        return float(to_shape(geom).distance(to_shape(ref_geom)))
    except Exception:
        return float("inf")