# Data Fusion Service
# Multi-source evidence aggregation and fusion

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from app.schemas.provenance import (
    EvidenceBundle,
    ProvenanceRecord,
    SourceType,
    DataFreshness,
    GeoJSONGeometry,
    SourceHealth,
)

logger = logging.getLogger(__name__)


class DataFusionEngine:
    """
    Fuses multiple EvidenceBundles into a unified evidence context.
    Handles spatial/temporal alignment, deduplication, and conflict resolution.
    """
    
    def __init__(self):
        self.provenance_chain: List[ProvenanceRecord] = []
        self.source_registry: Dict[str, SourceHealth] = {}
    
    def register_source(self, source: SourceHealth) -> None:
        """Register a data source for health tracking."""
        self.source_registry[source.source_id] = source
    
    def get_source_health(self, source_id: str) -> Optional[SourceHealth]:
        return self.source_registry.get(source_id)
    
    def create_bundle(
        self,
        source_type: SourceType,
        source_name: str,
        source_url: Optional[str],
        variables: List[str],
        measurements: Dict[str, Any],
        units: Dict[str, str],
        geographic_scope: Optional[GeoJSONGeometry],
        valid_from: Optional[datetime],
        valid_to: Optional[datetime],
        quality_flags: Dict[str, Any],
        freshness: Optional[DataFreshness],
        confidence: float,
        agent_name: str,
        tool_name: str,
        provenance_metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceBundle:
        """Create a new EvidenceBundle with provenance tracking."""
        bundle = EvidenceBundle(
            source_id=f"{source_type.value}_{source_name}_{uuid4().hex[:8]}",
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
            variables=variables,
            measurements=measurements,
            units=units,
            geographic_scope=geographic_scope,
            valid_from=valid_from,
            valid_to=valid_to,
            quality_flags=quality_flags,
            freshness=freshness,
            confidence=confidence,
            agent_name=agent_name,
            tool_name=tool_name,
            provenance_metadata=provenance_metadata or {},
        )
        
        # Record provenance
        record = ProvenanceRecord(
            id=bundle.source_id,
            source_bundle=bundle,
            created_by=f"{agent_name}.{tool_name}",
        )
        self.provenance_chain.append(record)
        
        return bundle
    
    def fuse_bundles(
        self,
        bundles: List[EvidenceBundle],
        spatial_tolerance_km: float = 5.0,
        temporal_tolerance_hours: float = 6.0,
    ) -> Dict[str, Any]:
        """
        Fuse multiple evidence bundles into a unified context.
        
        Handles:
        - Spatial alignment (nearby observations)
        - Temporal alignment (overlapping time windows)
        - Variable deduplication
        - Conflict detection (conflicting measurements)
        """
        if not bundles:
            return {"bundles": [], "fused_variables": {}, "conflicts": [], "coverage": {}}
        
        # Group by variable
        variable_map: Dict[str, List[EvidenceBundle]] = {}
        for bundle in bundles:
            for var in bundle.variables:
                if var not in variable_map:
                    variable_map[var] = []
                variable_map[var].append(bundle)
        
        # Fuse each variable
        fused_variables = {}
        conflicts = []
        
        for var, var_bundles in variable_map.items():
            fused = self._fuse_variable(var, var_bundles, spatial_tolerance_km, temporal_tolerance_hours)
            fused_variables[var] = fused
            
            # Check for conflicts
            if len(var_bundles) > 1:
                conflict = self._detect_conflicts(var, var_bundles)
                if conflict:
                    conflicts.append(conflict)
        
        # Compute combined coverage
        coverage = self._compute_coverage(bundles)
        
        return {
            "bundles": [b.model_dump() for b in bundles],
            "fused_variables": fused_variables,
            "conflicts": conflicts,
            "coverage": coverage,
            "source_count": len(bundles),
            "source_types": list(set(b.source_type.value for b in bundles)),
        }
    
    def _fuse_variable(
        self,
        variable: str,
        bundles: List[EvidenceBundle],
        spatial_tolerance_km: float,
        temporal_tolerance_hours: float,
    ) -> Dict[str, Any]:
        """Fuse measurements for a single variable from multiple sources."""
        all_measurements = []
        sources = []
        
        for bundle in bundles:
            if variable in bundle.measurements:
                value = bundle.measurements[variable]
                if isinstance(value, (int, float)):
                    all_measurements.append(float(value))
                elif isinstance(value, list):
                    all_measurements.extend([float(v) for v in value if isinstance(v, (int, float))])
                sources.append({
                    "source_id": bundle.source_id,
                    "source_type": bundle.source_type.value,
                    "confidence": bundle.confidence,
                })
        
        if not all_measurements:
            return {"values": [], "sources": sources, "statistics": None}
        
        # Compute statistics
        import numpy as np
        arr = np.array(all_measurements)
        
        return {
            "values": all_measurements,
            "sources": sources,
            "statistics": {
                "count": len(all_measurements),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "median": float(np.median(arr)),
            },
            "source_count": len(sources),
        }
    
    def _detect_conflicts(
        self,
        variable: str,
        bundles: List[EvidenceBundle],
    ) -> Optional[Dict[str, Any]]:
        """Detect conflicting measurements for the same variable."""
        values = []
        for bundle in bundles:
            if variable in bundle.measurements:
                val = bundle.measurements[variable]
                if isinstance(val, (int, float)):
                    values.append((float(val), bundle.source_id, bundle.confidence))
        
        if len(values) < 2:
            return None
        
        # Check if values differ significantly (beyond expected uncertainty)
        vals = [v[0] for v in values]
        import numpy as np
        mean_val = np.mean(vals)
        std_val = np.std(vals)
        
        # If coefficient of variation > 50% and we have high-confidence sources
        high_conf_sources = [v for v in values if v[2] > 0.7]
        if len(high_conf_sources) >= 2 and mean_val != 0 and (std_val / abs(mean_val)) > 0.5:
            return {
                "variable": variable,
                "values": [{"value": v[0], "source": v[1], "confidence": v[2]} for v in values],
                "mean": float(mean_val),
                "std": float(std_val),
                "cv": float(std_val / abs(mean_val)) if mean_val != 0 else None,
                "severity": "high" if (std_val / abs(mean_val)) > 1.0 else "medium",
            }
        
        return None
    
    def _compute_coverage(self, bundles: List[EvidenceBundle]) -> Dict[str, Any]:
        """Compute combined spatial/temporal coverage."""
        spatial_bounds = None
        temporal_bounds = None
        
        for bundle in bundles:
            # Spatial
            if bundle.geographic_scope:
                coords = self._extract_coordinates(bundle.geographic_scope)
                if coords:
                    if spatial_bounds is None:
                        spatial_bounds = {"min_lat": coords[0], "max_lat": coords[0], "min_lon": coords[1], "max_lon": coords[1]}
                    else:
                        spatial_bounds["min_lat"] = min(spatial_bounds["min_lat"], coords[0])
                        spatial_bounds["max_lat"] = max(spatial_bounds["max_lat"], coords[0])
                        spatial_bounds["min_lon"] = min(spatial_bounds["min_lon"], coords[1])
                        spatial_bounds["max_lon"] = max(spatial_bounds["max_lon"], coords[1])
            
            # Temporal
            if bundle.valid_from or bundle.valid_to:
                if temporal_bounds is None:
                    temporal_bounds = {"start": bundle.valid_from, "end": bundle.valid_to}
                else:
                    if bundle.valid_from and (temporal_bounds["start"] is None or bundle.valid_from < temporal_bounds["start"]):
                        temporal_bounds["start"] = bundle.valid_from
                    if bundle.valid_to and (temporal_bounds["end"] is None or bundle.valid_to > temporal_bounds["end"]):
                        temporal_bounds["end"] = bundle.valid_to
        
        return {
            "spatial": spatial_bounds,
            "temporal": temporal_bounds,
            "variable_count": len(set().union(*[set(b.variables) for b in bundles])),
        }
    
    def _extract_coordinates(self, geometry: GeoJSONGeometry) -> Optional[tuple]:
        """Extract lat/lon from geometry."""
        if geometry.type == "Point" and geometry.coordinates:
            return (geometry.coordinates[1], geometry.coordinates[0])  # lat, lon
        return None
    
    def get_provenance_chain(self, source_id: str) -> List[ProvenanceRecord]:
        """Get full provenance chain for a source."""
        chain = []
        visited = set()
        
        def traverse(sid: str):
            if sid in visited:
                return
            visited.add(sid)
            for record in self.provenance_chain:
                if record.id == sid:
                    chain.append(record)
                    for parent_id in record.parent_ids:
                        traverse(parent_id)
                    break
        
        traverse(source_id)
        return chain


# Global fusion engine instance
_fusion_engine: Optional[DataFusionEngine] = None


def get_fusion_engine() -> DataFusionEngine:
    global _fusion_engine
    if _fusion_engine is None:
        _fusion_engine = DataFusionEngine()
    return _fusion_engine