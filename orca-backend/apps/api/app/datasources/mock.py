# TEST-MOCK / sample marine data source.
#
# PURPOSE
# While waiting for government API keys to be approved, this adapter emits
# deterministic, physically-plausible SAMPLE data so the full pipeline
# (fetch -> validate -> normalize -> dedup -> store -> track) can be exercised
# and demonstrated end-to-end.
#
# HARD RULES
# - This is NEVER LIVE data.  `is_mock` is True, so every status surface
#   renders it as TEST_MOCK (never LIVE) - see registry._status_from_availability
#   and MarineDataService._source_statuses.
# - Data is gated by explicit config flags (MOCK_MARINE_ENABLED,
#   MOCK_WEATHER_ENABLED, MOCK_WARNINGS_ENABLED), all off by default.
# - Values stay within physical plausibility bounds so the validation
#   classifier treats them as VALID (they demonstrate pipeline success, not
#   error handling).
from datetime import timedelta
import structlog
from typing import Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceNotConfiguredError
from app.datasources.http import HttpDataTransport
from app.models.common import GeographicPoint, QualityStatus, utcnow
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.source import SourceCapability, SourceType
from app.models.tides import TidePrediction, TideType
from app.models.weather import WeatherForecast, WeatherObservation
from app.models.warnings import MarineWarning, WarningSeverity, WarningType

logger = structlog.get_logger(__name__)

# Sentinel base URL so `is_configured` is satisfiable without a real endpoint.
MOCK_BASE_URL = "mock://sample-data"


