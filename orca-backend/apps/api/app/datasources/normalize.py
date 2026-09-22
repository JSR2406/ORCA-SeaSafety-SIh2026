# Shared normalization helpers used by source adapters to map raw upstream
# payloads onto canonical models.
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.datasources.errors import SourceInvalidDataError
from app.models.common import utcnow


def coerce_utc(value: datetime) -> datetime:
    """Ensure a datetime is timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_datetime(value: Any, default: Optional[datetime] = None) -> Optional[datetime]:
    """Parse ISO-8601 (or common variants) into tz-aware UTC; None on failure."""
    if not value:
        return default
    if isinstance(value, datetime):
        return coerce_utc(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not isinstance(value, str):
        return default
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return coerce_utc(parsed)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return default


def take_numeric(raw: Dict, *keys, scale: float = 1.0) -> Optional[float]:
    """First non-None numeric value among candidate keys (with optional scaling)."""
    for key in keys:
        val = raw.get(key)
        if isinstance(val, str):
            val = val.strip().replace(" ", "")
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if scale != 1.0:
            num = num * scale
        return num
    return None


def take_bool(raw: Dict, *keys) -> Optional[bool]:
    for key in keys:
        val = raw.get(key)
        if val is None:
            continue
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            lowered = val.strip().lower()
            if lowered in ("1", "true", "yes", "y"):
                return True
            if lowered in ("0", "false", "no", "n"):
                return False
    return None


def take_string(raw: Dict, *keys, default: str = "") -> str:
    for key in keys:
        val = raw.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def take_coordinates(raw: Dict) -> Tuple[float, float]:
    """Best-effort (lat, lon) extraction from various payload shapes."""
    for key in ("latitude", "lat"):
        val = raw.get(key)
        try:
            return float(val), float(raw.get("longitude", raw.get("lon")))
        except (TypeError, ValueError):
            pass
    loc = raw.get("location") or raw.get("position") or raw.get("point")
    if isinstance(loc, dict):
        lat = loc.get("latitude", loc.get("lat"))
        lon = loc.get("longitude", loc.get("lon"))
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass
    if isinstance(loc, (list, tuple)) and len(loc) == 2:
        # tolerate [lat, lon] and [lon, lat] by range
        try:
            a, b = float(loc[0]), float(loc[1])
        except (TypeError, ValueError):
            pass
        else:
            if -90 <= a <= 90 and not -90 <= b <= 90:
                return a, b
            return b, a
    raise SourceInvalidDataError(
        f"cannot extract coordinates from payload keys: {list(raw.keys())}"
    )


def ensure_list(payload: Any) -> List[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # tolerate {"data": [...]} or {"records": {...}, "features": [...]}
        for key in ("data", "records", "features", "values", "items"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                return [inner]
        return [payload]
    return [payload]


def now_utc() -> datetime:
    return utcnow()