# MarineDataService - the read-side facade for the Phase 1 data layer.
# All consumers (API routers, Phase 2 MCP tools, agents) read marine data
# through this service, which returns the uniform MarineDataResult envelope
# with status/sources/timestamps/freshness/provenance.  No mock fallback:
# unconfigured sources -> NOT_CONFIGURED, missing data -> UNAVAILABLE.
import structlog
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import Settings
from app.datasources.registry import SourceRegistry
from app.db.marine_repository import MarineRepository
from app.geo_utils import geojson_to_wkb
from app.models.common import DataStatus, utcnow
from app.models.result import (
    Freshness,
    MarineDataResult,
    ProvenanceEntry,
    QueryTimes,
    error_result,
    not_configured_result,
    unavailable_result,
)
from app.models.source import SourceStatus
from app.models.warnings import WarningStatus, evaluate_window_status

logger = structlog.get_logger(__name__)

PRODUCT_THRESHOLD_FIELD = {
    "ocean": "ocean_freshness_seconds",
    "weather_observation": "weather_freshness_seconds",
    "weather_forecast": "weather_freshness_seconds",
    "tides": "tide_freshness_seconds",
    "pfz": "pfz_freshness_seconds",
    "warnings": "warning_freshness_seconds",
}


class MarineDataService:
    def __init__(
        self,
        settings: Settings,
        registry: SourceRegistry,
        session_factory,
    ):
        self.settings = settings
        self.registry = registry
        self.session_factory = session_factory

    # ---------------------------------------------------------------- helpers
    def _threshold(self, product: str) -> int:
        field = PRODUCT_THRESHOLD_FIELD[product]
        return int(getattr(self.settings, field))

    def _configured_for(self, product: str) -> List[str]:
        out = []
        for source in self.registry.list():
            if source.is_configured and any(
                cap.data_product == product for cap in source.capabilities
            ):
                out.append(source.name)
        return out

    def _all_sources_mock(self, sources: List[str]) -> bool:
        """True when every configured source for a product is a TEST-MOCK source.

        Used to downgrade a computed LIVE status to TEST_MOCK so mock-only
        results are never presented as live real-world data.
        """
        if not sources:
            return False
        if self.registry is None:
            return False
        for source in self.registry.list():
            if source.is_configured and source.name in sources and not source.is_mock:
                return False
        return True

    def _validate_point(self, lat: float, lon: float) -> None:
        if not (-90 <= lat <= 90):
            raise ValueError(f"latitude out of range: {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"longitude out of range: {lon}")

    def _render(self, *, status: DataStatus, product: str, data: Any,
                sources: List[str], rows: List[Dict[str, Any]],
                ts_field: str, source_status: Optional[List[SourceStatus]] = None,
                warnings: Optional[List[str]] = None) -> MarineDataResult:
        latest_ts = None
        for row in rows:
            val = row.get(ts_field)
            if val is not None and (latest_ts is None or val > latest_ts):
                latest_ts = val
        freshness = None
        if latest_ts is not None:
            age = max(0.0, (utcnow() - latest_ts).total_seconds())
            threshold = self._threshold(product)
            freshness = Freshness(
                threshold_seconds=threshold,
                age_seconds=age,
                latest_data_timestamp=latest_ts,
                is_within_threshold=age <= threshold,
            )
            if status not in (DataStatus.STALE, DataStatus.UNAVAILABLE):
                status = DataStatus.LIVE if age <= threshold else DataStatus.STALE
            if status == DataStatus.LIVE and self._all_sources_mock(sources):
                status = DataStatus.TEST_MOCK
        return MarineDataResult(
            status=status,
            data=data,
            sources=sources,
            timestamps=QueryTimes(
                requested_at=utcnow(),
                data_timestamp=latest_ts,
                source_timestamp=rows[0].get("source_timestamp") if rows else None,
                retrieved_at=utcnow(),
            ),
            freshness=freshness,
            provenance=[ProvenanceEntry(
                source=r["source"],
                source_record_id=r.get("source_record_id"),
                observation_time=r.get(ts_field),
                retrieved_at=utcnow(),
            ) for r in rows],
            source_status=source_status,
            warnings=warnings or [],
            confidence=_confidence(freshness),
        )

    async def _source_statuses(self, repo: MarineRepository) -> List[SourceStatus]:
        tracked = {d.name: d for d in await repo.list_tracked_sources()}
        statuses: List[SourceStatus] = []
        now = utcnow()
        for source in self.registry.list():
            avail = source.get_availability()
            tr = tracked.get(source.name)
            threshold = None
            age = None
            last_fetch = tr.last_successful_fetch if tr else avail.last_successful_fetch
            if source.is_mock:
                sstatus = DataStatus.TEST_MOCK
                message = avail.message
            elif tr and tr.status in ("stale", "unavailable"):
                sstatus = DataStatus.STALE if tr.status == "stale" else DataStatus.UNAVAILABLE
                message = tr.last_error or avail.message
            elif avail.configured:
                sstatus = DataStatus.LIVE
                message = "configured and healthy"
            else:
                sstatus = DataStatus.NOT_CONFIGURED
                message = avail.message
            if last_fetch is not None:
                threshold = self._threshold("ocean")
                if hasattr(now, "tzinfo") and now.tzinfo and last_fetch.tzinfo is None:
                    last_fetch = last_fetch.replace(tzinfo=timezone.utc)
                age = max(0.0, (now - (last_fetch if last_fetch.tzinfo else last_fetch.replace(tzinfo=timezone.utc))).total_seconds())
            statuses.append(SourceStatus(
                source=source.name,
                source_type=source.source_type,
                status=sstatus,
                configured=avail.configured,
                connected=avail.connected or avail.configured,
                last_successful_fetch=last_fetch,
                latest_data_timestamp=tr.latest_data_timestamp if tr else None,
                threshold_seconds=threshold,
                age_seconds=age if age is not None else None,
                consecutive_failures=tr.consecutive_failures if tr else 0,
                last_error=tr.last_error if tr else None,
                message=message,
                evaluated_at=now,
            ))
        return statuses

    # ---------------------------------------------------------------- ocean
    async def get_ocean_conditions(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        radius_km: float = 25.0, limit: int = 5,
    ) -> MarineDataResult:
        self._validate_point(lat, lon)
        sources = self._configured_for("ocean")
        if not sources:
            not_found = not_configured_result("openmeteo")
            return not_found
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            rows = await repo.ocean_conditions(
                lat, lon, radius_m=radius_km * 1000.0, time=time, limit=limit,
                srid=self.settings.geom_srid)
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="ocean", data=None,
                    sources=sources, rows=[], ts_field="observation_time",
                    source_status=statuses,
                    warnings=[f"No ocean observations within {radius_km:g} km of "
                              f"({lat:.4f}, {lon:.4f})."],
                )
            return self._render(
                status=DataStatus.LIVE, product="ocean", data=rows,
                sources=sources, rows=rows, ts_field="observation_time",
                source_status=statuses,
            )

    # ---------------------------------------------------------------- weather
    async def get_weather_forecast(
        self, lat: float, lon: float, valid_time: Optional[datetime] = None,
        radius_km: float = 50.0, limit: int = 5,
    ) -> MarineDataResult:
        self._validate_point(lat, lon)
        sources = self._configured_for("weather_forecast")
        if not sources:
            return not_configured_result("openmeteo")
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            rows = await repo.weather_forecasts(
                lat, lon, radius_m=radius_km * 1000.0, valid_time=valid_time, limit=limit,
            )
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="weather_forecast", data=None,
                    sources=sources, rows=[], ts_field="issue_time", source_status=statuses,
                    warnings=[f"No weather forecast within {radius_km:g} km of "
                              f"({lat:.4f}, {lon:.4f})."],
                )
            return self._render(
                status=DataStatus.LIVE, product="weather_forecast", data=rows,
                sources=sources, rows=rows, ts_field="issue_time", source_status=statuses,
            )

    async def get_weather_observation(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        radius_km: float = 50.0, limit: int = 5,
    ) -> MarineDataResult:
        self._validate_point(lat, lon)
        sources = self._configured_for("weather_observation")
        if not sources:
            return not_configured_result("openmeteo")
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            rows = await repo.weather_observations(
                lat, lon, radius_m=radius_km * 1000.0, time=time, limit=limit,
            )
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="weather_observation", data=None,
                    sources=sources, rows=[], ts_field="valid_time", source_status=statuses,
                    warnings=[f"No weather observations within {radius_km:g} km of "
                              f"({lat:.4f}, {lon:.4f})."],
                )
            return self._render(
                status=DataStatus.LIVE, product="weather_observation", data=rows,
                sources=sources, rows=rows, ts_field="valid_time", source_status=statuses,
            )

    # ---------------------------------------------------------------- tides
    async def get_tides(
        self, lat: float, lon: float,
        start: Optional[datetime] = None, end: Optional[datetime] = None,
        radius_km: float = 50.0, limit: int = 100,
    ) -> MarineDataResult:
        self._validate_point(lat, lon)
        now = utcnow()
        start = start or now - timedelta(hours=24)
        end = end or now + timedelta(hours=48)
        if end < start:
            raise ValueError("tide 'end' must be after 'start'")
        sources = self._configured_for("tides")
        if not sources:
            return not_configured_result("stormglass")
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            rows = await repo.tides(
                lat, lon, start, end,
                radius_m=radius_km * 1000.0, limit=limit, srid=self.settings.geom_srid,
            )
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="tides", data=None,
                    sources=sources, rows=[], ts_field="event_time", source_status=statuses,
                    warnings=[f"No tide predictions within {radius_km:g} km of "
                              f"({lat:.4f}, {lon:.4f}) for the requested window."],
                )
            return self._render(
                status=DataStatus.LIVE, product="tides", data=rows,
                sources=sources, rows=rows, ts_field="event_time", source_status=statuses,
            )

    # ---------------------------------------------------------------- pfz
    async def get_pfz(
        self, lat: Optional[float] = None, lon: Optional[float] = None,
        date: Optional[datetime] = None, geometry: Optional[Dict] = None,
        radius_km: float = 50.0, limit: int = 20,
    ) -> MarineDataResult:
        if lat is not None or lon is not None:
            if lat is None or lon is None:
                raise ValueError("both lat and lon are required")
            self._validate_point(lat, lon)
        sources = self._configured_for("pfz")
        if not sources:
            return not_configured_result("coastwatch")
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            if lat is not None and lon is not None:
                rows = await repo.nearest_pfz(
                    lat, lon, date=date, limit=limit, srid=self.settings.geom_srid)
            else:
                geom = geojson_to_wkb(geometry, srid=self.settings.geom_srid) if geometry else None
                rows = await repo.pfz_zones(date=date, geometry=geom, limit=limit,
                                            srid=self.settings.geom_srid)
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="pfz", data=None,
                    sources=sources, rows=[], ts_field="generated_at", source_status=statuses,
                    warnings=["No PFZ advisory zones available for the requested area/time."],
                )
            return self._render(
                status=DataStatus.LIVE, product="pfz", data=rows,
                sources=sources, rows=rows, ts_field="generated_at", source_status=statuses,
            )

    # ---------------------------------------------------------------- warnings
    async def get_marine_warnings(
        self, lat: Optional[float] = None, lon: Optional[float] = None,
        geometry: Optional[Dict] = None,
        start: Optional[datetime] = None, end: Optional[datetime] = None,
        active_at: Optional[datetime] = None, limit: int = 50,
    ) -> MarineDataResult:
        if lat is not None or lon is not None:
            if lat is None or lon is None:
                raise ValueError("both lat and lon are required")
            self._validate_point(lat, lon)
        sources = self._configured_for("warnings")
        if not sources:
            return not_configured_result("gdacs")
        ref_geom = None
        if geometry is not None:
            ref_geom = geojson_to_wkb(geometry, srid=self.settings.geom_srid)
        elif lat is not None:
            from shapely.geometry import Point
            ref_geom = geojson_to_wkb(
                {"type": "Point", "coordinates": [lon, lat]},
                srid=self.settings.geom_srid)
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            rows = await repo.warnings(
                geometry=ref_geom, start=start, end=end, active_at=None, limit=limit)
            now = active_at or utcnow()
            for row in rows:
                row["status"] = evaluate_window_status(
                    row.get("valid_from"), row.get("valid_until"), now)
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="warnings", data=None,
                    sources=sources, rows=[], ts_field="issued_at", source_status=statuses,
                    warnings=["No marine warnings in effect for the requested area."],
                )
            return self._render(
                status=DataStatus.LIVE, product="warnings", data=rows,
                sources=sources, rows=rows, ts_field="issued_at", source_status=statuses,
            )

    # ---------------------------------------------------------------- restrictions
    async def get_restricted_areas(
        self, lat: Optional[float] = None, lon: Optional[float] = None,
        geometry: Optional[Dict] = None, time: Optional[datetime] = None,
        limit: int = 50,
    ) -> MarineDataResult:
        if lat is not None or lon is not None:
            if lat is None or lon is None:
                raise ValueError("both lat and lon are required")
            self._validate_point(lat, lon)
        sources = self._configured_for("warnings")
        if not sources:
            return not_configured_result("gdacs")
        ref_geom = None
        if geometry is not None:
            ref_geom = geojson_to_wkb(geometry, srid=self.settings.geom_srid)
        elif lat is not None:
            ref_geom = geojson_to_wkb(
                {"type": "Point", "coordinates": [lon, lat]}, srid=self.settings.geom_srid)
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            statuses = await self._source_statuses(repo)
            rows = await repo.restricted_areas(
                geometry=ref_geom, active_at=None, limit=limit)
            now = time or utcnow()
            for row in rows:
                row["status"] = evaluate_window_status(
                    row.get("valid_from"), row.get("valid_until"), now)
            if not rows:
                return self._render(
                    status=DataStatus.UNAVAILABLE, product="warnings", data=None,
                    sources=sources, rows=[], ts_field="ingested_at", source_status=statuses,
                    warnings=["No restricted areas intersect the requested location."],
                )
            return self._render(
                status=DataStatus.LIVE, product="warnings", data=rows,
                sources=sources, rows=rows, ts_field="ingested_at", source_status=statuses,
            )

    async def check_marine_restrictions(
        self, lat: float, lon: float, time: Optional[datetime] = None,
    ) -> MarineDataResult:
        self._validate_point(lat, lon)
        result = await self.get_restricted_areas(lat=lat, lon=lon, time=time)
        if result.status in (DataStatus.NOT_CONFIGURED, DataStatus.ERROR):
            return result
        areas = result.data or []
        active_areas = [a for a in areas if a.get("status") == WarningStatus.ACTIVE]
        result.data = {
            "restricted": bool(active_areas),
            "active_areas": active_areas,
            "total_areas": len(areas),
        }
        if not areas and result.status == DataStatus.UNAVAILABLE:
            result.data = {"restricted": False, "active_areas": [], "total_areas": 0}
            result.status = DataStatus.LIVE
        return result

    # ---------------------------------------------------------------- source status
    async def sources_status(self) -> List[SourceStatus]:
        async with self.session_factory() as session:
            repo = MarineRepository(session, srid=self.settings.geom_srid)
            return await self._source_statuses(repo)


def _confidence(freshness: Optional[Freshness]) -> Optional[float]:
    if freshness is None:
        return None
    if freshness.is_within_threshold:
        return 0.85
    if freshness.age_seconds is not None and freshness.threshold_seconds:
        return max(0.1, round(0.6 * (freshness.threshold_seconds / freshness.age_seconds), 2))
    return 0.3