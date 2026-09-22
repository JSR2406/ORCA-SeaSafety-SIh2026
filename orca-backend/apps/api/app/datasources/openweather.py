# OpenWeatherMap adapter - real-time weather + marine fallback.
#
# Uses the keyed OpenWeatherMap API (api.openweathermap.org/data):
#   - weather_observation  -> /data/2.5/weather   (current weather)
#   - weather_forecast     -> /data/2.5/forecast  (5-day / 3-hour)
#   - ocean                -> /data/2.5/weather over sea (+ wave where present)
#
# OpenWeatherMap augments and backs up the Indian government sources (IMD /
# INCOIS / MOSDAC) which often need whitelisting or are rate-limited.  No
# fabricated data ever: if the key is missing or a call fails, the fetchers
# return empty and other sources cover the product.
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceInvalidDataError
from app.datasources.http import HttpDataTransport
from app.datasources.scrapers import (
    fetch_openweather_current,
    fetch_openweather_forecast,
    fetch_openweather_marine,
)
from app.models.common import QualityStatus, utcnow
from app.models.ocean import OceanConditions
from app.models.source import SourceCapability, SourceType
from app.models.weather import WeatherForecast, WeatherObservation

logger = logging.getLogger(__name__)


class OpenWeatherAdapter(BaseMarineDataSource):
    name = "openweather"
    display_name = "OpenWeatherMap"
    source_type = SourceType.OPEN_WEATHER

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "weather_observation": "/2.5/weather",
        "weather_forecast": "/2.5/forecast",
        "ocean": "/2.5/weather",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.openweather_base_url

    @property
    def api_key(self) -> Optional[str]:
        return self.settings.openweather_api_key or None

    @property
    def enabled(self) -> bool:
        return self.settings.openweather_enabled

    @property
    def is_configured(self) -> bool:
        # OpenWeatherMap genuinely needs a key (unlike the open gov endpoints).
        return bool(self.enabled and self.api_key)

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="current_weather",
                description="Current weather observations (temp, wind, pressure, humidity)",
                data_product="weather_observation",
                config_required=True,
            ),
            SourceCapability(
                name="weather_forecast",
                description="5-day / 3-hour weather forecast",
                data_product="weather_forecast",
                config_required=True,
            ),
            SourceCapability(
                name="marine_conditions",
                description="Surface marine conditions over coastal/ocean points",
                data_product="ocean",
                config_required=True,
            ),
        ]

    # ------------------------------------------------------------ observation
    async def fetch_weather_observation(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[WeatherObservation]:
        self._ensure_configured("weather_observation")
        data = await fetch_openweather_current(
            lat, lon, self.api_key, self.settings.openweather_units)
        if not data:
            return []
        try:
            return [WeatherObservation(
                latitude=lat,
                longitude=lon,
                valid_time=_from_ts(data.get("observation_time")) or (time or utcnow()),
                source_timestamp=utcnow(),
                temperature_c=data.get("temperature_c"),
                wind_speed_ms=data.get("wind_speed_ms"),
                wind_direction_deg=data.get("wind_direction_deg"),
                precipitation_mm=data.get("precipitation_mm"),
                pressure_hpa=data.get("pressure_hpa"),
                humidity_pct=data.get("humidity_pct"),
                visibility_m=data.get("visibility_m"),
                lightning=None,
                condition=data.get("condition"),
                source=self.name,
                source_record_id=f"ow-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=data,
            )]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid openweather observation: {exc}")

    # --------------------------------------------------------------- forecast
    async def fetch_weather_forecast(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[WeatherForecast]:
        self._ensure_configured("weather_forecast")
        data = await fetch_openweather_forecast(
            lat, lon, self.api_key, self.settings.openweather_units)
        if not data:
            return []
        entries = data.get("entries") or []
        try:
            issue_time = _from_ts(data.get("observation_time")) or (time or utcnow())
            fc = WeatherForecast(
                latitude=lat,
                longitude=lon,
                issue_time=issue_time,
                valid_from=issue_time,
                valid_until=issue_time + timedelta(hours=120),
                forecast_horizon_h=120,
                source_timestamp=utcnow(),
                temperature_c=entries[0].get("temperature_c") if entries else None,
                temperature_min_c=data.get("temp_min_c"),
                temperature_max_c=data.get("temp_max_c"),
                wind_speed_ms=data.get("wind_speed_ms"),
                wind_direction_deg=data.get("wind_direction_deg"),
                precipitation_mm=entries[0].get("precipitation_mm") if entries else None,
                pressure_hpa=data.get("pressure_hpa"),
                humidity_pct=data.get("humidity_pct"),
                visibility_m=None,
                lightning=None,
                condition=entries[0].get("condition") if entries else None,
                source=self.name,
                source_record_id=f"ow-fc-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=data,
            )
            return [fc]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid openweather forecast: {exc}")

    # ----------------------------------------------------------------- ocean
    async def fetch_ocean(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[OceanConditions]:
        self._ensure_configured("ocean")
        data = await fetch_openweather_marine(
            lat, lon, self.api_key, self.settings.openweather_units)
        if not data:
            return []
        try:
            return [OceanConditions(
                latitude=lat,
                longitude=lon,
                observation_time=_from_ts(data.get("observation_time")) or (time or utcnow()),
                source_timestamp=utcnow(),
                sst_c=None,
                chlorophyll=None,
                wave_height_m=None,
                wave_period_s=None,
                wave_direction_deg=None,
                current_speed_ms=None,
                current_direction_deg=None,
                salinity_psu=None,
                source=self.name,
                source_record_id=f"ow-ocean-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload=data,
            )]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid openweather marine data: {exc}")


def _from_ts(value) -> Optional[datetime]:
    """Convert a unix epoch timestamp (seconds) to an aware UTC datetime."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None
