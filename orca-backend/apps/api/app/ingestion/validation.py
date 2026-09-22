# Quality validation for canonical marine records.
# Classifies records and individual fields as VALID / SUSPICIOUS / INVALID /
# MISSING using configurable physical plausibility bounds.
from typing import List, Optional, Tuple

from datetime import date, datetime

import structlog

from app.config import Settings
from app.models.common import QualityReport, QualityStatus
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.tides import TidePrediction
from app.models.weather import WeatherForecast, WeatherObservation

logger = structlog.get_logger(__name__)

MISSING = QualityStatus.MISSING
INVALID = QualityStatus.INVALID
SUSPICIOUS = QualityStatus.SUSPICIOUS
VALID = QualityStatus.VALID


class MarineValidationService:
    """Deterministic, bounds-driven quality classification."""

    def __init__(self, settings: Settings):
        self.settings = settings

    # ------------------------------------------------------------------ helpers
    def _num(self, value, field: str, lo: Optional[float] = None,
             hi: Optional[float] = None, missing_ok: bool = True) -> QualityReport:
        if value is None:
            return QualityReport(field=field, status=MISSING if missing_ok else INVALID,
                                 reason="field missing")
        # Temporal fields are presence-checked, not numerically bounded.
        if isinstance(value, (datetime, date)):
            return QualityReport(field=field, status=VALID, reason=None)
        try:
            num = float(value)
        except (TypeError, ValueError):
            return QualityReport(field=field, status=INVALID, reason="not numeric")
        if lo is not None and num < lo:
            return QualityReport(field=field, status=INVALID if hi is not None else SUSPICIOUS,
                                 reason=f"below plausible bound ({lo})")
        if hi is not None and num > hi:
            return QualityReport(field=field, status=INVALID if lo is not None else SUSPICIOUS,
                                 reason=f"above plausible bound ({hi})")
        return QualityReport(field=field, status=VALID, reason=None)

    def _coords(self, lat: float, lon: float) -> Tuple[QualityReport, QualityReport]:
        lat_r = self._num(lat, "latitude", -90.0, 90.0, missing_ok=False)
        lon_r = self._num(lon, "longitude", -180.0, 180.0, missing_ok=False)
        return lat_r, lon_r

    @staticmethod
    def _report(checks: List[QualityReport]) -> Tuple[QualityStatus, List[str]]:
        reasons = [c.reason for c in checks if c.reason]
        if any(c.status == INVALID for c in checks):
            return INVALID, reasons
        if any(c.status == SUSPICIOUS for c in checks):
            return SUSPICIOUS, reasons
        return VALID, []

    @staticmethod
    def _missing(checks: List[QualityReport]) -> int:
        return sum(1 for c in checks if c.status == MISSING)

    # ------------------------------------------------------------------ record
    def classify_ocean(self, record: OceanConditions) -> Tuple[QualityStatus, List[str]]:
        checks: List[QualityReport] = []
        lat_r, lon_r = self._coords(record.latitude, record.longitude)
        checks += [lat_r, lon_r]
        checks.append(self._num(record.observation_time, "observation_time", missing_ok=False))
        checks.append(self._num(record.sst_c, "sst_c", self.settings.sst_min_c, self.settings.sst_max_c))
        checks.append(self._num(record.wave_height_m, "wave_height_m", 0.0, self.settings.wave_max_m))
        checks.append(self._num(record.current_speed_ms, "current_speed_ms", 0.0, self.settings.current_max_ms))
        checks.append(self._num(record.wave_direction_deg, "wave_direction_deg", 0.0, 360.0))
        return self._report(checks)

    def classify_weather_observation(self, record: WeatherObservation) -> Tuple[QualityStatus, List[str]]:
        checks: List[QualityReport] = []
        lat_r, lon_r = self._coords(record.latitude, record.longitude)
        checks += [lat_r, lon_r]
        checks.append(self._num(record.valid_time, "valid_time", missing_ok=False))
        checks.append(self._num(record.temperature_c, "temperature_c", -60.0, 55.0))
        checks.append(self._num(record.wind_speed_ms, "wind_speed_ms", 0.0, self.settings.wind_max_ms))
        checks.append(self._num(record.wind_direction_deg, "wind_direction_deg", 0.0, 360.0))
        checks.append(self._num(record.pressure_hpa, "pressure_hpa", 850.0, 1085.0))
        checks.append(self._num(record.humidity_pct, "humidity_pct", 0.0, 100.0))
        return self._report(checks)

    def classify_weather_forecast(self, record: WeatherForecast) -> Tuple[QualityStatus, List[str]]:
        checks: List[QualityReport] = []
        lat_r, lon_r = self._coords(record.latitude, record.longitude)
        checks += [lat_r, lon_r]
        checks.append(self._num(record.valid_from, "valid_from", missing_ok=False))
        checks.append(self._num(record.valid_until, "valid_until", missing_ok=False))
        checks.append(self._num(record.temperature_c, "temperature_c", -60.0, 55.0))
        checks.append(self._num(record.wind_speed_ms, "wind_speed_ms", 0.0, self.settings.wind_max_ms))
        checks.append(self._num(record.pressure_hpa, "pressure_hpa", 850.0, 1085.0))
        checks.append(self._num(record.humidity_pct, "humidity_pct", 0.0, 100.0))
        return self._report(checks)

    def classify_tide(self, record: TidePrediction) -> Tuple[QualityStatus, List[str]]:
        checks: List[QualityReport] = []
        lat_r, lon_r = self._coords(record.latitude, record.longitude)
        checks += [lat_r, lon_r]
        checks.append(self._num(record.event_time, "event_time", missing_ok=False))
        # Wide range: extreme-range ports (e.g. Gulf of Khambhat, Bay of Fundy)
        # exceed the +/-2 m open-marine envelope at low/high water.
        checks.append(self._num(record.tide_height_m, "tide_height_m", -12.0, 25.0))
        return self._report(checks)

    def classify_pfz(self, record: PFZZone) -> Tuple[QualityStatus, List[str]]:
        checks: List[QualityReport] = []
        lat_r, lon_r = self._coords(record.centroid.latitude, record.centroid.longitude)
        checks += [lat_r, lon_r]
        checks.append(self._num(record.confidence, "confidence", 0.0, 1.0))
        if not record.geometry or record.geometry.get("type") not in ("Polygon", "MultiPolygon"):
            checks.append(QualityReport(field="geometry", status=INVALID, reason="not a polygon"))
        return self._report(checks)

    def classify_warning(self, record) -> Tuple[QualityStatus, List[str]]:
        from app.models.warnings import MarineWarning
        checks: List[QualityReport] = []
        if not record.warning_id:
            checks.append(QualityReport(field="warning_id", status=INVALID, reason="missing id"))
        if not record.geometry or record.geometry.get("type") not in ("Polygon", "MultiPolygon"):
            checks.append(QualityReport(field="geometry", status=INVALID, reason="not a polygon"))
        return self._report(checks)

    def validate_geometry(self, geojson: dict) -> QualityStatus:
        try:
            from app.geo_utils import geojson_to_shape
            geom = geojson_to_shape(geojson)
            if not geom.is_valid:
                return QualityStatus.INVALID
            return QualityStatus.VALID
        except Exception:
            return QualityStatus.INVALID