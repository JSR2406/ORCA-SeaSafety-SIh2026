# Phase 6 - shared evidence navigation for the structured-output builders.
#
# Tools hand back envelopes of the shape {"status": "live", "data": {...}}.
# These helpers unwrap them defensively so the map/chart/alert builders see the
# same values the chat answer (synthesis) is drawn from - a single verified
# execution result is the only source of truth for every output channel.
from typing import Any, Dict, List


def unwrap(value: Dict[str, Any]) -> Dict[str, Any]:
    if "data" in value and isinstance(value.get("data"), dict):
        return value["data"]
    return value


def all_dicts(evidence: Dict[str, Any]):
    """Yield every dict one level deep in the evidence (handler bundles often
    nest per-tool output under the task's primary tool key)."""
    for value in evidence.values():
        yield value if isinstance(value, dict) else {}
        if isinstance(value, dict):
            for sub in value.values():
                if isinstance(sub, dict) or isinstance(sub, list):
                    if isinstance(sub, list):
                        for item in sub:
                            if isinstance(item, dict):
                                yield item
                    else:
                        yield sub


def find(evidence: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    """Locate a dict payload at the top level or nested one level deep."""
    for key in keys:
        for bucket in all_dicts(evidence):
            if isinstance(bucket, dict) and key in bucket \
                    and isinstance(bucket[key], dict):
                return unwrap(bucket[key])
        value = evidence.get(key)
        if isinstance(value, dict):
            return unwrap(value)
    return {}


def find_list(evidence: Dict[str, Any], key: str) -> List[Any]:
    for bucket in all_dicts(evidence):
        if isinstance(bucket, dict) and key in bucket \
                and isinstance(bucket[key], list):
            return bucket[key]
    value = evidence.get(key)
    return value if isinstance(value, list) else []


def fused_freshness(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Read the freshness envelope from the fused-state evidence (never invents)."""
    fused = find(evidence, "fused_state", "marine.get_fused_state")
    freshness = fused.get("freshness") if isinstance(fused, dict) else None
    if isinstance(freshness, dict):
        return freshness
    payloads = [p for p in all_dicts(evidence)
                if isinstance(p, dict) and p.get("freshness")]
    if payloads:
        return payloads[0]["freshness"]
    return {"overall": "unknown", "threshold_seconds": None, "per_source": {}}


def fused_source(evidence: Dict[str, Any]) -> str:
    """Provider label for the fused-state evidence, or a fallback family."""
    fused = find(evidence, "fused_state", "marine.get_fused_state")
    sources = fused.get("sources") or []
    if sources:
        return str(sources[0])
    return "fusion"


def risk_level(evidence: Dict[str, Any]) -> str:
    """Deterministic risk level from the risk-profile evidence ('unknown' if absent)."""
    risk = find(evidence, "risk_profile", "analytics.risk_profile")
    level = risk.get("level")
    if not level:
        return "unknown"
    return str(level).lower()