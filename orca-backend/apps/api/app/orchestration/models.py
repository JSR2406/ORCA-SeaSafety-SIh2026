# Agentic orchestration - core data models (Phase 4).
#
# These are pure dataclasses; no DB or network.  The plan vocabulary is
# data-driven (capability matrix) so the orchestrator is never a keyword router.
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class IntentName(str, Enum):
    BRIEFING = "briefing"
    SAFETY = "safety"
    FISHING = "fishing"
    ROUTE = "route"
    SCENARIO = "scenario"
    KNOWLEDGE = "knowledge"
    PFZ = "pfz"
    PRODUCTIVITY = "productivity"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Intent:
    name: IntentName
    language: str = "en-IN"
    location: Optional[Dict[str, Any]] = None   # {"lat","lon","label"} | None
    origin: Optional[Dict[str, Any]] = None     # route origin (from X)
    time: str = "now"
    target: str = "fishing"
    query: str = ""                             # raw user text
    needs: List[str] = field(default_factory=list)
    confidence: float = 0.7
    origin_raw: str = ""
    merged_from_context: bool = False
    offset: Optional[Dict[str, Any]] = None   # {"km","direction","anchor_label","applied"}
    route: Optional[List[Tuple[float, float]]] = None  # waypoints for route intent

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Task:
    task_id: str
    agent: str
    tool: Optional[str] = None                   # MCP tool name (data tasks)
    domain_step: Optional[str] = None            # verifier | scenario (local)
    depends_on: List[str] = field(default_factory=list)
    required: bool = True
    max_retries: int = 2
    timeout_seconds: float = 30.0
    safety_step: bool = False
    args: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    retry_count: int = 0


@dataclass
class Plan:
    intent: Intent
    tasks: List[Task] = field(default_factory=list)
    strategy: str = "capability_matrix"
    safety: bool = False

    def by_id(self, task_id: str) -> Optional[Task]:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None


@dataclass
class ValidationResult:
    ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add(self, error: str) -> None:
        self.ok = False
        self.errors.append(error)


@dataclass
class ExecutionResult:
    status: str = "pending"                      # success | partial | aborted
    tasks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    tool_calls: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    repairs: List[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class AgentSpec:
    name: str
    description: str
    capabilities: List[str]
    tools: List[str] = field(default_factory=list)   # MCP tools this agent may call
    domain: Optional[str] = None                     # allowed deterministic step
    priority: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__