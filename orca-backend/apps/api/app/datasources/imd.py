# IMD adapter - India Meteorological Department.
#
# Uses the real IMD public APIs at api.imd.gov.in (no auth required).
# Products served:
#   - weather_observation  → Sea Area Bulletin (/api/v1/seabulletin)
#   - weather_forecast     → Coastal Bulletin (/api/v1/coastalbulletin)
#   - warnings             → Cyclone Track + Cyclone Wind + Port Warning
#
# All endpoint contracts are based on the published IMD API reference:
#   https://api.imd.gov.in/public/api_reference.html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceInvalidDataError
from app.datasources.http import HttpDataTransport
from app.datasources.normalize import (
    ensure_list,
    parse_datetime,
    take_numeric,
    take_string,
)
from app.datasources.scrapers import (
    fetch_imd_coastal_bulletin,
    fetch_imd_cyclone_track,
    fetch_imd_cyclone_wind,
    fetch_imd_port_warning,
    fetch_imd_sea_bulletin,
)
from app.models.common import QualityStatus, utcnow
from app.models.source import SourceCapability, SourceType
from app.models.weather import WeatherForecast, WeatherObservation
from app.models.warnings import MarineWarning, WarningSeverity, WarningType

logger = logging.getLogger(__name__)

# IMD sea area IDs for sea area bulletin queries.
# Full list: https://mausam.imd.gov.in/responsive/marine_forecast.php
IMD_SEA_AREAS = [
    {"id": "101", "name": "North Arabian Sea"},
    {"id": "102", "name": "Central Arabian Sea"},
    {"id": "103", "name": "South Arabian Sea"},
    {"id": "104", "name": "North Bay of Bengal"},
    {"id": "105", "name": "Central Bay of Bengal"},
    {"id": "106", "name": "South Bay of Bengal"},
    {"id": "107", "name": "Lakshadweep Area"},
    {"id": "108", "name": "Maldives Area"},
    {"id": "109", "name": "Comorin Area"},
    {"id": "110", "name": "Andaman Sea"},
]

# IMD port IDs for port warnings.
IMD_PORT_IDS = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
]


