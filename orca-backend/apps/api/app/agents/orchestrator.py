# Agent Orchestrator
# Execution graph coordinator for agent orchestration

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.agents import BaseAgent, ExecutionContext, AgentRegistry, get_agent_registry
from app.services.data_fusion import get_fusion_engine, DataFusionEngine
from app.services.provenance import get_provenance_service, ProvenanceService
from app.schemas.provenance import EvidenceBundle, SourceType

logger = logging.getLogger(__name__)


class Orchestrator(BaseAgent):
    """
    Execution graph coordinator that manages agent orchestration.
    
    Responsibilities:
    1. Select agents based on structured query intent
    2. Execute agents in dependency order (DAG)
    3. Merge EvidenceBundles from all agents using DataFusionEngine
    4. Run verifier on merged results
    5. Calculate confidence on final results
    6. Record full execution trace for provenance
    """
    
    def __init__(self):
        super().__init__("orchestrator")
        from app.agents import _register_default_agents
        _register_default_agents()
        self.registry = get_agent_registry()
        self.fusion_engine = get_fusion_engine()
        self.provenance_service = get_provenance_service()
    
    def get_required_inputs(self) -> List[str]:
        return []  # Orchestrator doesn't require evidence inputs
    
    def get_output_types(self) -> List[SourceType]:
        return [SourceType.ARGO, SourceType.WEATHER, SourceType.WAVE, 
                SourceType.CURRENT, SourceType.SATELLITE, SourceType.HAZARD]
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Execution graph coordinator for agent orchestration",
            "selects_agents": True,
            "merge_evidence": True,
            "available_agents": [a.name for a in self.registry.get_all()],
        }
    
    async def execute(self, context: ExecutionContext) -> List[EvidenceBundle]:
        """
        Main orchestration entry point.
        
        1. Analyze structured query to determine required agents
        2. Build execution DAG based on agent dependencies
        3. Execute agents in topological order
        4. Merge all EvidenceBundles using data fusion
        5. Run verifier on merged results
        6. Calculate confidence score
        7. Record provenance
        8. Return final EvidenceBundles
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Step 1: Determine required agents from structured query
            agent_plan = self._plan_agents(context.structured_query)
            
            if agent_plan["status"] == "needs_clarification":
                context.add_warning(agent_plan["clarification_question"])
                return []
            
            if agent_plan["status"] == "unsupported":
                context.add_error("Orchestrator", "plan", agent_plan.get("error", "Unsupported query"))
                return []
            
            # Step 2: Execute agents in dependency order
            all_bundles = []
            executed_agents = []
            
            for agent_info in agent_plan["agent_sequence"]:
                agent_name = agent_info["agent"]
                agent = self.registry.get(agent_name)
                
                if agent is None:
                    logger.error(f"Agent not found: {agent_name}")
                    context.add_error("orchestrator", agent_name, f"Agent {agent_name} not found")
                    continue
                
                # Get required evidence inputs for this agent
                required_input_types = agent.get_required_inputs()
                input_bundles = context.get_evidence(required_input_types) if required_input_types else []
                
                # Execute the agent
                result_bundles = await self._execute_agent_with_provenance(
                    agent, agent_name, input_bundles, context
                )
                
                if result_bundles:
                    all_bundles.extend(result_bundles)
                    executed_agents.append(agent_name)
                    
                    # Add agent output to context for downstream agents
                    context.set_agent_output(agent_name, result_bundles)
                
                # Small delay to prevent overwhelming data sources
                await asyncio.sleep(0.01)
            
            # Step 3: Merge all EvidenceBundles using data fusion
            if all_bundles:
                fused_result = self.fusion_engine.fuse_bundles(all_bundles)
                
                # Create unified evidence bundles from fused result
                final_bundles = self._create_final_bundles(fused_result, executed_agents, context)
            else:
                final_bundles = []
            
            # Step 4: Calculate confidence on final results
            if final_bundles:
                # Use the first bundle's confidence as overall, or compute aggregate
                overall_confidence = max(b.confidence for b in final_bundles) if final_bundles else 0.5
                
                # Update confidence if we have merged statistics
                if fused_result.get("fused_variables"):
                    for bundle in final_bundles:
                        # Attach fusion metadata to provenance
                        if "statistics" in fused_result.get("fused_variables", {}):
                            bundle.provenance_metadata["fusion_statistics"] = fused_result["fused_variables"]
            
            # Step 5: Record full provenance
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            self.provenance_service.record_execution(
                query_run_id=context.query_run_id,
                agent_name=self.name,
                tool_name="orchestrate",
                input_bundles=[],  # Input bundles are handled internally
                output_bundles=final_bundles,
                execution_time_ms=execution_time_ms,
                status="success" if final_bundles else "no_data",
            )
            
            # Add trace entry
            context.add_trace(
                self.name, "orchestrate", "success", execution_time_ms,
                f"Executed {len(executed_agents)} agents, produced {len(final_bundles)} evidence bundles"
            )
            
            logger.info(
                f"Orchestration complete: {len(executed_agents)} agents, "
                f"{len(final_bundles)} bundles, {execution_time_ms}ms"
            )
            
            return final_bundles
            
        except Exception as e:
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Record failure provenance
            self.provenance_service.record_execution(
                query_run_id=context.query_run_id,
                agent_name=self.name,
                tool_name="orchestrate",
                input_bundles=[],
                output_bundles=[],
                execution_time_ms=execution_time_ms,
                status="error",
                error=str(e),
            )
            
            context.add_trace(self.name, "orchestrate", "error", execution_time_ms, str(e))
            context.add_error("orchestrator", "orchestrate", str(e))
            
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            return []
    
    def _plan_agents(self, structured_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan which agents to execute based on the structured query intent.
        Returns agent sequence with dependencies.
        """
        intent = structured_query.get("intent", "")
        
        # Map intents to required agents
        intent_to_agents = {
            "profile_search": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "argo_agent", "dependencies": ["intent_agent"]},
            ],
            "timeseries_summary": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "argo_agent", "dependencies": ["intent_agent"]},
                {"agent": "confidence_agent", "dependencies": ["argo_agent"]},
            ],
            "depth_profile_summary": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "argo_agent", "dependencies": ["intent_agent"]},
                {"agent": "confidence_agent", "dependencies": ["argo_agent"]},
            ],
            "anomaly_detection": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "argo_agent", "dependencies": ["intent_agent"]},
                {"agent": "weather_agent", "dependencies": ["intent_agent"]},
                {"agent": "confidence_agent", "dependencies": ["argo_agent", "weather_agent"]},
            ],
            "marine_condition_briefing": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "weather_agent", "dependencies": ["intent_agent"]},
                {"agent": "wave_agent", "dependencies": ["intent_agent"]},
                {"agent": "current_agent", "dependencies": ["intent_agent"]},
                {"agent": "hazard_agent", "dependencies": ["weather_agent", "wave_agent", "current_agent"]},
                {"agent": "confidence_agent", "dependencies": ["weather_agent", "wave_agent", "current_agent", "hazard_agent"]},
            ],
            "route_analysis": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "route_agent", "dependencies": ["intent_agent"]},
                {"agent": "hazard_agent", "dependencies": ["route_agent"]},
                {"agent": "confidence_agent", "dependencies": ["route_agent", "hazard_agent"]},
            ],
            "hazard_assessment": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "hazard_agent", "dependencies": ["intent_agent"]},
                {"agent": "confidence_agent", "dependencies": ["hazard_agent"]},
            ],
            "scenario_projection": [
                {"agent": "intent_agent", "dependencies": []},
                {"agent": "scenario_agent", "dependencies": ["intent_agent"]},
                {"agent": "confidence_agent", "dependencies": ["scenario_agent"]},
            ],
        }
        
        # Get the agent list for this intent
        agents = intent_to_agents.get(intent)
        if not agents:
            # Check if intent is supported by checking registered agents
            return {
                "status": "unsupported",
                "error": f"Unsupported intent: {intent}",
                "clarification_question": None,
            }
        
        # Build dependency-respecting execution order using topological sort
        # Simple approach: respect dependencies, execute in order
        agent_map = {a["agent"]: a["dependencies"] for a in agents}
        
        # Topological sort
        executed = set()
        agent_sequence = []
        
        def execute_agent(agent_name: str):
            if agent_name in executed:
                return
            deps = agent_map.get(agent_name, [])
            for dep in deps:
                execute_agent(dep)
            executed.add(agent_name)
            agent_sequence.append({"agent": agent_name, "dependencies": deps})
        
        # Start with intent_agent if present
        if "intent_agent" in agent_map:
            execute_agent("intent_agent")
        else:
            # If no intent_agent, start from the first agent
            if agents:
                execute_agent(agents[0]["agent"])
        
        return {
            "status": "ready",
            "intent": intent,
            "agent_sequence": agent_sequence,
            "clarification_question": None,
        }
    
    async def _execute_agent_with_provenance(
        self,
        agent: BaseAgent,
        agent_name: str,
        input_bundles: List[EvidenceBundle],
        context: ExecutionContext,
    ) -> List[EvidenceBundle]:
        """Execute a single agent with full provenance tracking."""
        # Create a sub-context for the agent
        agent_context = ExecutionContext(
            query_run_id=context.query_run_id,
            user_query=context.user_query,
            structured_query=context.structured_query,
            detected_language=context.detected_language,
            session_id=context.session_id,
        )
        
        # Add existing evidence as input
        if input_bundles:
            agent_context.add_evidence(input_bundles)
        
        # Execute the agent
        result_bundles = await agent.execute(agent_context)
        
        # Record provenance for this agent execution
        self.provenance_service.record_execution(
            query_run_id=context.query_run_id,
            agent_name=agent_name,
            tool_name=agent_name,
            input_bundles=input_bundles,
            output_bundles=result_bundles,
            execution_time_ms=0,  # Will be tracked by agent
            status="success" if result_bundles else "no_data",
        )
        
        # Add trace
        duration = getattr(agent, '_last_duration_ms', 0)
        context.add_trace(agent_name, agent_name, "success" if result_bundles else "no_data", duration or 0)
        
        # Store agent output for downstream agents
        context.set_agent_output(agent_name, result_bundles)
        
        return result_bundles
    
    def _create_final_bundles(
        self,
        fused_result: Dict[str, Any],
        executed_agents: List[str],
        context: ExecutionContext,
    ) -> List[EvidenceBundle]:
        """Create final EvidenceBundles from fusion results."""
        final_bundles = []
        fusion_stats = fused_result.get("fused_variables", {})
        
        # Create a summary bundle with fusion metadata
        if fusion_stats:
            # Determine the primary variable from fusion
            primary_var = list(fusion_stats.keys())[0] if fusion_stats else "unknown"
            
            # Create a comprehensive evidence bundle
            from app.schemas.provenance import SourceType, GeoJSONGeometry
            
            # Use the first agent's region as the scope
            primary_agent = executed_agents[0] if executed_agents else "intent_agent"
            
            bundle = EvidenceBundle(
                source_id=f"orca_{context.query_run_id}_{primary_agent}",
                source_type=SourceType.ARGO,  # Default, could be mixed
                source_name=f"ORCA Orchestrated Query - {context.query_run_id}",
                source_url=None,
                variables=[primary_var],
                measurements={primary_var: fusion_stats.get(primary_var, {}).get("mean", 0) if isinstance(fusion_stats.get(primary_var), dict) else fusion_stats.get(primary_var, 0)},
                units={primary_var: "°C" if "temperature" in primary_var else "PSU" if "salinity" in primary_var else "unknown"},
                geographic_scope=None,  # Would need to merge spatial scopes
                valid_from=None,
                valid_to=None,
                quality_flags={},
                freshness=None,
                confidence=0.8,  # Default, could be computed from components
                agent_name="orchestrator",
                tool_name="orchestrate",
                provenance_metadata={
                    "fusion_statistics": fusion_stats,
                    "executed_agents": executed_agents,
                    "query_run_id": context.query_run_id,
                },
            )
            final_bundles.append(bundle)
        
        return final_bundles


# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


# Export
__all__ = ["Orchestrator", "get_orchestrator"]