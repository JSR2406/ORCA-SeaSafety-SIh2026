# GDACS (Global Disaster Alert and Coordination System) adapter - cyclone
# warnings.
#
# Keyless public framework feed (EU, CC BY 4.0): the RSS each active tropical
# cyclone carries the centre point, affected-area bbox, validity window and
# severity.  Used as the reliable keyless warnings source when official JTWC
# bulletins are unreachable (their products section 403s some networks -
# the RSS still enumerates storms, but geometry/bulletins are not available).
#
# Geometry is the affected-area bbox turned into a polygon; severity is
# derived from alert level first, wind speed second.  Never fabricates data -
# empty results on failure.
from datetime import timedelta
import logging
from typing import Dict, List, Optional

from shapely.geometry import box, mapping

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.http import HttpDataTransport
from app.datasources.scrapers import fetch_gdacs_cyclone_warnings
from app.models.common import QualityStatus, utcnow
from app.models.source import SourceCapability, SourceType
from app.models.warnings import (
    MarineWarning,
    WarningSeverity,
    WarningType,
)

logger = logging.getLogger(__name__)


class GDACSAdapter(BaseMarineDataSource):
    name = "gdacs"
    display_name = "GDACS Cyclone Warnings"
    source_type = SourceType.GDACS

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "warnings": "https://www.gdacs.org/xml/rss.xml",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.gdacs_base_url

    @property
    def api_key(self) -> Optional[str]:
        return None

    @property
    def enabled(self) -> bool:
        return self.settings.gdacs_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="cyclone_warnings",
                description="Active tropical cyclone alerts with affected-area "
                            "geometry from the keyless GDACS public feed",
                data_product="warnings",
            ),
        ]

    async def fetch_warnings(
        self, *, lat: float = None, lon: float = None, **kw
    ) -> List[MarineWarning]:
        self._ensure_configured("warnings")
        events = await fetch_gdacs_cyclone_warnings()
        if not events:
            return []

        warnings: List[MarineWarning] = []
        now = utcnow()
        for event in events:
            geometry = _event_geometry(event)
            if not geometry:
                continue
            issued_at = event.get("issued_at")
            valid_from = _parse_dt(issued_at) or now
            valid_until = _parse_dt(event.get("valid_until"))
            if valid_until is None:
                valid_until = valid_from + timedelta(hours=12)
            # Help a narrow GDACS feed: their todate can lag a few hours behind
            # the advisory end.  Keep recently-ended events (48h grace) so an
            # ongoing storm isn't dropped until well after it really ended.
            if valid_until < (now - timedelta(hours=48)):
                continue
            warnings.append(MarineWarning(
                warning_id=event.get("warning_id")
                          or f"gdacs-{event.get('eventid', '')}",
                warning_type=WarningType.CYCLONE,
                severity=_severity(event),
                geometry=geometry,
                valid_from=valid_from,
                valid_until=valid_until,
                issued_at=issued_at,
                updated_at=now,
                description=_describe(event),
                source=self.name,
                source_record_id=event.get("warning_id")
                          or f"gdacs-{event.get('eventid', 'unknown')}",
                metadata={
                    "storm_name": event.get("storm_name"),
                    "alertlevel": event.get("alertlevel"),
                    "max_wind_kmh": event.get("severity_kmh"),
                    "center": event.get("center"),
                    "bbox": event.get("bbox"),
                    "link": event.get("link"),
                    "estimate": True,
                },
                quality=QualityStatus.VALID,
                raw_payload=dict(event),
            ))
        return warnings


# ----------------------------------------------------------------- helpers
def _event_geometry(event) -> Optional[Dict]:
    """Affected-area bbox turned into a polygon (never stitched shut by guess)."""
    bbox = event.get("bbox")
    if not bbox:
        return None
    try:
        min_lon, max_lon, min_lat, max_lat = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if not (-180.0 <= min_lon <= max_lon <= 180.0) \
            or not (-90.0 <= min_lat <= max_lat <= 90.0):
        return None
    area = box(min_lon, min_lat, max_lon, max_lat)
    if area.area < 0.0001:
        area = area.buffer(0.1)
    geom = mapping(area)
    if geom.get("type") in ("Polygon", "MultiPolygon"):
        return geom
    return None


def _severity(event) -> WarningSeverity:
    level = (event.get("alertlevel") or "").strip().lower()
    level_map = {
        "red": WarningSeverity.CRITICAL,
        "orange": WarningSeverity.HIGH,
        "yellow": WarningSeverity.MODERATE,
        "green": WarningSeverity.LOW,
    }
    if level in level_map:
        return level_map[level]
    # Fall back to wind speed: severity value is max wind in km/h.
    try:
        max_wind_kmh = float(event.get("severity_kmh"))
    except (TypeError, ValueError):
        return WarningSeverity.MODERATE
    max_wind_kt = max_wind_kmh * 0.5399568
    if max_wind_kt >= 130:
        return WarningSeverity.CRITICAL
    if max_wind_kt >= 64:
        return WarningSeverity.HIGH
    if max_wind_kt >= 34:
        return WarningSeverity.MODERATE
    return WarningSeverity.LOW


def _describe(event) -> str:
    name = event.get("storm_name") or "tropical cyclone"
    parts = [f"{name} active tropical cyclone alert"]
    level = event.get("alertlevel")
    if level:
        parts.append(f"GDACS alert level {level}")
    if event.get("severity_kmh"):
        parts.append(f"max winds {event['severity_kmh']} km/h")
    return ", ".join(parts) + "."


def _parse_dt(value):
    from app.datasources.normalize import parse_datetime
    return parse_datetime(value)