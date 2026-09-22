# JTWC (Joint Typhoon Warning Center) adapter - cyclone warnings.
#
# Keyless public feed on metoc.navy.mil:
#   RSS (jtwc/rss/jtwc.rss) lists active tropical systems; each item's
#   description carries the storm names + bulletin links, and each bulletin
#   carries the current + forecast track positions and max wind.
#
# Geometry is a conservative convex hull of the current + forecast track
# positions, buffered to reflect the cyclone wind field; severity is derived
# from max sustained wind.  Never fabricates data - empty results on failure.
from datetime import timedelta
import logging
from typing import Dict, List, Optional

from shapely.geometry import MultiPoint, Point, mapping

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.http import HttpDataTransport
from app.datasources.scrapers import fetch_jtwc_cyclone_warnings
from app.models.common import QualityStatus, utcnow
from app.models.source import SourceCapability, SourceType
from app.models.warnings import (
    MarineWarning,
    WarningSeverity,
    WarningType,
)

logger = logging.getLogger(__name__)

_WARNING_VALIDITY_HOURS = 6
_MIN_GEOMETRY_POINTS = 2


class JTWCAdapter(BaseMarineDataSource):
    name = "jtwc"
    display_name = "JTWC Cyclone Warnings"
    source_type = SourceType.JTWC

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "warnings": "/jtwc/rss/jtwc.rss",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.jtwc_base_url

    @property
    def api_key(self) -> Optional[str]:
        return None

    @property
    def enabled(self) -> bool:
        return self.settings.jtwc_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="cyclone_warnings",
                description="Active tropical cyclone warnings (track + wind) "
                            "from the keyless JTWC public feed",
                data_product="warnings",
            ),
        ]

    async def fetch_warnings(
        self, *, lat: float = None, lon: float = None, **kw
    ) -> List[MarineWarning]:
        self._ensure_configured("warnings")
        storms = await fetch_jtwc_cyclone_warnings(self.base_url)
        if not storms:
            return []

        warnings: List[MarineWarning] = []
        for storm in storms:
            positions = storm.get("positions") or []
            if len(positions) < _MIN_GEOMETRY_POINTS:
                continue
            geometry = _storm_geometry(positions)
            if not geometry:
                continue
            max_wind_kt = storm.get("max_wind_kt")
            issued_at = storm.get("issued_at")
            valid_from = _parse_dt(issued_at) or utcnow()
            warnings.append(MarineWarning(
                warning_id=storm.get("warning_id") or f"jtwc-{storm.get('storm_name', '')}",
                warning_type=WarningType.CYCLONE,
                severity=_severity(max_wind_kt),
                geometry=geometry,
                valid_from=valid_from,
                valid_until=valid_from + timedelta(hours=_WARNING_VALIDITY_HOURS),
                issued_at=issued_at,
                updated_at=utcnow(),
                description=_describe(storm),
                source=self.name,
                source_record_id=(storm.get("warning_id")
                                  or f"jtwc-{storm.get('storm_name', 'unknown')}"),
                metadata={
                    "storm_name": storm.get("storm_name"),
                    "basin": storm.get("basin"),
                    "kind": storm.get("kind"),
                    "warning_number": storm.get("warning_number"),
                    "max_wind_kt": max_wind_kt,
                    "pressure_mb": storm.get("pressure_mb"),
                    "bulletin_url": storm.get("bulletin_url"),
                    "position_count": len(positions),
                    "estimate": True,
                },
                quality=QualityStatus.VALID,
                raw_payload=dict(storm),
            ))
        return warnings


# ----------------------------------------------------------------- helpers
def _storm_geometry(positions) -> Optional[Dict]:
    """Convex hull of current+forecast positions, buffered by the storm size."""
    if not positions:
        return None
    pts = MultiPoint([(float(p["lon"]), float(p["lat"])) for p in positions])
    hull = pts.convex_hull
    if hull.geom_type in ("Point", "LineString") or hull.is_empty:
        # None of the positions form an area yet - expand current position
        # by a fixed guard radius so a young storm still rings a warning area.
        anchor = pts.geoms[0] if hull.is_empty else hull.representative_point()
        hull = Point(anchor).buffer(0.9)
    if hull.area < 0.01:
        hull = hull.buffer(0.9)
    geom = mapping(hull)
    if geom.get("type") in ("Polygon", "MultiPolygon"):
        return geom
    return None


def _severity(max_wind_kt) -> WarningSeverity:
    if max_wind_kt is None:
        return WarningSeverity.MODERATE
    if max_wind_kt >= 130:
        return WarningSeverity.CRITICAL
    if max_wind_kt >= 64:
        return WarningSeverity.HIGH
    if max_wind_kt >= 34:
        return WarningSeverity.MODERATE
    return WarningSeverity.LOW


def _describe(storm) -> str:
    name = storm.get("storm_name") or "tropical cyclone"
    parts = [f"{name} active cyclone warning"]
    if storm.get("max_wind_kt"):
        parts.append(f"max winds {storm['max_wind_kt']} kt")
    if storm.get("pressure_mb"):
        parts.append(f"central pressure {storm['pressure_mb']} mb")
    return ", ".join(parts) + "."


def _parse_dt(value):
    from app.datasources.normalize import parse_datetime
    return parse_datetime(value)