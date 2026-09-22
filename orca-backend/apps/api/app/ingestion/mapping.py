# Map canonical models onto DB row dicts (idempotent-friendly shapes).
from datetime import datetime, timezone
from typing import Any, Dict, List

from shapely.geometry import Point
from geoalchemy2.shape import from_shape

from app.config import Settings
from app.geo_utils import geojson_to_wkb, normalize_multipolygon
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.tides import TidePrediction
from app.models.weather import WeatherForecast, WeatherObservation
from app.models.warnings import MarineWarning, RestrictedArea


def _point_wkb(lon: float, lat: float, srid: int):
    return from_shape(Point(float(lon), float(lat)), srid=srid)


def ocean_to_row(o: OceanConditions, settings: Settings) -> Dict[str, Any]:
    return {
        "source": o.source,
        "source_record_id": o.source_record_id,
        "latitude": o.latitude,
        "longitude": o.longitude,
        "geom": _point_wkb(o.longitude, o.latitude, settings.geom_srid),
        "observation_time": o.observation_time,
        "source_timestamp": o.source_timestamp,
        "ingested_at": o.ingested_at or datetime.now(timezone.utc),
        "sst_c": o.sst_c, "chlorophyll": o.chlorophyll,
        "wave_height_m": o.wave_height_m, "wave_period_s": o.wave_period_s,
        "wave_direction_deg": o.wave_direction_deg,
        "current_speed_ms": o.current_speed_ms,
        "current_direction_deg": o.current_direction_deg,
        "salinity_psu": o.salinity_psu,
        "quality": o.quality.value if hasattr(o.quality, "value") else o.quality,
        "raw_payload": o.raw_payload,
    }


def weather_observation_to_row(o: WeatherObservation, settings: Settings) -> Dict[str, Any]:
    return {
        "source": o.source,
        "source_record_id": o.source_record_id,
        "latitude": o.latitude,
        "longitude": o.longitude,
        "geom": _point_wkb(o.longitude, o.latitude, settings.geom_srid),
        "valid_time": o.valid_time,
        "source_timestamp": o.source_timestamp,
        "ingested_at": o.ingested_at or datetime.now(timezone.utc),
        "temperature_c": o.temperature_c, "wind_speed_ms": o.wind_speed_ms,
        "wind_direction_deg": o.wind_direction_deg, "precipitation_mm": o.precipitation_mm, "pressure_hpa": o.pressure_hpa,
        "humidity_pct": o.humidity_pct, "visibility_m": o.visibility_m, "lightning": o.lightning, "condition": o.condition,
        "quality": o.quality.value if hasattr(o.quality, "value") else o.quality,
        "raw_payload": o.raw_payload,
    }


def weather_forecast_to_row(f: WeatherForecast, settings: Settings) -> Dict[str, Any]:
    return {
        "source": f.source,
        "source_record_id": f.source_record_id,
        "latitude": f.latitude,
        "longitude": f.longitude,
        "geom": _point_wkb(f.longitude, f.latitude, settings.geom_srid),
        "issue_time": f.issue_time, "valid_from": f.valid_from, "valid_until": f.valid_until,
        "forecast_horizon_h": f.forecast_horizon_h,
        "source_timestamp": f.source_timestamp,
        "ingested_at": f.ingested_at or datetime.now(timezone.utc),
        "temperature_c": f.temperature_c, "temperature_min_c": f.temperature_min_c,
        "temperature_max_c": f.temperature_max_c, "wind_speed_ms": f.wind_speed_ms,
        "wind_direction_deg": f.wind_direction_deg, "precipitation_mm": f.precipitation_mm,
        "pressure_hpa": f.pressure_hpa, "humidity_pct": f.humidity_pct,
        "visibility_m": f.visibility_m, "lightning": f.lightning, "condition": f.condition,
        "quality": f.quality.value if hasattr(f.quality, "value") else f.quality,
        "raw_payload": f.raw_payload,
    }


