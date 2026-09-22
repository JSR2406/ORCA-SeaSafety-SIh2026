# Open-Meteo adapter - keyless open marine / weather forecast APIs.
#
# Primary real-time weather + wave source (replaces the unreliable gov feeds):
#   - ocean                -> Marine API /v1/marine (wave height/period/direction)
#   - weather_observation  -> Forecast API /v1/forecast (current block)
#   - weather_forecast     -> Forecast API /v1/forecast (24h horizon)
#
# No auth key required.  Never fabricates data: failures return empty lists.
from datetime import timedelta
import logging
from typing import Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceInvalidDataError
from app.datasources.http import HttpDataTransport
from app.datasources.scrapers import (
    fetch_open_meteo_forecast,
    fetch_open_meteo_marine,
)
from app.models.common import QualityStatus, utcnow
from app.models.ocean import OceanConditions
from app.models.source import SourceCapability, SourceType
from app.models.weather import WeatherForecast, WeatherObservation

logger = logging.getLogger(__name__)

# WMO weather interpretation codes -> human condition label.
_WMO_CONDITION = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "heavy freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "light snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}


class OpenMeteoAdapter(BaseMarineDataSource):
    name = "openmeteo"
    display_name = "Open-Meteo"
    source_type = SourceType.OPEN_METEO

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "ocean": "/v1/marine",
        "weather_observation": "/v1/forecast",
        "weather_forecast": "/v1/forecast",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.open_meteo_marine_url

    @property
    def api_key(self) -> Optional[str]:
        return None

    @property
    def enabled(self) -> bool:
        return self.settings.open_meteo_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="marine_waves",
                description="Near-real-time wave height, period and direction in open water",
                data_product="ocean",
            ),
            SourceCapability(
                name="current_weather",
                description="Current weather observation (temp, wind, pressure, humidity)",
                data_product="weather_observation",
            ),
            SourceCapability(
                name="weather_forecast",
                description="24h weather forecast at the point",
                data_product="weather_forecast",
            ),
        ]

    async def fetch_ocean(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[OceanConditions]:
        self._ensure_configured("ocean")
        data = await fetch_open_meteo_marine(lat, lon)
        if not data:
            return []
        try:
            return [OceanConditions(
                latitude=lat,
                longitude=lon,
                observation_time=_parse_dt(data.get("observation_time")) or (time or utcnow()),
                source_timestamp=utcnow(),
                sst_c=None,
                chlorophyll=None,
                wave_height_m=_num(data.get("wave_height_m")),
                wave_period_s=_num(data.get("wave_period_s")),
                wave_direction_deg=_num(data.get("wave_direction_deg")),
                current_speed_ms=None,
                current_direction_deg=None,
                salinity_psu=None,
                source=self.name,
                source_record_id=f"om-ocean-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=data,
            )]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid open-meteo marine data: {exc}")

    async def fetch_weather_observation(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[WeatherObservation]:
        self._ensure_configured("weather_observation")
        data = await fetch_open_meteo_forecast(lat, lon)
        if not data:
            return []
        try:
            return [WeatherObservation(
                latitude=lat,
                longitude=lon,
                valid_time=_parse_dt(data.get("observation_time")) or (time or utcnow()),
                source_timestamp=utcnow(),
                temperature_c=_num(data.get("temperature_c")),
                wind_speed_ms=_num(data.get("wind_speed_ms")),
                wind_direction_deg=_num(data.get("wind_direction_deg")),
                precipitation_mm=_num(data.get("precipitation_mm")),
                pressure_hpa=_num(data.get("pressure_hpa")),
                humidity_pct=_num(data.get("humidity_pct")),
                visibility_m=None,
                lightning=None,
                condition=_wmo_condition(data.get("weather_code")),
                source=self.name,
                source_record_id=f"om-obs-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=data,
            )]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid open-meteo observation: {exc}")

    async def fetch_weather_forecast(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[WeatherForecast]:
        self._ensure_configured("weather_forecast")
        data = await fetch_open_meteo_forecast(lat, lon)
        if not data:
            return []
        try:
            begin = time or utcnow()
            return [WeatherForecast(
                latitude=lat,
                longitude=lon,
                issue_time=begin,
                valid_from=begin,
                valid_until=begin + timedelta(hours=24),
                forecast_horizon_h=24,
                source_timestamp=utcnow(),
                temperature_c=_num(data.get("temperature_c")),
                temperature_min_c=None,
                temperature_max_c=None,
                wind_speed_ms=_num(data.get("wind_speed_ms")),
                wind_direction_deg=_num(data.get("wind_direction_deg")),
                precipitation_mm=_num(data.get("precipitation_mm")),
                pressure_hpa=_num(data.get("pressure_hpa")),
                humidity_pct=_num(data.get("humidity_pct")),
                visibility_m=None,
                lightning=None,
                condition=_wmo_condition(data.get("weather_code")),
                source=self.name,
                source_record_id=f"om-fc-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=data,
            )]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid open-meteo forecast: {exc}")


def _num(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_dt(value) -> Optional[object]:
    from app.datasources.normalize import parse_datetime
    return parse_datetime(value)


def _wmo_condition(code) -> Optional[str]:
    try:
        return _WMO_CONDITION.get(int(code))
    except (ValueError, TypeError):
        return None