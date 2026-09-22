# Phase 12 - model registry.
#
# A versioned registry owning the production model lifecycle:
#
#   CANDIDATE  (registered, not yet trusted)
#   VALIDATED  (passed offline/validation metrics)
#   PRODUCTION (served by the model service)
#   DEPRECATED (retired; kept for provenance, no longer served)
#
# Rollback: promoting a model to PRODUCTION records the previous production
# version so a regression can be rolled back to the last-known-good model.
# The registry is bounded (candidate window capped) and never invents metrics.
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class ModelStage(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


@dataclass
class ModelVersion:
    name: str                       # e.g. "pfz", "risk", "productivity", "forecast"
    version: str                    # semantic version, e.g. "1.0.0"
    stage: ModelStage = ModelStage.CANDIDATE
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    metrics: Dict[str, Any] = field(default_factory=dict)
    card: Dict[str, Any] = field(default_factory=dict)
    parent_version: Optional[str] = None   # model this was trained on top of
    sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "stage": self.stage.value,
            "created_at": self.created_at.isoformat(),
            "metrics": self.metrics,
            "card": self.card,
            "parent_version": self.parent_version,
            "sha256": self.sha256,
        }


class ModelRegistry:
    """Bounded registry of model versions with lifecycle transitions."""

    def __init__(self, max_candidates: int = 8) -> None:
        self.max_candidates = max_candidates
        self.versions: Dict[str, ModelVersion] = {}   # f"{name}@{version}"
        self.production: Dict[str, str] = {}          # name -> active version
        self.previous_production: Dict[str, str] = {} # name -> prior (rollback)
        self.history: List[Dict[str, Any]] = []
        self._candidate_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------ api
    def _key(self, name: str, version: str) -> str:
        return f"{name}@{version}"

    def register(self, name: str, version: str, *, metrics=None, card=None,
                 parent_version=None, sha256=None) -> ModelVersion:
        key = self._key(name, version)
        if key in self.versions:
            raise ValueError(f"model {key} already registered")
        mv = ModelVersion(
            name=name, version=version, stage=ModelStage.CANDIDATE,
            metrics=metrics or {}, card=card or {},
            parent_version=parent_version, sha256=sha256)
        self.versions[key] = mv
        self._candidate_counts[name] = self._candidate_counts.get(name, 0) + 1
        self._record(name, version, ModelStage.CANDIDATE)
        self._trim_candidates(name)
        return mv

    def validate(self, name: str, version: str, metrics: Dict[str, Any]) -> ModelVersion:
        mv = self._require(name, version)
        mv.stage = ModelStage.VALIDATED
        mv.metrics = {**mv.metrics, **metrics}
        self._record(name, version, ModelStage.VALIDATED)
        return mv

    def promote(self, name: str, version: str, *, require_validated=True) -> ModelVersion:
        mv = self._require(name, version)
        if require_validated and mv.stage not in (ModelStage.VALIDATED,
                                                  ModelStage.PRODUCTION):
            raise ValueError(f"{name}@{version} must be VALIDATED to promote")
        prior = self.production.get(name)
        self.previous_production[name] = prior
        mv.stage = ModelStage.PRODUCTION
        self.production[name] = version
        # demote the previously-active production model to validated
        if prior and prior != version:
            old = self.versions.get(self._key(name, prior))
            if old is not None and old.stage == ModelStage.PRODUCTION:
                old.stage = ModelStage.VALIDATED
        self._record(name, version, ModelStage.PRODUCTION)
        return mv

    def rollback(self, name: str) -> Optional[ModelVersion]:
        prior = self.previous_production.get(name)
        if prior is None:
            return None
        current = self.production.get(name)
        self.production[name] = prior
        cur = self.versions.get(self._key(name, prior))
        if cur is not None:
            cur.stage = ModelStage.PRODUCTION
        if current and cur is not None and current != prior:
            old = self.versions.get(self._key(name, current))
            if old is not None:
                old.stage = ModelStage.VALIDATED
        self.previous_production[name] = current or prior
        self._record(name, prior, ModelStage.PRODUCTION, rollback=True)
        return cur

    def deprecate(self, name: str, version: str) -> ModelVersion:
        mv = self._require(name, version)
        mv.stage = ModelStage.DEPRECATED
        if self.production.get(name) == version:
            del self.production[name]
        self._record(name, version, ModelStage.DEPRECATED)
        return mv

    def get(self, name: str, version: str) -> Optional[ModelVersion]:
        return self.versions.get(self._key(name, version))

    def production_version(self, name: str) -> Optional[ModelVersion]:
        version = self.production.get(name)
        if version is None:
            return None
        return self.versions.get(self._key(name, version))

    def list(self, name: Optional[str] = None) -> List[ModelVersion]:
        out = [v for k, v in self.versions.items()
               if name is None or v.name == name]
        out.sort(key=lambda v: v.created_at)
        return out

    # -------------------------------------------------------------- internal
    def _require(self, name: str, version: str) -> ModelVersion:
        mv = self.versions.get(self._key(name, version))
        if mv is None:
            raise KeyError(f"unknown model {name}@{version}")
        return mv

    def _record(self, name, version, stage, rollback=False) -> None:
        self.history.append({
            "name": name, "version": version, "stage": stage.value,
            "rollback": rollback,
            "at": datetime.now().astimezone().isoformat(),
        })

    def _trim_candidates(self, name: str) -> None:
        count = self._candidate_counts[name]
        if count <= self.max_candidates:
            return
        candidates = [v for v in self.list(name)
                      if v.stage == ModelStage.CANDIDATE]
        # evict oldest non-production candidates beyond the cap
        to_evict = sorted(candidates,
                          key=lambda v: v.created_at)[:-self.max_candidates]
        for mv in to_evict:
            mv.stage = ModelStage.DEPRECATED
            self._candidate_counts[name] -= 1
            self._record(name, mv.version, ModelStage.DEPRECATED)

    def stats(self) -> Dict[str, Any]:
        return {
            "count": len(self.versions),
            "production": dict(self.production),
            "history_len": len(self.history),
        }

    # ------------------------------------------------------- state persistence
    def to_snapshot(self) -> Dict[str, Any]:
        """JSON-serializable registry state (versions + active production)."""
        return {
            "versions": {key: v.to_dict() for key, v in self.versions.items()},
            "production": dict(self.production),
            "previous_production": dict(self.previous_production),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any],
                      max_candidates: int = 8) -> "ModelRegistry":
        """Reconstruct a registry from a persisted snapshot."""
        reg = cls(max_candidates=max_candidates)
        for key, data in (snapshot.get("versions") or {}).items():
            name, _, version = key.rpartition("@")
            reg.versions[key] = ModelVersion(
                name=name, version=version,
                stage=ModelStage(data.get("stage", "candidate")),
                created_at=datetime.fromisoformat(data["created_at"]),
                metrics=data.get("metrics") or {},
                card=data.get("card") or {},
                parent_version=data.get("parent_version"),
                sha256=data.get("sha256"))
            if reg.versions[key].stage == ModelStage.CANDIDATE:
                reg._candidate_counts[name] = reg._candidate_counts.get(name, 0) + 1
        reg.production = dict(snapshot.get("production") or {})
        reg.previous_production = dict(snapshot.get("previous_production") or {})
        return reg

    def persist(self, path: Optional[str] = None) -> Optional[str]:
        """Write the registry snapshot to disk (returns the path or None)."""
        import json
        import os
        if path is None:
            from app.config import settings
            path = getattr(settings, "ml_registry_path", None)
        if not path:
            return None
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_snapshot(), fh, indent=2, default=str)
        return path


def load_registry_state(path: Optional[str]) -> Dict[str, Any]:
    """Read a persisted registry snapshot, or {} when absent/corrupt."""
    import json
    import os
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001 - corrupt snapshot -> fresh registry
        return {}


_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        from app.config import settings
        state = load_registry_state(settings.ml_registry_path)
        if state:
            _registry = ModelRegistry.from_snapshot(
                state, max_candidates=settings.model_registry_max_candidates)
        else:
            _registry = ModelRegistry(
                max_candidates=settings.model_registry_max_candidates)
    return _registry