def tide_to_row(t: TidePrediction, settings: Settings) -> Dict[str, Any]:
    return {
        "source": t.source,
        "source_record_id": t.source_record_id,
        "location_name": t.location_name,
        "latitude": t.latitude,
        "longitude": t.longitude,
        "geom": _point_wkb(t.longitude, t.latitude, settings.geom_srid),
        "event_time": t.event_time,
        "tide_height_m": t.tide_height_m,
        "tide_type": t.tide_type.value if hasattr(t.tide_type, "value") else t.tide_type,
        "is_prediction": t.is_prediction,
        "source_timestamp": t.source_timestamp,
        "ingested_at": t.ingested_at or datetime.now(timezone.utc),
        "quality": t.quality.value if hasattr(t.quality, "value") else t.quality,
        "raw_payload": t.raw_payload,
    }


def pfz_to_row(z: PFZZone, settings: Settings) -> Dict[str, Any]:
    return {
        "source": z.source,
        "source_record_id": z.source_record_id,
        "geometry": geojson_to_wkb(normalize_multipolygon(z.geometry), srid=settings.geom_srid),
        "centroid_longitude": z.centroid.longitude,
        "centroid_latitude": z.centroid.latitude,
        "generated_at": z.generated_at,
        "valid_from": z.valid_from,
        "valid_until": z.valid_until,
        "species": z.species,
        "confidence": z.confidence,
        "metadata_json": z.metadata,
        "source_timestamp": z.source_timestamp,
        "ingested_at": z.ingested_at or datetime.now(timezone.utc),
        "quality": z.quality.value if hasattr(z.quality, "value") else z.quality,
        "raw_payload": z.raw_payload,
    }


def warning_to_row(w: MarineWarning, settings: Settings) -> Dict[str, Any]:
    return {
        "source": w.source,
        "source_record_id": w.source_record_id,
        "warning_id": w.warning_id,
        "warning_type": w.warning_type.value if hasattr(w.warning_type, "value") else w.warning_type,
        "severity": w.severity.value if hasattr(w.severity, "value") else w.severity,
        "geometry": geojson_to_wkb(normalize_multipolygon(w.geometry), srid=settings.geom_srid),
        "valid_from": w.valid_from,
        "valid_until": w.valid_until,
        "issued_at": w.issued_at,
        "updated_at": w.updated_at,
        "description": w.description,
        "metadata_json": w.metadata,
        "ingested_at": w.ingested_at or datetime.now(timezone.utc),
    }


def restricted_area_to_row(r: RestrictedArea, settings: Settings) -> Dict[str, Any]:
    return {
        "source": r.source,
        "source_record_id": r.source_record_id,
        "area_id": r.area_id,
        "area_name": r.area_name,
        "restriction_kind": r.restriction_kind.value if hasattr(r.restriction_kind, "value") else r.restriction_kind,
        "restriction_type": r.restriction_type.value if hasattr(r.restriction_type, "value") else r.restriction_type,
        "severity": r.severity.value if hasattr(r.severity, "value") else r.severity,
        "geometry": geojson_to_wkb(normalize_multipolygon(r.geometry), srid=settings.geom_srid),
        "valid_from": r.valid_from,
        "valid_until": r.valid_until,
        "description": r.description,
        "metadata_json": r.metadata,
        "ingested_at": r.ingested_at or datetime.now(timezone.utc),
    }


PRODUCT_MAPPERS = {
    "ocean": ocean_to_row,
    "weather_observation": weather_observation_to_row,
    "weather_forecast": weather_forecast_to_row,
    "tides": tide_to_row,
    "pfz": pfz_to_row,
    "warnings": warning_to_row,
    "restricted_areas": restricted_area_to_row,
}


def map_records(product: str, records: List[Any], settings: Settings) -> List[Dict[str, Any]]:
    mapper = PRODUCT_MAPPERS[product]
    return [mapper(r, settings) for r in records]