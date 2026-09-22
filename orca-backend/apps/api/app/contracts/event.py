# Streaming event contract (Phase 10 - Part 17, 43).
#
# A WebSocket / SSE-compatible envelope for long-running orchestration.  Only
# safe execution metadata is streamed - never secrets, internal prompts, or
# hidden reasoning.
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.contracts.versions import contract_meta


class EventType(str, Enum):
    RUN_STARTED = "run.started"
    PLAN_CREATED = "plan.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    FUSION_COMPLETED = "fusion.completed"
    RISK_COMPLETED = "risk.completed"
    VERIFICATION_COMPLETED = "verification.completed"
    ALERT_CREATED = "alert.created"
    ALERT_UPDATED = "alert.updated"
    ALERT_EXPIRED = "alert.expired"
    RESPONSE_READY = "response.ready"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


class StreamEvent(BaseModel):
    run_id: str
    timestamp: str
    event: EventType = EventType.RUN_STARTED
    status: str = "ok"
    task_id: Optional[str] = None
    agent: Optional[str] = None
    tool: Optional[str] = None
    session_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    event_schema_version: str = contract_meta()["event_schema_version"]

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "event": self.event.value,
            "status": self.status,
            "task_id": self.task_id,
            "agent": self.agent,
            "tool": self.tool,
            "session_id": self.session_id,
            "data": self.data,
            "event_schema_version": self.event_schema_version,
        }
