# Phase 5 - evidence graph + provenance trail.
#
# Lightweight provenance model linking claims -> evidence bundles -> sources,
# plus the freshness labels the verifier uses, so the response can show *why*
# the system believes what it believes.
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceNode:
    """One verified fact underpinning a claim."""
    claim_id: str
    claim: str
    value: Any
    unit: str
    kind: str                       # measurement | aggregation | comparison | projection | climatology
    source: str
    source_record_id: str
    freshness: str                  # fresh | aging | stale | expired | unknown
    verified: bool
    confidence_label: str = "high"
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "value": self.value,
            "unit": self.unit,
            "kind": self.kind,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "freshness": self.freshness,
            "verified": self.verified,
            "confidence": self.confidence_label,
            "limitations": self.limitations,
        }


class EvidenceGraph:
    """Builds the claim -> bundle -> source provenance graph per query."""

    def __init__(self) -> None:
        self._nodes: List[EvidenceNode] = []

    def add(self, node: EvidenceNode) -> str:
        self._nodes.append(node)
        return node.claim_id

    def add_claim(
        self,
        claim: str,
        value: Any,
        unit: str,
        source: str,
        source_record_id: str = "",
        freshness: str = "unknown",
        kind: str = "measurement",
        verified: bool = True,
    ) -> str:
        claim_id = "cl-" + hashlib.sha1(
            f"{claim}:{source}:{source_record_id}".encode("utf-8")
        ).hexdigest()[:10]
        node = EvidenceNode(
            claim_id=claim_id,
            claim=claim,
            value=value,
            unit=unit,
            source=source,
            source_record_id=source_record_id,
            freshness=freshness,
            verified=verified,
            kind=kind,
        )
        self.add(node)
        return claim_id

    def add_numeric_claim(self, claim: str, value: float, unit: str,
                          source: str, source_record_id: str = "",
                          freshness: str = "unknown") -> str:
        return self.add_claim(claim, value, unit, source, source_record_id,
                              freshness, kind="measurement")

    def nodes(self) -> List[EvidenceNode]:
        return list(self._nodes)

    def claims(self) -> List[Dict[str, Any]]:
        return [n.to_dict() for n in self._nodes]

    def sources(self) -> List[Dict[str, Any]]:
        by_source: Dict[str, Dict[str, Any]] = {}
        for n in self._nodes:
            entry = by_source.setdefault(n.source, {
                "source": n.source,
                "source_record_ids": [],
                "freshness": n.freshness,
                "verified": n.verified,
                "claim_count": 0,
            })
            if n.source_record_id and n.source_record_id not in entry["source_record_ids"]:
                entry["source_record_ids"].append(n.source_record_id)
            if n.freshness == "expired":
                entry["freshness"] = "expired"
            elif n.freshness == "stale" and entry["freshness"] not in ("stale", "expired"):
                entry["freshness"] = "stale"
            elif n.freshness == "aging" and entry["freshness"] not in ("stale", "expired", "aging"):
                entry["freshness"] = "aging"
            entry["verified"] = entry["verified"] and n.verified
            entry["claim_count"] += 1
        return sorted(by_source.values(), key=lambda s: s["claim_count"], reverse=True)

    def legacy_claims_dict(self) -> Dict[str, Any]:
        """Bundle shape used by pre-existing Verifier/NumericClaim code paths."""
        return {"claims": self.claims(), "sources": self.sources()}

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": self.claims(), "sources": self.sources()}

    @staticmethod
    def merge(graphs: List["EvidenceGraph"]) -> "EvidenceGraph":
        merged = EvidenceGraph()
        for graph in graphs:
            for node in graph.nodes():
                merged.add(node)
        return merged