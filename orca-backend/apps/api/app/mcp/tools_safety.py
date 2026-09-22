# Tool group: safety - decision-support checks combining restrictions and
# active warnings for a point.  Output is advisory only (no vessel control).
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.mcp.registry import DECISION_SUPPORT, SPATIAL_ANALYSIS, ToolDefinition, ToolRegistry
from app.models.common import DataStatus
from app.models.result import MarineDataResult
from app.models.warnings import WarningStatus
from app.services.geospatial_service import GeospatialService
from app.services.marine_data_service import MarineDataService


class MarineSafetyCheckInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    time: Optional[datetime] = Field(None, description="Reference time (ISO-8601)")


def _severity(status: DataStatus) -> int:
    order = {
        DataStatus.NOT_CONFIGURED: 4,
        DataStatus.ERROR: 3,
        DataStatus.UNAVAILABLE: 2,
        DataStatus.STALE: 1,
        DataStatus.RECENT: 1,
        DataStatus.LIVE: 0,
    }
    return order.get(status, 0)


def _merge(*results: MarineDataResult) -> MarineDataResult:
    """Merge sub-results into one envelope; the most severe status wins."""
    invoked = [r for r in results if r is not None]
    if not invoked:
        return MarineDataResult(status=DataStatus.ERROR, error="no sub-results")
    worst = max(invoked, key=lambda r: _severity(r.status))
    sources = sorted({s for r in invoked for s in r.sources})
    warnings: List[str] = []
    for r in invoked:
        warnings.extend(r.warnings or [])
    confidence = [r.confidence for r in invoked if r.confidence is not None]
    return MarineDataResult(
        status=worst.status,
        data=None,
        sources=sources,
        warnings=warnings,
        confidence=round(sum(confidence) / len(confidence), 2) if confidence else None,
    )


def register(registry: ToolRegistry, marine: MarineDataService, geo: GeospatialService) -> None:
    async def marine_safety_check(
        lat: float, lon: float, time: Optional[datetime] = None, ctx=None
    ) -> MarineDataResult:
        restrictions = await geo.check_point_in_restricted_area(lat, lon, time=time)
        warnings_res = await marine.get_marine_warnings(lat=lat, lon=lon, active_at=time)

        base = _merge(restrictions, warnings_res)
        base.data = {
            "point": {"lat": lat, "lon": lon},
            "inside_restricted_area": (
                (restrictions.data or {}).get("inside_restricted_area", False)
                if restrictions.data else False
            ),
            "restriction_details": (restrictions.data or {}).get("inside_areas", []),
            "active_warnings": [
                w for w in (warnings_res.data or [])
                if w.get("status") == WarningStatus.ACTIVE.value
                or w.get("status") == WarningStatus.ACTIVE
            ],
            "warning_count": len(warnings_res.data or []),
            "suggested": "avoid_region" if bool(
                (restrictions.data or {}).get("inside_restricted_area", False)
            ) or any(
                (w.get("status") == WarningStatus.ACTIVE.value or w.get("status") == WarningStatus.ACTIVE)
                for w in (warnings_res.data or [])
            ) else "proceed_with_caution",
        }
        return base

    registry.register(ToolDefinition(
        name="safety.marine_safety_check",
        fn=marine_safety_check,
        title="Marine safety check",
        description=("Advisory check combining restricted-area containment and active marine "
                     "warnings for a point. Informational only; never issues warnings directly."),
        group="safety",
        safety=DECISION_SUPPORT,
        input_model=MarineSafetyCheckInput,
    ))