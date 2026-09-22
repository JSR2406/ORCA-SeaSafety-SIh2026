# MarineCapabilityClient - the seam between the legacy ORCA agents and the live
# marine data layer (MarineDataService + GeospatialService).
#
# Agents are deliberately decoupled from DB sessions and adapters: they call the
# client, which lazily owns the data services and normalizes every result into a
# "never raise, never fabricate" envelope:
#
#   {"available": bool, "status": str, "sources": [...], "data": ...}
#
# When a source is not configured, unavailable or errored, `available` is False
# and the agent falls back to its own deterministic estimates while recording a
# limitation.  Facts are never invented.
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.common import DataStatus

logger = logging.getLogger(__name__)

_OK_STATUSES = (DataStatus.LIVE, DataStatus.RECENT, DataStatus.STALE)


def _normalize(result, empty=None):
    """Normalize a MarineDataResult into the capability envelope."""
    if result is None or getattr(result, "status", None) not in _OK_STATUSES:
        status = getattr(result, "status", DataStatus.UNAVAILABLE)
        return {
            "available": False,
            "status": status.value,
            "sources": getattr(result, "sources", []),
            "data": empty if empty is not None else None,
            "error": getattr(result, "error", None),
        }
    return {
        "available": result.data is not None and result.data != [] and result.data != {},
        "status": result.status.value,
        "sources": result.sources,
        "data": result.data,
        "error": None,
    }


class MarineCapabilityClient:
    """Async facade for mariner agents over the live marine data services."""

    def __init__(self, marine=None, geo=None, evidence=None):
        from app.config import get_settings
        from app.datasources.registry import build_registry
        from app.db.client import get_session
        from app.services.geospatial_service import GeospatialService
        from app.services.marine_data_service import MarineDataService

        self.settings = get_settings()
        if marine is None:
            sources = build_registry(self.settings)
            marine = MarineDataService(self.settings, sources, get_session)
        self.marine = marine
        self.geo = geo or GeospatialService(self.settings, self.marine)
        self._evidence = evidence

    async def _record_evidence(
        self,
        *,
        query_run_id: Optional[str],
        agent_name: str,
        tool_name: str,
        evidence_type: str,
        source: str,
        data: Any,
    ) -> None:
        """Best-effort evidence write; never raises."""
        if not query_run_id or self._evidence is None or data is None:
            return
        payload = data
        if isinstance(data, dict) and "raw_payload" in data:
            payload = {k: v for k, v in data.items() if k != "raw_payload"}
        try:
            await self._evidence.record(
                query_run_id=query_run_id,
                agent_name=agent_name,
                tool_name=tool_name,
                evidence_type=evidence_type,
                source=source,
                payload={"data": payload},
            )
        except Exception:  # noqa: BLE001 - observability never breaks data flow
            logger.warning("capability client evidence write failed", exc_info=True)

    async def ocean_conditions(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Nearest ocean observation rows (wave/wind/current/SST/chlorophyll)."""
        result = await self.marine.get_ocean_conditions(
            lat, lon, time=time, radius_km=50.0, limit=5)
        env = _normalize(result, empty=[])
        if env["available"]:
            rows = env["data"]
            row = rows[0] if rows else {}
            env["data"] = {"row": row, "count": len(rows)}
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="ocean_conditions",
                evidence_type="ocean_observation",
                source=",".join(env.get("sources") or []),
                data=row,
            )
        return env

    async def weather_at(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Nearest weather observation rows (wind/temp/precip/visibility)."""
        result = await self.marine.get_weather_observation(
            lat, lon, time=time, radius_km=50.0, limit=5)
        env = _normalize(result, empty=[])
        if env["available"]:
            rows = env["data"]
            env["data"] = {"row": rows[0] if rows else {}, "count": len(rows)}
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="weather_at",
                evidence_type="weather_observation",
                source=",".join(env.get("sources") or []),
                data=rows[0] if rows else {},
            )
        return env

    async def active_restrictions_at(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.geo.check_point_in_restricted_area(lat, lon, time=time)
        data = _normalize(result, empty={"active_restrictions": []}).get("data")
        active = (data or {}).get("active_restrictions") or []
        if data is None:
            data = {}
        data["active_restrictions"] = active
        if active:
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="active_restrictions_at",
                evidence_type="restricted_area",
                source=",".join(result.sources or []),
                data=active,
            )
        return {"available": True, "status": "live", "sources": result.sources,
                "data": data}

    async def active_warnings_at(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.models.warnings import WarningStatus
        result = await self.marine.get_marine_warnings(lat=lat, lon=lon, active_at=time)
        env = _normalize(result, empty=[])
        rows = env["data"] if env["available"] else []
        active = [w for w in rows if w.get("status") == WarningStatus.ACTIVE]
        env["available"] = bool(active)
        env["data"] = active
        if active:
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="active_warnings_at",
                evidence_type="marine_warning",
                source=",".join(env.get("sources") or []),
                data=active,
            )
        return env

    async def restrictions_near_route(
        self, route: Sequence[Tuple[float, float]], time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.geo.restrictions_near_route(route, time=time)
        env = _normalize(result, empty={})
        if env["data"] is None:
            env["data"] = {"route_intersects_restricted_count": 0, "intersections": []}
        if env.get("available"):
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="restrictions_near_route",
                evidence_type="restricted_area",
                source=",".join(env.get("sources") or []),
                data=env["data"],
            )
        return env

    async def warnings_near_route(
        self, route: Sequence[Tuple[float, float]], time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.geo.warnings_near_route(route, time=time)
        env = _normalize(result, empty={})
        if env["data"] is None:
            env["data"] = {"warnings_intersecting": 0, "warning_intersections": []}
        if env.get("available"):
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="warnings_near_route",
                evidence_type="marine_warning",
                source=",".join(env.get("sources") or []),
                data=env["data"],
            )
        return env

    async def pfz_at(
        self, lat: float, lon: float, date: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.geo.check_point_in_pfz(lat, lon, date=date)
        env = _normalize(result, empty={"inside_pfz": False, "containing_zones": [],
                                        "nearby_zones": 0})
        if env.get("available"):
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="pfz_at",
                evidence_type="pfz_zone",
                source=",".join(env.get("sources") or []),
                data=env.get("data"),
            )
        return env

    async def fused_state(
        self, lat: float, lon: float, time: Optional[datetime] = None,
        query_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Canonical fused marine state at a point (real observations only)."""
        from app.services.marine_fusion import MarineDataFusion

        fusion = MarineDataFusion(marine=self.marine)
        state = await fusion.fused_state(lat, lon, time=time)
        payload = state.to_dict()
        available = bool(state.variables)
        if available and query_run_id:
            await self._record_evidence(
                query_run_id=query_run_id,
                agent_name="marine_capability",
                tool_name="fused_state",
                evidence_type="fused_state",
                source=",".join(state.sources),
                data=payload,
            )
        payload["available"] = available
        payload["error"] = None
        return payload


_capability_client: Optional[MarineCapabilityClient] = None


def get_marine_capability_client() -> MarineCapabilityClient:
    global _capability_client
    if _capability_client is None:
        _capability_client = MarineCapabilityClient()
    return _capability_client