def _wind_knots_to_ms(knots_str: str) -> Optional[float]:
    """Parse wind string like '5 - 10 Knots' and return max in m/s."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*[Kk]nots?", knots_str)
    if match:
        try:
            return float(match.group(2)) * 0.5144  # knots to m/s
        except ValueError:
            pass
    # Single value.
    match = re.search(r"(\d+(?:\.\d+)?)\s*[Kk]nots?", knots_str)
    if match:
        try:
            return float(match.group(1)) * 0.5144
        except ValueError:
            pass
    return None


def _wind_direction_deg(direction_str: str) -> Optional[float]:
    """Parse wind direction string like 'East/ South Easterly' to degrees."""
    direction_map = {
        "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
        "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
        "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
        "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
    }
    # Try to match a compass direction.
    for key, deg in direction_map.items():
        if key.lower() in direction_str.lower():
            return deg
    # Try numeric.
    match = re.search(r"(\d{1,3})\s*deg", direction_str, re.I)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


class IMDAdapter(BaseMarineDataSource):
    name = "imd"
    display_name = "India Meteorological Department"
    source_type = SourceType.IMD

    # IMD public API endpoints (no auth, JSON responses).
    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "weather_observation": "/api/v1/seabulletin",
        "weather_forecast": "/api/v1/coastalbulletin",
        "warnings": "/api/v1/cyclone_wind",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.imd_base_url

    @property
    def api_key(self) -> Optional[str]:
        return self.settings.imd_api_key or None

    @property
    def enabled(self) -> bool:
        return self.settings.imd_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="marine_weather_observation",
                description="Marine weather observations from Sea Area Bulletins",
                data_product="weather_observation",
                config_required=True,
            ),
            SourceCapability(
                name="marine_weather_forecast",
                description="Coastal weather forecasts from Coastal Bulletins",
                data_product="weather_forecast",
                config_required=True,
            ),
            SourceCapability(
                name="cyclone_warnings",
                description="Cyclone track, wind warnings and port warnings",
                data_product="warnings",
                config_required=True,
            ),
        ]

    # ----------------------------------------------------------- observations
    async def fetch_weather_observation(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[WeatherObservation]:
        self._ensure_configured("weather_observation")

        # Determine which sea area bulletin to fetch based on lat/lon.
        area_id = self._nearest_sea_area(lat, lon)
        raw_bulletins = await fetch_imd_sea_bulletin(area_id)

        results: List[WeatherObservation] = []
        for bulletin in raw_bulletins:
            try:
                obs = self._parse_sea_bulletin_as_observation(bulletin, lat, lon)
                if obs:
                    results.append(obs)
            except Exception as exc:
                logger.debug("imd_obs_parse_skip", error=str(exc))
                continue

        # Also try AWS data for direct point observations.
        if not results:
            aws_data = await self._fetch_aws_near(lat, lon)
            results.extend(aws_data)

        # IMD's public API requires whitelisting; try context providers in
        # order: OpenWeatherMap (keyed) -> Open-Meteo (keyless).  These are
        # real fallbacks, never fabricated data.
        if not results:
            ow = await self._fetch_openweather_observation(lat, lon)
            if ow:
                results.append(ow)
            else:
                om = await self._fetch_open_meteo_weather(lat, lon)
                if om:
                    obs = om.get("observation")
                    if obs:
                        results.append(obs)

        return results

    async def _fetch_openweather_observation(
        self, lat: float, lon: float
    ) -> Optional[WeatherObservation]:
        """Fallback real observation from OpenWeatherMap (keyed)."""
        from app.datasources.scrapers import fetch_openweather_current

        key = self.settings.openweather_api_key
        if not key or not self.settings.openweather_enabled:
            return None
        data = await fetch_openweather_current(lat, lon, key, self.settings.openweather_units)
        if not data:
            return None
        return WeatherObservation(
            latitude=lat,
            longitude=lon,
            valid_time=_from_ow_ts(data.get("observation_time")) or utcnow(),
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
            source_record_id=f"openweather-{lat:.2f}-{lon:.2f}",
            quality=QualityStatus.VALID,
            raw_payload={"provider": "openweathermap", **data},
        )

    def _parse_sea_bulletin_as_observation(
        self, bulletin: dict, lat: float, lon: float
    ) -> Optional[WeatherObservation]:
        """Convert an IMD Sea Area Bulletin into a WeatherObservation."""
        obs_time = parse_datetime(
            bulletin.get("Date of Observation") or bulletin.get("Valid From")
        )
        wind_str = take_string(bulletin, "Wind")
        weather_str = take_string(bulletin, "Weather")
        vis_str = take_string(bulletin, "Visibility")
        sea_str = take_string(bulletin, "Sea Condition")
        update_time = parse_datetime(bulletin.get("Update Time"))

        wind_speed = _wind_knots_to_ms(wind_str)
        wind_dir = _wind_direction_deg(wind_str)

        # Extract temperature if present in the bulletin.
        temp = take_numeric(bulletin, "Temperature", "temperature", "temp")

        # Map weather string to condition.
        condition = weather_str if weather_str else sea_str

        # Parse visibility from string like "Good Becoming Moderate".
        visibility_m = _parse_visibility(vis_str)

        # Pressure from bulletin if available.
        pressure = take_numeric(bulletin, "MSLP", "Pressure", "pressure", "slp")

        return WeatherObservation(
            latitude=lat,
            longitude=lon,
            valid_time=obs_time or update_time or utcnow(),
            source_timestamp=update_time or utcnow(),
            temperature_c=temp,
            wind_speed_ms=wind_speed,
            wind_direction_deg=wind_dir,
            precipitation_mm=None,
            pressure_hpa=pressure,
            humidity_pct=None,
            visibility_m=visibility_m,
            lightning=None,
            condition=condition or None,
            source=self.name,
            source_record_id=bulletin.get("Id"),
            quality=QualityStatus.VALID,
            raw_payload=bulletin,
        )

    async def _fetch_aws_near(self, lat: float, lon: float) -> List[WeatherObservation]:
        """Try to fetch AWS (Automatic Weather Station) data near a point."""
        # IMD AWS data is at /api/v1/aws_data — it lists all stations.
        # We fetch and find the nearest station.
        url = f"{self.base_url.rstrip('/')}/api/v1/aws_data"
        try:
            data = await self.transport.get_json(url)
        except Exception:
            return []

        if not data:
            return []

        stations = ensure_list(data)
        # Find nearest station within 2 degrees.
        best_dist = float("inf")
        best_station = None
        for station in stations:
            try:
                s_lat = float(station.get("Latitude", 0))
                s_lon = float(station.get("Longitude", 0))
            except (ValueError, TypeError):
                continue
            dist = abs(s_lat - lat) + abs(s_lon - lon)
            if dist < best_dist and dist < 2.0:
                best_dist = dist
                best_station = station

        if not best_station:
            return []

        try:
            return [WeatherObservation(
                latitude=float(best_station.get("Latitude", lat)),
                longitude=float(best_station.get("Longitude", lon)),
                valid_time=parse_datetime(best_station.get("DATE")) or utcnow(),
                source_timestamp=utcnow(),
                temperature_c=take_numeric(best_station, "CURR_TEMP", "Temperature"),
                wind_speed_ms=take_numeric(best_station, "WIND_SPEED"),
                wind_direction_deg=take_numeric(best_station, "WIND_DIRECTION"),
                precipitation_mm=None,
                pressure_hpa=take_numeric(best_station, "MSLP"),
                humidity_pct=take_numeric(best_station, "RH"),
                visibility_m=None,
                lightning=None,
                condition=take_string(best_station, "WEATHER_CODE") or None,
                source=self.name,
                source_record_id=best_station.get("ID"),
                quality=QualityStatus.VALID,
                raw_payload=best_station,
            )]
        except Exception:
            return []

    # ---------------------------------------------------------------- forecast
    async def fetch_weather_forecast(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[WeatherForecast]:
        self._ensure_configured("weather_forecast")

        raw_bulletins = await fetch_imd_coastal_bulletin()
        results: List[WeatherForecast] = []

        for bulletin in raw_bulletins:
            try:
                fc = self._parse_coastal_bulletin_as_forecast(bulletin, lat, lon)
                if fc:
                    results.append(fc)
            except Exception as exc:
                logger.debug("imd_fc_parse_skip", error=str(exc))
                continue

        if not results:
            ow = await self._fetch_openweather_forecast(lat, lon)
            if ow:
                results.append(ow)
            else:
                om = await self._fetch_open_meteo_weather(lat, lon)
                if om:
                    fc = om.get("forecast")
                    if fc:
                        results.append(fc)

        return results

    async def _fetch_openweather_forecast(
        self, lat: float, lon: float
    ) -> Optional[WeatherForecast]:
        """Fallback real forecast from OpenWeatherMap (keyed)."""
        from app.datasources.scrapers import fetch_openweather_forecast as _ow_fc

        key = self.settings.openweather_api_key
        if not key or not self.settings.openweather_enabled:
            return None
        data = await _ow_fc(lat, lon, key, self.settings.openweather_units)
        if not data:
            return None
        entries = data.get("entries") or []
        issue_time = _from_ow_ts(data.get("observation_time")) or utcnow()
        return WeatherForecast(
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
            source_record_id=f"openweather-fc-{lat:.2f}-{lon:.2f}",
            quality=QualityStatus.VALID,
            raw_payload={"provider": "openweathermap", **data},
        )

    async def _fetch_open_meteo_weather(
        self, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        """Fallback real weather from Open-Meteo (keyless, global coverage)."""
        from app.datasources.scrapers import fetch_open_meteo_forecast

        data = await fetch_open_meteo_forecast(lat, lon)
        if not data:
            return None

        obs_time = parse_datetime(data.get("observation_time")) or utcnow()

        observation = WeatherObservation(
            latitude=lat,
            longitude=lon,
            valid_time=obs_time,
            source_timestamp=utcnow(),
            temperature_c=data.get("temperature_c"),
            wind_speed_ms=data.get("wind_speed_ms"),
            wind_direction_deg=data.get("wind_direction_deg"),
            precipitation_mm=data.get("precipitation_mm"),
            pressure_hpa=data.get("pressure_hpa"),
            humidity_pct=data.get("humidity_pct"),
            visibility_m=None,
            lightning=None,
            condition=None,
            source=self.name,
            source_record_id=f"openmeteo-{lat:.2f}-{lon:.2f}",
            quality=QualityStatus.VALID,
            raw_payload={"provider": "open-meteo", **data},
        )

        hourly = data.get("hourly_forecast") or []
        forecast = WeatherForecast(
            latitude=lat,
            longitude=lon,
            issue_time=obs_time,
            valid_from=obs_time,
            valid_until=obs_time + timedelta(hours=24),
            forecast_horizon_h=24,
            source_timestamp=utcnow(),
            temperature_c=data.get("temperature_c"),
            temperature_min_c=min((h.get("temperature_c") for h in hourly
                                   if h.get("temperature_c") is not None),
                                  default=None),
            temperature_max_c=max((h.get("temperature_c") for h in hourly
                                   if h.get("temperature_c") is not None),
                                  default=None),
            wind_speed_ms=data.get("wind_speed_ms"),
            wind_direction_deg=data.get("wind_direction_deg"),
            precipitation_mm=data.get("precipitation_mm"),
            pressure_hpa=data.get("pressure_hpa"),
            humidity_pct=data.get("humidity_pct"),
            visibility_m=None,
            lightning=None,
            condition=None,
            source=self.name,
            source_record_id=f"openmeteo-fc-{lat:.2f}-{lon:.2f}",
            quality=QualityStatus.VALID,
            raw_payload={"provider": "open-meteo", **data},
        )

        return {"observation": observation, "forecast": forecast}

    def _parse_coastal_bulletin_as_forecast(
        self, bulletin: dict, lat: float, lon: float
    ) -> Optional[WeatherForecast]:
        """Convert an IMD Coastal Bulletin into a WeatherForecast."""
        issue_time = parse_datetime(bulletin.get("Date of Observation"))
        valid_from = parse_datetime(bulletin.get("Valid From"))
        validity_hours = take_numeric(bulletin, "Validity")

        wind_str = take_string(bulletin, "Wind")
        weather_str = take_string(bulletin, "Weather")
        vis_str = take_string(bulletin, "Visibility")
        sea_str = take_string(bulletin, "Sea Condition")
        update_time = parse_datetime(bulletin.get("Update Time"))

        wind_speed = _wind_knots_to_ms(wind_str)
        wind_dir = _wind_direction_deg(wind_str)
        visibility_m = _parse_visibility(vis_str)
        pressure = take_numeric(bulletin, "MSLP", "Pressure", "slp")
        temp = take_numeric(bulletin, "Temperature", "temperature")

        if valid_from and validity_hours:
            valid_until = valid_from + __import__("datetime").timedelta(hours=float(validity_hours))
        else:
            valid_until = None

        return WeatherForecast(
            latitude=lat,
            longitude=lon,
            issue_time=issue_time or utcnow(),
            valid_from=valid_from or utcnow(),
            valid_until=valid_until,
            forecast_horizon_h=validity_hours,
            source_timestamp=update_time or utcnow(),
            temperature_c=temp,
            temperature_min_c=None,
            temperature_max_c=None,
            wind_speed_ms=wind_speed,
            wind_direction_deg=wind_dir,
            precipitation_mm=None,
            pressure_hpa=pressure,
            humidity_pct=None,
            visibility_m=visibility_m,
            lightning=None,
            condition=weather_str or sea_str or None,
            source=self.name,
            source_record_id=bulletin.get("Id"),
            quality=QualityStatus.VALID,
            raw_payload=bulletin,
        )

    # ---------------------------------------------------------------- warnings
    async def fetch_warnings(
        self, *, lat: float = None, lon: float = None, **kw
    ) -> List[MarineWarning]:
        self._ensure_configured("warnings")

        results: List[MarineWarning] = []

        # 1. Cyclone wind warning (GeoJSON polygons by wind speed category).
        cyclone_wind = await fetch_imd_cyclone_wind()
        if cyclone_wind.get("data"):
            for category, geom in cyclone_wind.get("data", {}).items():
                severity = _cyclone_category_severity(category)
                results.append(MarineWarning(
                    warning_id=f"imd-cyclone-wind-{category}",
                    warning_type=WarningType.CYCLONE,
                    severity=severity,
                    geometry=geom,
                    valid_from=None,
                    valid_until=None,
                    issued_at=utcnow(),
                    updated_at=utcnow(),
                    description=f"Cyclone wind warning: {category} sustained winds",
                    source=self.name,
                    source_record_id=f"imd-cw-{category}",
                    metadata={"category": category, "source": "imd_cyclone_wind"},
                ))

        # 2. Cyclone track (observed + forecast positions).
        cyclone_track = await fetch_imd_cyclone_track()
        if cyclone_track.get("data"):
            track_data = cyclone_track["data"]
            observed = track_data.get("observed", [])
            forecast = track_data.get("forecast", [])
            all_points = observed + forecast
            if all_points:
                name = all_points[0].get("CYCLONE_NAME", "Unknown")
                # Build a LineString from the track points.
                coords = []
                for pt in all_points:
                    try:
                        lat_pt = float(pt.get("lat", 0))
                        lon_pt = float(pt.get("lon", 0))
                        coords.append([lon_pt, lat_pt])
                    except (ValueError, TypeError):
                        continue
                if len(coords) >= 2:
                    geom = {"type": "LineString", "coordinates": coords}
                    results.append(MarineWarning(
                        warning_id=f"imd-cyclone-track-{name}",
                        warning_type=WarningType.CYCLONE,
                        severity=WarningSeverity.HIGH,
                        geometry=geom,
                        valid_from=None,
                        valid_until=None,
                        issued_at=utcnow(),
                        updated_at=utcnow(),
                        description=f"Cyclone track: {name}",
                        source=self.name,
                        source_record_id=f"imd-ct-{name}",
                        metadata={"cyclone_name": name, "point_count": len(all_points)},
                    ))

        # 3. Port warnings (general maritime warnings).
        for port_id in IMD_PORT_IDS[:5]:  # Bound to avoid excessive calls.
            port_warnings = await fetch_imd_port_warning(port_id)
            for pw in port_warnings:
                warning_text = take_string(pw, "Warning")
                if not warning_text or warning_text.upper() == "NIL":
                    continue
                results.append(MarineWarning(
                    warning_id=f"imd-port-{pw.get('Port Id', port_id)}",
                    warning_type=_classify_port_warning(warning_text),
                    severity=WarningSeverity.MODERATE,
                    geometry={},
                    valid_from=parse_datetime(pw.get("Date of Issue")),
                    valid_until=None,
                    issued_at=parse_datetime(pw.get("Date of Issue")),
                    updated_at=utcnow(),
                    description=warning_text,
                    source=self.name,
                    source_record_id=f"imd-pw-{pw.get('Port Id', port_id)}",
                    metadata={"port_name": pw.get("Port Name", ""), "issued_by": pw.get("Issued By", "")},
                ))

        # 4. Sea area bulletin TTT warnings (if any).
        for area in IMD_SEA_AREAS[:5]:
            bulletins = await fetch_imd_sea_bulletin(area["id"])
            for b in bulletins:
                ttt = take_string(b, "TTT Warning")
                if not ttt or ttt.upper() == "NIL":
                    continue
                results.append(MarineWarning(
                    warning_id=f"imd-ttt-{area['id']}",
                    warning_type=WarningType.NAVIGATIONAL_WARNING,
                    severity=WarningSeverity.MODERATE,
                    geometry={},
                    valid_from=parse_datetime(b.get("Valid From")),
                    valid_until=None,
                    issued_at=parse_datetime(b.get("Update Time")),
                    updated_at=utcnow(),
                    description=f"Sea area {area['name']}: {ttt}",
                    source=self.name,
                    source_record_id=f"imd-ttt-{area['id']}",
                    metadata={"sea_area": area["name"]},
                ))

        return results

    # ---------------------------------------------------------------- helpers
    def _nearest_sea_area(self, lat: float, lon: float) -> str:
        """Return the IMD sea area ID closest to the given coordinates."""
        # Very rough mapping based on known IMD sea area locations.
        areas = {
            "101": (20.0, 67.0),   # North Arabian Sea
            "102": (15.0, 68.0),   # Central Arabian Sea
            "103": (8.0, 70.0),    # South Arabian Sea
            "104": (18.0, 88.0),   # North Bay of Bengal
            "105": (14.0, 88.0),   # Central Bay of Bengal
            "106": (8.0, 88.0),    # South Bay of Bengal
            "107": (10.0, 72.0),   # Lakshadweep
            "108": (5.0, 73.0),    # Maldives
            "109": (8.0, 77.0),    # Comorin
            "110": (12.0, 95.0),   # Andaman Sea
        }
        best_id = "101"
        best_dist = float("inf")
        for area_id, (a_lat, a_lon) in areas.items():
            dist = abs(lat - a_lat) + abs(lon - a_lon)
            if dist < best_dist:
                best_dist = dist
                best_id = area_id
        return best_id


def _parse_visibility(vis_str: str) -> Optional[float]:
    """Parse visibility string like 'Good Becoming Moderate' to meters."""
    if not vis_str:
        return None
    lower = vis_str.lower()
    if "good" in lower:
        return 10000.0
    if "moderate" in lower:
        return 5000.0
    if "poor" in lower:
        return 2000.0
    if "very poor" in lower:
        return 1000.0
    if "fog" in lower:
        return 500.0
    return None


def _cyclone_category_severity(category: str) -> WarningSeverity:
    """Map IMD cyclone wind category to severity."""
    lower = category.lower().replace("kt", "").strip()
    try:
        knots = int(lower)
    except ValueError:
        return WarningSeverity.MODERATE
    if knots >= 64:
        return WarningSeverity.CRITICAL
    if knots >= 48:
        return WarningSeverity.HIGH
    if knots >= 34:
        return WarningSeverity.MODERATE
    return WarningSeverity.LOW


def _classify_port_warning(text: str) -> WarningType:
    """Classify port warning type from text."""
    lower = text.lower()
    if "cyclone" in lower:
        return WarningType.CYCLONE
    if "storm" in lower:
        return WarningType.STORM_WARNING
    if "fishing" in lower:
        return WarningType.FISHING_WARNING
    return WarningType.NAVIGATIONAL_WARNING


def _from_ow_ts(value) -> Optional[datetime]:
    """Convert a unix epoch timestamp (seconds) to an aware UTC datetime."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None
