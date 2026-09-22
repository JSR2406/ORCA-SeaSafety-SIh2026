# Execution telemetry (Phase 4).
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class TraceEvent:
    kind: str
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "at": self.at.isoformat(),
            "source": self.source,
            "payload": self.payload,
        }


class Tracer:
    """Collects a bounded list of events; stores nothing else."""

    def __init__(self, limit: int = 400):
        self._events: List[TraceEvent] = []
        self.limit = limit

    async def event(self, kind: str, source: str = "",
                    payload: Dict[str, Any] | None = None) -> None:
        if len(self._events) >= self.limit:
            return
        self._events.append(
            TraceEvent(kind=kind, source=source, payload=payload or {}))

    def snapshot(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]