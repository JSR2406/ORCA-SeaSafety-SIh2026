# Phase 11 - ProactiveMarineAgent.
#
# Interprets meaningful marine events, determines the affected geography,
# correlates marine/weather/safety information, and invokes the relevant
# specialized agents THROUGH the MCP tool bus (never external APIs).  It
# produces evidence-backed ALERT CANDIDATES that are later gated by the
# AlertPolicyEngine -> Risk Engine -> Verifier.
#
# Safety authority is immutable:
#   HARD CONSTRAINTS > RISK ENGINE > VERIFIER > ML > RAG > LLM.
# This agent is a coordinator only; it can never override a hard restriction.
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from app.events.model import EventSeverity, MarineEvent, MarineEventType
from app.events.policy import preference_category
from app.services.risk_engine import get_risk_engine

logger = structlog.get_logger(__name__)


@dataclass
class AlertCandidateEnvelope:
    """Evidence-backed alert candidate prepared by the proactive agent."""
    candidate_id: str
    event_type: MarineEventType
    source: str
    title: str
    message: str
    severity: EventSeverity
    geography: Dict[str, Any]
    lat: Optional[float] = None
    lon: Optional[float] = None
    probability: Optional[float] = None
    tool_evidence: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: str = ""
    hard_constraint: bool = False
    tool_calls: int = 0
    agents_invoked: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "geography": self.geography,
            "lat": self.lat,
            "lon": self.lon,
            "probability": self.probability,
            "tool_evidence": self.tool_evidence,
            "risk_level": self.risk_level,
            "hard_constraint": self.hard_constraint,
            "tool_calls": self.tool_calls,
            "agents_invoked": self.agents_invoked,
        }


class ProactiveMarineAgent:
    """Coordination agent that maps marine events to candidate alerts via MCP
    tools and the Risk Engine (authoritative)."""

    def __init__(self, tool_registry=None, risk_engine=None) -> None:
        # tool_registry is the MCP ToolRegistry (ToolBus); if absent the agent
        # still reasons over event metadata + the deterministic Risk Engine.
        self.tools = tool_registry
        self.risk = risk_engine or get_risk_engine()
        self._calls = 0

    async def correlate(self, event: MarineEvent) -> Dict[str, Any]:
        """Optionally pull fused state through MCP for the event location."""
        if self.tools is None or not event.location:
            return {}
        try:
            result = await self.tools.invoke(
                "marine.get_fused_state",
                {"lat": event.location.get("lat"),
                 "lon": event.location.get("lon")},
                request_id=f"proactive-{uuid.uuid4().hex[:8]}",
            )
            self._calls += 1
            return result.get("data") or {}
        except Exception as exc:  # noqa: BLE001 - correlation is best-effort
            logger.warning("proactive_correlate_failed", error=str(exc))
            return {}

    async def prepare_candidate(self, event: MarineEvent) -> Optional[AlertCandidateEnvelope]:
        """Interpret an event, correlate, evaluate risk (Risk Engine), and
        build an evidence-backed alert candidate."""
        fused = await self.correlate(event)
        lat = (event.location or {}).get("lat")
        lon = (event.location or {}).get("lon")

        # Risk evaluation via the authoritative RiskEngine when we have data.
        risk_level = ""
        hard = False
        risk_evidence: List[Dict[str, Any]] = []
        vars_ = (fused.get("variables") or {}) if isinstance(fused, dict) else {}
        if vars_:
            scores = []
            for var, calc in (("wave_height_m", self.risk._calc_wave_risk),
                              ("wind_speed_ms", self.risk._calc_wind_risk),
                              ("current_speed_ms", self.risk._calc_current_risk)):
                value = vars_.get(var)
                if value is not None:
                    r = calc(value)
                    scores.append({"variable": var, "value": value, "risk": r})
            active = bool((fused.get("missing") or []) in (fused.get("missing"),)
                          and vars_)
            if active or scores:
                avg = sum(s["risk"] for s in scores) / len(scores) if scores else 0.0
                risk_level = self.risk._score_to_risk_level(avg) if scores else "unavailable"
            if fused.get("hard_constraint") or fused.get("restricted"):
                hard = True
                risk_level = "elevated"
        # A hard restriction always dominates the candidate severity.
        severity = EventSeverity.CRITICAL if hard else event.severity

        tool_evidence = [{
            "tool": "marine.get_fused_state",
            "source": "marine_fusion",
            "retrieved": True,
            "variables_present": list(vars_.keys()),
            "paired_evidence": fused,
        }] if fused else []
        if risk_evidence:
            tool_evidence += risk_evidence
        if not tool_evidence:
            tool_evidence = [{
                "tool": "event.source",
                "source": event.source,
                "claim": (event.metadata or {}).get("description")
                         or event.event_type.value,
            }]

        candidate = AlertCandidateEnvelope(
            candidate_id=f"cand-{uuid.uuid4().hex[:10]}",
            event_type=event.event_type,
            source=event.source,
            title=self._title(event),
            message=(event.metadata or {}).get("description")
                    or self._title(event),
            severity=severity,
            geography={"lat": lat, "lon": lon},
            lat=lat, lon=lon,
            probability=self._probability(event),
            tool_evidence=tool_evidence,
            risk_level=risk_level,
            hard_constraint=hard,
            tool_calls=self._calls,
            agents_invoked=self._agents_for(event),
        )
        return candidate

    @staticmethod
    def _agents_for(event: MarineEvent) -> List[str]:
        category = preference_category(event.event_type)
        mapping = {
            "cyclone": ["weather_agent", "safety_agent"],
            "waves": ["marine_agent", "risk_agent"],
            "weather": ["weather_agent", "safety_agent"],
            "lightning": ["weather_agent", "safety_agent"],
            "restrictions": ["geofence_agent", "restriction_agent"],
            "geofence": ["geofence_agent"],
            "pfz": ["fishing_agent"],
            "data": ["marine_agent"],
        }
        return mapping.get(category, ["marine_agent"])

    @staticmethod
    def _title(event: MarineEvent) -> str:
        meta = event.metadata or {}
        return meta.get("name") or meta.get("title") or event.event_type.value

    @staticmethod
    def _probability(event: MarineEvent) -> Optional[float]:
        return event.metadata.get("probability")

    @property
    def calls(self) -> int:
        return self._calls


_proactive_agent: Optional[ProactiveMarineAgent] = None
_engine: Any = None


def get_proactive_agent(tool_registry=None, risk_engine=None) -> ProactiveMarineAgent:
    global _proactive_agent
    if _proactive_agent is None:
        _proactive_agent = ProactiveMarineAgent(tool_registry=tool_registry,
                                                risk_engine=risk_engine)
    return _proactive_agent


def get_proactive_engine(persistence=None) -> Any:
    global _engine
    if _engine is None:
        from app.services.proactive_engine import ProactiveMarineEngine
        from app.services.alert_repository import AlertRepository
        if persistence is None:
            persistence = AlertRepository()  # shared in-memory backing store
        _engine = ProactiveMarineEngine(persistence=persistence)
    return _engine


def reset_proactive_singletons() -> None:
    """Test/restart hook to clear cross-test singleton state."""
    global _proactive_agent, _engine
    _proactive_agent = None
    _engine = None