def _box_geojson(lat: float, lon: float, delta: float = 1.0) -> Dict:
    """Small valid Polygon around (lat, lon) for PFZ geometry."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - delta, lat - delta],
            [lon + delta, lat - delta],
            [lon + delta, lat + delta],
            [lon - delta, lat + delta],
            [lon - delta, lat - delta],
        ]],
    }


class MockMarineDataSource(BaseMarineDataSource):
    """Deterministic sample-data source (TEST-MOCK, never LIVE)."""

    name = "mock_marine"
    display_name = "TEST-MOCK Sample Marine Data (not live)"
    source_type = SourceType.UNKNOWN
    default_base_url = MOCK_BASE_URL
    is_mock = True

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    # -- configuration ------------------------------------------------
    @property
    def base_url(self) -> str:
        return MOCK_BASE_URL

    @property
    def api_key(self) -> Optional[str]:
        return None

    @property
    def enabled(self) -> bool:
        # Enabled if any mock product flag is on (the per-product fetchers
        # additionally check their own flag so shutdown is fine-grained).
        return bool(
            self.settings.mock_marine_enabled
            or self.settings.mock_weather_enabled
            or self.settings.mock_warnings_enabled
        )

    @property
    def capabilities(self) -> List[SourceCapability]:
        caps: List[SourceCapability] = []
        if self.settings.mock_marine_enabled:
            caps += [
                SourceCapability(
                    name="sample_ocean_conditions",
                    description="TEST-MOCK ocean conditions sample data",
                    data_product="ocean", config_required=False,
                ),
                SourceCapability(
                    name="sample_tide_predictions",
                    description="TEST-MOCK tide predictions sample data",
                    data_product="tides", config_required=False,
                ),
                SourceCapability(
                    name="sample_pfz_advisories",
                    description="TEST-MOCK PFZ advisory sample data",
                    data_product="pfz", config_required=False,
                ),
            ]
        if self.settings.mock_weather_enabled:
            caps += [
                SourceCapability(
                    name="sample_marine_weather",
                    description="TEST-MOCK marine weather observation sample data",
                    data_product="weather_observation", config_required=False,
                ),
                SourceCapability(
                    name="sample_marine_weather_forecast",
                    description="TEST-MOCK marine weather forecast sample data",
                    data_product="weather_forecast", config_required=False,
                ),
            ]
        if self.settings.mock_warnings_enabled:
            caps.append(SourceCapability(
                name="sample_marine_warnings",
                description="TEST-MOCK marine warnings sample data",
                data_product="warnings", config_required=False,
            ))
        return caps

    # -- ocean ---------------------------------------------------------
    async def fetch_ocean(self, *, lat: float, lon: float, time=None, **kw) -> List[OceanConditions]:
        if not self.settings.mock_marine_enabled:
            raise SourceNotConfiguredError("mock marine source is disabled")
        now = time or utcnow()
        return [
            OceanConditions(
                latitude=lat,
                longitude=lon,
                observation_time=now,
                source_timestamp=now,
                sst_c=29.4,
                chlorophyll=0.62,
                wave_height_m=1.1,
                wave_period_s=8.0,
                wave_direction_deg=210.0,
                current_speed_ms=0.8,
                current_direction_deg=45.0,
                salinity_psu=34.8,
                source=self.name,
                source_record_id=f"mock-ocean-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload={"mock": True},
            )
        ]

    # -- weather -----------------------------------------------------
    async def fetch_weather_observation(self, *, lat: float, lon: float, time=None, **kw) -> List[WeatherObservation]:
        if not self.settings.mock_weather_enabled:
            raise SourceNotConfiguredError("mock weather source is disabled")
        now = time or utcnow()
        return [
            WeatherObservation(
                latitude=lat,
                longitude=lon,
                valid_time=now,
                source_timestamp=now,
                temperature_c=29.0,
                wind_speed_ms=6.0,
                wind_direction_deg=120.0,
                precipitation_mm=0.0,
                pressure_hpa=1008.0,
                humidity_pct=78.0,
                visibility_m=15000.0,
                lightning=False,
                condition="partly_cloudy",
                source=self.name,
                source_record_id=f"mock-wobs-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload={"mock": True},
            )
        ]

    async def fetch_weather_forecast(self, *, lat: float, lon: float, time=None, **kw) -> List[WeatherForecast]:
        if not self.settings.mock_weather_enabled:
            raise SourceNotConfiguredError("mock weather source is disabled")
        now = time or utcnow()
        windows = [
            (0, 12, 29.5, 27.0, 6.0),
            (12, 24, 30.0, 27.5, 8.0),
            (24, 36, 30.0, 27.0, 7.0),
        ]
        records: List[WeatherForecast] = []
        for i, (sh, eh, tmax, tmin, wind) in enumerate(windows):
            records.append(WeatherForecast(
                latitude=lat,
                longitude=lon,
                issue_time=now,
                valid_from=now + timedelta(hours=sh),
                valid_until=now + timedelta(hours=eh),
                forecast_horizon_h=eh,
                source_timestamp=now,
                temperature_c=tmax - 1.0,
                temperature_min_c=tmin,
                temperature_max_c=tmax,
                wind_speed_ms=wind,
                wind_direction_deg=130.0,
                precipitation_mm=1.0 if i else 0.0,
                pressure_hpa=1008.0,
                humidity_pct=80.0,
                visibility_m=12000.0,
                lightning=False,
                condition="partly_cloudy",
                source=self.name,
                source_record_id=f"mock-wfcst-{lat:.2f}-{lon:.2f}-h{sh}",
                quality=QualityStatus.VALID,
                raw_payload={"mock": True},
            ))
        return records

    # -- warnings ------------------------------------------------------
    async def fetch_warnings(self, *, lat: float = None, lon: float = None, **kw) -> List[MarineWarning]:
        if not self.settings.mock_warnings_enabled:
            raise SourceNotConfiguredError("mock warnings source is disabled")
        now = utcnow()
        center_lat = lat if lat is not None else 9.9
        center_lon = lon if lon is not None else 76.3
        return [
            MarineWarning(
                warning_id="mock-cyclone-2026",
                warning_type=WarningType.STORM_WARNING,
                severity=WarningSeverity.MODERATE,
                geometry=_box_geojson(center_lat, center_lon),
                valid_from=now,
                valid_until=now + timedelta(hours=48),
                issued_at=now,
                updated_at=now,
                description="TEST-MOCK: sample storm warning for pipeline demonstration.",
                source=self.name,
                source_record_id=f"mock-warn-{center_lat:.2f}-{center_lon:.2f}",
                metadata={"mock": True, "test_only": True},
                raw_payload=None,
            )
        ]

    # -- tides --------------------------------------------------------
    async def fetch_tides(self, *, lat: float, lon: float, start=None, end=None, **kw) -> List[TidePrediction]:
        if not self.settings.mock_marine_enabled:
            raise SourceNotConfiguredError("mock marine source is disabled")
        now = start or utcnow()
        events = [
            (0, 1.6, TideType.HIGH),
            (6, 0.3, TideType.LOW),
            (12, 1.7, TideType.HIGH),
            (18, 0.2, TideType.LOW),
        ]
        records: List[TidePrediction] = []
        for i, (hoff, height, ttype) in enumerate(events):
            records.append(TidePrediction(
                location_name="TEST-MOCK (Kochi sample)",
                latitude=lat,
                longitude=lon,
                event_time=now + timedelta(hours=hoff),
                tide_height_m=height,
                tide_type=ttype,
                is_prediction=True,
                source_timestamp=now,
                source=self.name,
                source_record_id=f"mock-tide-{lat:.2f}-{lon:.2f}-{i}",
                quality=QualityStatus.VALID,
                raw_payload={"mock": True},
            ))
        return records

    # -- pfz ----------------------------------------------------------
    async def fetch_pfz(self, *, lat: float = None, lon: float = None, date=None, **kw) -> List[PFZZone]:
        if not self.settings.mock_marine_enabled:
            raise SourceNotConfiguredError("mock marine source is disabled")
        center_lat = lat if lat is not None else 9.9
        center_lon = lon if lon is not None else 76.3
        now = date or utcnow()
        return [
            PFZZone(
                geometry=_box_geojson(center_lat, center_lon, delta=0.5),
                centroid=GeographicPoint(latitude=center_lat, longitude=center_lon),
                generated_at=now,
                valid_from=now,
                valid_until=now + timedelta(hours=72),
                species=["tuna", "mackerel"],
                confidence=0.8,
                metadata={"mock": True},
                source_timestamp=now,
                source=self.name,
                source_record_id=f"mock-pfz-{center_lat:.2f}-{center_lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload={"mock": True},
            )
        ]