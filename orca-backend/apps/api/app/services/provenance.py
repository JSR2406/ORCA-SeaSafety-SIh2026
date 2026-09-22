# Provenance Service
# Source traceability, audit logging, and data lineage

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4

from app.schemas.provenance import (
    EvidenceBundle,
    ProvenanceRecord,
    SourceType,
    SourceHealth,
    ProvenanceQuery,
)
from app.services.data_fusion import get_fusion_engine

logger = logging.getLogger(__name__)


class ProvenanceService:
    """
    Manages data provenance, audit trails, and source health tracking.
    """
    
    def __init__(self):
        self.fusion_engine = get_fusion_engine()
        self.provenance_store: Dict[str, ProvenanceRecord] = {}
        self.query_audit_log: List[Dict[str, Any]] = []
    
    def record_execution(
        self,
        query_run_id: str,
        agent_name: str,
        tool_name: str,
        input_bundles: List[EvidenceBundle],
        output_bundles: List[EvidenceBundle],
        execution_time_ms: int,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Record an agent/tool execution for audit trail."""
        
        # Record output bundles in fusion engine
        for bundle in output_bundles:
            bundle.agent_name = agent_name
            bundle.tool_name = tool_name
        
        # Create provenance records
        for bundle in output_bundles:
            parent_ids = [b.source_id for b in input_bundles]
            record = ProvenanceRecord(
                id=bundle.source_id,
                source_bundle=bundle,
                transformation=f"{agent_name}.{tool_name}",
                parent_ids=parent_ids,
                created_by=f"{agent_name}.{tool_name}",
                checksum=self._compute_checksum(bundle),
            )
            self.provenance_store[bundle.source_id] = record
            self.fusion_engine.provenance_chain.append(record)
        
        # Audit log
        self.query_audit_log.append({
            "query_run_id": query_run_id,
            "agent": agent_name,
            "tool": tool_name,
            "input_count": len(input_bundles),
            "output_count": len(output_bundles),
            "execution_time_ms": execution_time_ms,
            "status": status,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        logger.info(
            f"Execution recorded: {agent_name}.{tool_name} "
            f"({len(input_bundles)} inputs -> {len(output_bundles)} outputs, "
            f"{execution_time_ms}ms, {status})"
        )
    
    def get_provenance(self, source_id: str) -> Optional[ProvenanceRecord]:
        """Get provenance record for a source."""
        return self.provenance_store.get(source_id)
    
    def get_full_lineage(self, source_id: str) -> List[ProvenanceRecord]:
        """Get full lineage chain for a source."""
        return self.fusion_engine.get_provenance_chain(source_id)
    
    def query_provenance(self, query: ProvenanceQuery) -> List[ProvenanceRecord]:
        """Query provenance records by criteria."""
        results = []
        
        for record in self.provenance_store.values():
            bundle = record.source_bundle
            
            # Filter by source_ids
            if query.source_ids and bundle.source_id not in query.source_ids:
                continue
            
            # Filter by source_types
            if query.source_types and bundle.source_type not in query.source_types:
                continue
            
            # Filter by time range
            if query.time_range:
                start = query.time_range.get("start")
                end = query.time_range.get("end")
                if start and bundle.retrieved_at < start:
                    continue
                if end and bundle.retrieved_at > end:
                    continue
            
            # Filter by geographic scope (simplified)
            if query.geographic_scope and bundle.geographic_scope:
                # Would need proper spatial intersection
                pass
            
            results.append(record)
        
        return results
    
    def get_audit_log(
        self,
        query_run_id: Optional[str] = None,
        agent: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get execution audit log."""
        log = self.query_audit_log
        
        if query_run_id:
            log = [e for e in log if e.get("query_run_id") == query_run_id]
        if agent:
            log = [e for e in log if e.get("agent") == agent]
        
        return log[-limit:]
    
    def update_source_health(
        self,
        source_id: str,
        source_type: SourceType,
        status: Literal["healthy", "degraded", "unavailable", "unknown"],
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
        data_freshness_hours: Optional[float] = None,
    ) -> None:
        """Update health status of a data source."""
        health = SourceHealth(
            source_id=source_id,
            source_type=source_type,
            status=status,
            last_successful_fetch=datetime.utcnow() if status == "healthy" else None,
            last_error=error,
            latency_ms=latency_ms,
            data_freshness_hours=data_freshness_hours,
        )
        self.fusion_engine.register_source(health)
    
    def get_source_health(self, source_id: str) -> Optional[SourceHealth]:
        return self.fusion_engine.get_source_health(source_id)
    
    def get_all_source_health(self) -> Dict[str, SourceHealth]:
        return self.fusion_engine.source_registry
    
    def _compute_checksum(self, bundle: EvidenceBundle) -> str:
        """Compute deterministic checksum for a bundle."""
        content = f"{bundle.source_id}{bundle.source_type.value}{bundle.measurements}{bundle.valid_from}{bundle.valid_to}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def export_provenance_graph(self, query_run_id: str) -> Dict[str, Any]:
        """Export provenance graph for a query run."""
        nodes = []
        edges = []
        
        for record in self.query_audit_log:
            if record.get("query_run_id") == query_run_id:
                # Add nodes for agent/tool
                agent_node = f"agent:{record['agent']}"
                tool_node = f"tool:{record['agent']}.{record['tool']}"
                
                if agent_node not in [n["id"] for n in nodes]:
                    nodes.append({"id": agent_node, "type": "agent", "label": record["agent"]})
                if tool_node not in [n["id"] for n in nodes]:
                    nodes.append({"id": tool_node, "type": "tool", "label": f"{record['agent']}.{record['tool']}"})
                
                # Edge from agent to tool
                edges.append({"from": agent_node, "to": tool_node, "type": "executes"})
                
                # Add input/output bundles as nodes
                for i, bundle_id in enumerate(record.get("input_bundles", [])):
                    nodes.append({"id": f"bundle:{bundle_id}", "type": "bundle", "label": f"Input {i}"})
                    edges.append({"from": f"bundle:{bundle_id}", "to": tool_node, "type": "input"})
                
                for i, bundle_id in enumerate(record.get("output_bundles", [])):
                    nodes.append({"id": f"bundle:{bundle_id}", "type": "bundle", "label": f"Output {i}"})
                    edges.append({"from": tool_node, "to": f"bundle:{bundle_id}", "type": "output"})
        
        return {"nodes": nodes, "edges": edges}


# Global provenance service instance
_provenance_service: Optional[ProvenanceService] = None


def get_provenance_service() -> ProvenanceService:
    global _provenance_service
    if _provenance_service is None:
        _provenance_service = ProvenanceService()
    return _provenance_service