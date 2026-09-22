# Deterministic dedup support for idempotent ingestion.
# Records with a durable source_record_id are deduped by (source, record_id).
# Records without one get a canonical content hash so re-ingestion of identical
# payloads is idempotent.
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence


def _jsonable_iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):  # enum
        return value.value
    if isinstance(value, dict):
        return {k: _jsonable_iso(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_iso(v) for v in value]
    return value


def canonical_hash(record: Any) -> str:
    """SHA-256 over a stable serialization of the canonical record (except
    ingested_at/raw_payload which vary across time)."""
    if isinstance(record, dict):
        payload = record
    elif hasattr(record, "model_dump"):
        payload = record.model_dump(exclude={"ingested_at", "raw_payload"})
    else:
        payload = vars(record)
    payload = _jsonable_iso(payload)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def ensure_dedup_keys(records: Sequence[Any], source: str) -> List[Any]:
    """Fill source_record_id with a canonical hash when it is absent."""
    out: List[Any] = []
    for record in records:
        if getattr(record, "source_record_id", None):
            out.append(record)
            continue
        record.source_record_id = f"hash:{canonical_hash(record)}"
        out.append(record)
    return out


def dedup_batch(records: Sequence[Any], source: str) -> List[Any]:
    """First-wins dedup within a single batch by the durable key."""
    seen: set[str] = set()
    out: List[Any] = []
    for record in records:
        key = getattr(record, "source_record_id", None) or canonical_hash(record)
        composite = f"{source}:{key}"
        if composite in seen:
            continue
        seen.add(composite)
        out.append(record)
    return out


def dedup_keys_dicts(rows: Sequence[Dict[str, Any]]) -> Optional[set]:
    """Return the set of (source, record_id) keys present in mapped rows."""
    keys = set()
    for row in rows:
        sid = row.get("source_record_id")
        if sid:
            keys.add((row["source"], sid))
    return keys if keys else None