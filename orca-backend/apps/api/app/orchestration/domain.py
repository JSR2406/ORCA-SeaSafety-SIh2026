# Deterministic domain steps (Phase 4).
#
# These are pure computation, run by the executor over evidence the MCP tools
# returned.  They never invent the underlying measurements.
from typing import Any, Dict, List


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _collect_evidence_numbers(evidence: Dict[str, Any],
                              seen: set) -> List[float]:
    """Collect every numeric leaf inside tool results (for claim tracing)."""
    numbers: List[float] = []
    if isinstance(evidence, dict):
        for key, value in evidence.items():
            if _is_number(value):
                numbers.append(float(value))
            elif isinstance(value, (dict, list)):
                numbers.extend(_collect_evidence_numbers(value, seen))
    elif isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, (dict, list)):
                numbers.extend(_collect_evidence_numbers(item, seen))
            elif _is_number(item):
                numbers.append(float(item))
    return numbers


def verify_claims(claims: List[Dict[str, Any]],
                  evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic source-trace verification.

    Each claim has {"name", "value"}.  A claim is verified when the exact value
    (absolute tolerance <= 0.001) appears somewhere in the tool results that
    were returned for this run - nothing is ever verified against an invented
    number.
    """
    if not claims:
        return {"verified": True, "all_verified": True, "checked": 0,
                "failed_claims": []}
    source_numbers = _collect_evidence_numbers(evidence, set())
    failed = []
    for claim in claims:
        value = claim.get("value")
        name = claim.get("name", "?")
        if not _is_number(value):
            failed.append({"name": name, "reason": "claim value not numeric"})
            continue
        if not any(abs(source - float(value)) <= 0.001
                   for source in source_numbers):
            failed.append({"name": name, "reason":
                           "claim value not traceable to tool output"})
    all_verified = not failed
    return {
        "verified": all_verified,
        "all_verified": all_verified,
        "checked": len(claims),
        "failed_claims": failed,
    }


def extract_claims(intent_name: str, evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Draft the numeric claims a response about `intent_name` would surface,
    pulled verbatim from the collected tool results."""
    claims: List[Dict[str, Any]] = []

    def walk(bucket: Dict[str, Any]):
        for key, value in bucket.items():
            if _is_number(value):
                claims.append({"name": key, "value": value})
            elif isinstance(value, dict):
                walk(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                walk(value[0])

    for tool, payload in evidence.items():
        if isinstance(payload, dict):
            walk(payload)
    # Deduplicate by name/value.
    unique: Dict[str, float] = {}
    for claim in claims:
        unique.setdefault(claim["name"], claim["value"])
    return [{"name": k, "value": v} for k, v in sorted(unique.items())][:12]