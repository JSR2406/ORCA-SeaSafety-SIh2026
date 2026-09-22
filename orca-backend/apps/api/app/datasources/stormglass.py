# Storm Glass adapter - global tide extremes (high/low + height).
#
# Keyed API (https://api.stormglass.io/v2, free tier = 10 req/day).
# One request returns a multi-day tides window at a point, so the scheduler
# seeds a small set of coastal anchors on a daily cadence and the read side
# snaps arbitrary queries to the nearest stored point.
#
# Auth: Storm Glass uses a bare `Authorization: <key>` header (no "Bearer").
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceInvalidDataError
from app.datasources.http import HttpDataTransport
from app.datasources.normalize import ensure_list, parse_datetime
from app.models.common import QualityStatus, utcnow
from app.models.source import SourceCapability, SourceType
from app.models.tides import TidePrediction, TideType

logger = logging.getLogger(__name__)

_TIDE_EXTREMES_PATH = "/tide/extremes/point"
_MAX_WINDOW_DAYS = 30


class StormGlassAdapter(BaseMarineDataSource):
    name = "stormglass"
    display_name = "Storm Glass Tides"
    source_type = SourceType.STORM_GLASS

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "tides": _TIDE_EXTREMES_PATH,
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.stormglass_base_url

    @property
    def api_key(self) -> Optional[str]:
        return self.settings.stormglass_api_key or None

    @property
    def enabled(self) -> bool:
        return self.settings.stormglass_enabled

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key)

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="tide_extremes",
                description="Global tide high/low extremes with height, "
                            "multi-day prediction window",
                data_product="tides",
                config_required=True,
            ),
        ]

    # Storm Glass wants the raw key as the Authorization header value.
    def _auth_headers(self) -> Optional[Dict[str, str]]:
        if self.api_key:
            return {"Authorization": self.api_key}
        return None

    async def fetch_tides(
        self, *, lat: float, lon: float,
        start=None, end=None, **kw,
    ) -> List[TidePrediction]:
        self._ensure_configured("tides")

        now = datetime.now(timezone.utc)
        start_dt = parse_datetime(start) or (now - timedelta(days=1))
        end_dt = parse_datetime(end)
        if end_dt is None:
            days = int(kw.get("days") or 7)
            days = max(1, min(days, _MAX_WINDOW_DAYS))
            end_dt = start_dt + timedelta(days=days)

        payload = await self._fetch_json(
            self._endpoint("tides"),
            params={
                "lat": str(lat),
                "lng": str(lon),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            },
        )

        items = ensure_list(payload)
        predictions: List[TidePrediction] = []
        for item in items:
            event_time = parse_datetime(item.get("time"))
            if event_time is None:
                continue
            raw_type = str(item.get("type") or "").lower()
            try:
                tide_type = TideType(raw_type)
            except ValueError:
                tide_type = TideType.HIGH if raw_type == "high" else TideType.LOW
            height = _as_float(item.get("height"))
            try:
                predictions.append(TidePrediction(
                    location_name=None,
                    latitude=lat,
                    longitude=lon,
                    event_time=event_time,
                    tide_height_m=height,
                    tide_type=tide_type,
                    is_prediction=True,
                    source_timestamp=utcnow(),
                    source=self.name,
                    source_record_id=_record_id(lat, lon, event_time, tide_type),
                    quality=QualityStatus.VALID,
                    raw_payload=dict(item),
                ))
            except Exception as exc:
                raise SourceInvalidDataError(
                    f"invalid storm glass tide item: {exc}") from exc

        return predictions


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _record_id(lat: float, lon: float, event_time: datetime,
               tide_type: TideType) -> str:
    return (
        f"sg-{lat:.4f}-{lon:.4f}-"
        f"{event_time:%Y%m%dT%H%M%S}-{tide_type.value}"
    )