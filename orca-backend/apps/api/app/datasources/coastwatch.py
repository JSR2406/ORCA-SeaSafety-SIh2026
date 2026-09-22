# NOAA CoastWatch adapter - keyless near-real-time satellite products.
#
# ERDDAP griddap endpoints (coastwatch.pfeg.noaa.gov/erddap):
#   - ocean  -> MUR SST + VIIRS chlorophyll at a point
#   - pfz    -> thermal-front PFZ derived from a small SST sample grid
#
# PFZ here is a satellite-derived *estimate* (flagged in metadata), never
# presented as the official INCOIS advisory.  No fabricated data ever.
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional

from app.config import Settings
from app.datasources.base import BaseMarineDataSource
from app.datasources.errors import SourceInvalidDataError
from app.datasources.http import HttpDataTransport
from app.datasources.scrapers import (
    derive_pfz_fronts_from_grid,
    fetch_coastwatch_chlorophyll_point,
    fetch_coastwatch_sst_front_grid,
    fetch_coastwatch_sst_point,
)
from app.models.common import GeographicPoint, QualityStatus, utcnow
from app.models.ocean import OceanConditions
from app.models.pfz import PFZZone
from app.models.source import SourceCapability, SourceType

logger = logging.getLogger(__name__)


class CoastWatchAdapter(BaseMarineDataSource):
    name = "coastwatch"
    display_name = "NOAA CoastWatch"
    source_type = SourceType.COASTWATCH

    PRODUCT_ENDPOINTS: Dict[str, str] = {
        "ocean": "/griddap",
        "pfz": "/griddap",
    }

    def __init__(self, settings: Settings, transport: Optional[HttpDataTransport] = None):
        super().__init__(settings, transport)

    @property
    def base_url(self) -> str:
        return self.settings.coastwatch_erddap_url

    @property
    def api_key(self) -> Optional[str]:
        return None

    @property
    def enabled(self) -> bool:
        return self.settings.coastwatch_enabled

    @property
    def capabilities(self) -> List[SourceCapability]:
        return [
            SourceCapability(
                name="sea_surface_temperature",
                description="Near-real-time MUR GHz SST at the point",
                data_product="ocean",
            ),
            SourceCapability(
                name="chlorophyll",
                description="Near-real-time VIIRS chlorophyll concentration",
                data_product="ocean",
            ),
            SourceCapability(
                name="pfz_fronts",
                description="Derived potential fishing zones from SST fronts "
                            "(estimated, not official advisory)",
                data_product="pfz",
            ),
        ]

    async def fetch_ocean(
        self, *, lat: float, lon: float, time=None, **kw
    ) -> List[OceanConditions]:
        self._ensure_configured("ocean")
        # Ask the scrapers for the configured datasets.
        dataset = kw.get("sst_dataset") or self.settings.coastwatch_mur_sst_dataset
        chl_dataset = kw.get("chl_dataset") or self.settings.coastwatch_chl_dataset
        sst_row = await fetch_coastwatch_sst_point(lat, lon, dataset=dataset)
        chl_row = await fetch_coastwatch_chlorophyll_point(lat, lon, dataset=chl_dataset)
        if not sst_row and not chl_row:
            return []
        observed = (
            _parse_dt(sst_row["time"] if sst_row else None)
            or _parse_dt(chl_row["time"] if chl_row else None)
            or (time or utcnow())
        )
        try:
            return [OceanConditions(
                latitude=lat,
                longitude=lon,
                observation_time=observed,
                source_timestamp=utcnow(),
                sst_c=_num(sst_row["sst_c"]) if sst_row else None,
                chlorophyll=_num(chl_row["chlorophyll"]) if chl_row else None,
                wave_height_m=None,
                wave_period_s=None,
                wave_direction_deg=None,
                current_speed_ms=None,
                current_direction_deg=None,
                salinity_psu=None,
                source=self.name,
                source_record_id=f"cw-ocean-{lat:.2f}-{lon:.2f}",
                quality=QualityStatus.VALID,
                raw_payload={"sst": sst_row, "chlorophyll": chl_row,
                             "sst_dataset": dataset, "chl_dataset": chl_dataset},
            )]
        except Exception as exc:
            raise SourceInvalidDataError(f"invalid coastwatch ocean data: {exc}")

    async def fetch_pfz(
        self, *, lat: float = None, lon: float = None, date=None, **kw
    ) -> List[PFZZone]:
        self._ensure_configured("pfz")
        if lat is None or lon is None:
            return []
        radius_deg = float(kw.get("radius_deg") or 0.75)
        step_deg = float(kw.get("step_deg") or 0.25)
        dataset = kw.get("sst_dataset") or self.settings.coastwatch_mur_sst_dataset
        grid = await fetch_coastwatch_sst_front_grid(
            lat, lon, radius_deg=radius_deg, step_deg=step_deg, dataset=dataset)
        fronts = derive_pfz_fronts_from_grid(grid)
        if not fronts:
            return []

        zones: List[PFZZone] = []
        observed = _parse_dt(grid[0].get("time")) if grid else utcnow()
        for front in fronts:
            flon, flat = float(front["lon"]), float(front["lat"])
            try:
                zones.append(PFZZone(
                    geometry=_cell_geometry(flat, flon, step_deg),
                    centroid=GeographicPoint(latitude=flat, longitude=flon),
                    generated_at=observed,
                    valid_from=observed,
                    valid_until=observed + timedelta(days=1),
                    species=[],
                    confidence=min(0.7, 0.4 + float(front.get("front_delta_c") or 0.0)),
                    metadata={
                        "estimated": True,
                        "basis": front.get("basis", "sst_front"),
                        "front_delta_c": front.get("front_delta_c"),
                        "sst_c": front.get("sst_c"),
                    },
                    source_timestamp=observed,
                    source=self.name,
                    source_record_id=(
                        f"cw-pfz-{flat:.4f}-{flon:.4f}-{observed:%Y%m%dT%H%M}"
                    ),
                    quality=QualityStatus.SUSPICIOUS,
                    raw_payload=dict(front),
                ))
            except Exception as exc:
                raise SourceInvalidDataError(f"invalid coastwatch pfz zone: {exc}")
        return zones


def _cell_geometry(lat: float, lon: float, step_deg: float) -> Dict:
    """Small square polygon around a grid cell (GeoJSON)."""
    half = step_deg / 2.0
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - half, lat - half],
            [lon + half, lat - half],
            [lon + half, lat + half],
            [lon - half, lat + half],
            [lon - half, lat - half],
        ]],
    }


def _num(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_dt(value):
    from app.datasources.normalize import parse_datetime
    return parse_datetime(value)