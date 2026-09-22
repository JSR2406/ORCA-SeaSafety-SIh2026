# Agent Framework
# Base agent class and execution context for agent orchestration

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Define SourceType locally to avoid circular imports
class SourceType(str, Enum):
    ARGO = "argo"
    WEATHER = "weather"
    WAVE = "wave"
    CURRENT = "current"
    SATELLITE = "satellite"
    HAZARD = "hazard"
    GEOFENCE = "geofence"
    FORECAST = "forecast"
    CLIMATOLOGY = "climatology"
    REANALYSIS = "reanalysis"
    DEMO = "demo"


@dataclass
class ExecutionContext:
    """Shared context passed between agents during execution."""
    
    query_run_id: str
    user_query: str
    structured_query: Dict[str, Any]
    detected_language: str
    session_id: str
    
    # Runtime state
    evidence_bundles: List[Any] = field(default_factory=list)
    agent_outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Configuration
    spatial_tolerance_km: float = 5.0
    temporal_tolerance_hours: float = 6.0
    confidence_threshold: float = 0.5
    
    # Execution trace
    trace: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_trace(self, agent: str, tool: str, status: str, duration_ms: int, details: Optional[str] = None):
        self.trace.append({
            "agent": agent,
            "tool": tool,
            "status": status,
            "duration_ms": duration_ms,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def add_evidence(self, bundles: List[Any]):
        self.evidence_bundles.extend(bundles)
    
    def add_error(self, agent: str, tool: str, error: str):
        self.errors.append({
            "agent": agent,
            "tool": tool,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logging.getLogger(__name__).warning(f"Agent {agent} error in {tool}: {error}")
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
    
    def get_evidence(self, source_type: Optional[SourceType] = None) -> List[Any]:
        if source_type:
            return [b for b in self.evidence_bundles if getattr(b, 'source_type', None) == source_type]
        return self.evidence_bundles
    
    def get_agent_output(self, agent_name: str) -> Optional[Any]:
        return self.agent_outputs.get(agent_name)
    
    def set_agent_output(self, agent_name: str, output: Any):
        self.agent_outputs[agent_name] = output


class BaseAgent(ABC):
    """
    Base class for all ORCA agents.
    
    Agents are deterministic services that:
    1. Take an ExecutionContext
    2. Execute their specific logic
    3. Return EvidenceBundle(s)
    4. Record provenance
    """
    
    def __init__(self, name: str):
        self.name = name
        self._tools: Dict[str, Any] = {}
    
    @abstractmethod
    async def execute(self, context: ExecutionContext) -> List[Any]:
        """
        Execute the agent's primary function.
        
        Args:
            context: Shared execution context
            
        Returns:
            List of EvidenceBundle produced by this agent
        """
        pass
    
    @abstractmethod
    def get_required_inputs(self) -> List[str]:
        """Return list of required input types (source_type values)."""
        pass
    
    @abstractmethod
    def get_output_types(self) -> List[SourceType]:
        """Return list of output source types this agent produces."""
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return agent capabilities for planner."""
        return {
            "name": self.name,
            "required_inputs": self.get_required_inputs(),
            "output_types": [t.value for t in self.get_output_types()],
            "tools": list(self._tools.keys()),
        }
    
    def register_tool(self, tool_name: str, tool_func):
        """Register a tool function."""
        self._tools[tool_name] = tool_func
    
    async def _execute_with_provenance(
        self,
        context: ExecutionContext,
        tool_name: str,
        tool_func,
        input_bundles: List[Any],
    ) -> List[Any]:
        """Execute a tool with provenance tracking."""
        start_time = time.time()
        
        try:
            output_bundles = await tool_func(context, input_bundles)
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Add to context trace
            context.add_trace(self.name, tool_name, "success" if output_bundles else "no_data", duration_ms)
            
            return output_bundles
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            context.add_trace(self.name, tool_name, "error", duration_ms, str(e))
            context.add_error(self.name, tool_name, str(e))
            
            logger.error(f"Agent {self.name} tool {tool_name} failed: {e}")
            return []
    
    def _get_relevant_evidence(self, context: ExecutionContext, source_types: List[SourceType]) -> List[Any]:
        """Get evidence bundles matching required source types."""
        relevant = []
        for st in source_types:
            relevant.extend(context.get_evidence(st))
        return relevant


class AgentRegistry:
    """Registry for managing available agents."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
    
    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")
    
    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)
    
    def get_all(self) -> List[BaseAgent]:
        return list(self._agents.values())
    
    def get_by_output_type(self, source_type: str) -> List[BaseAgent]:
        """Get agents that produce a specific source type."""
        try:
            st = SourceType(source_type)
        except ValueError:
            return []
        
        return [a for a in self._agents.values() if st in a.get_output_types()]
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {name: agent.get_capabilities() for name, agent in self._agents.items()}


# Global agent registry
_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry


# Auto-register default agents
def _register_default_agents() -> AgentRegistry:
    registry = get_agent_registry()
    # Check if already registered
    if registry.get("intent_agent") is not None:
        return registry
    
    # Import here to avoid circular imports
    from app.agents.intent_agent import IntentAgent
    from app.services.scenario_agent import ScenarioAgent
    from app.agents.route_agent import RouteAgent
    from app.agents.geofence_agent import GeofenceAgent
    
    registry.register(IntentAgent())
    registry.register(ScenarioAgent())
    registry.register(RouteAgent())
    registry.register(GeofenceAgent())
    
    return registry


# Export
__all__ = ["BaseAgent", "ExecutionContext", "AgentRegistry", "get_agent_registry", "SourceType", "_register_default_agents"]