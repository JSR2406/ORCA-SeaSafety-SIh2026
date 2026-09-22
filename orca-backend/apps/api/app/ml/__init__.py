# Phase 12 - production ML, forecasting and MLOps.
# Phase 13 - continuous learning, model governance & ML provenance.
from app.ml.features import FeatureStore, get_feature_store  # noqa: F401
from app.ml.registry import ModelRegistry, ModelStage, get_model_registry  # noqa: F401
from app.ml.drift import DriftDetector, get_drift_detector  # noqa: F401
from app.ml.models import Prediction  # noqa: F401
from app.ml.service import ModelService, get_model_service, reset_model_singletons  # noqa: F401
from app.ml.ledger import (  # noqa: F401
    ObservedOutcome, PredictionLedger, PredictionOutcomeMatcher,
)
from app.ml.eval import MultiWindowEvaluator, RollingEvaluator  # noqa: F401
from app.ml.dataset import DatasetBuilder, TrainingDataset  # noqa: F401
from app.ml.governance import (  # noqa: F401
    GovernanceEngine, RetrainingPolicyEngine, build_ml_provenance_contract,
    get_governance_engine, reset_governance_singletons,
)
from app.ml.governance_events import (  # noqa: F401
    LearningEventBus, emit_learning_event, get_event_bus, reset_event_bus,
)

__all__ = [
    "DatasetBuilder", "DriftDetector", "FeatureStore", "GovernanceEngine",
    "LearningEventBus", "ModelRegistry", "ModelService", "ModelStage",
    "MultiWindowEvaluator", "ObservedOutcome", "Prediction", "PredictionLedger",
    "PredictionOutcomeMatcher", "RetrainingPolicyEngine", "RollingEvaluator",
    "TrainingDataset", "build_ml_provenance_contract", "emit_learning_event",
    "get_drift_detector", "get_event_bus", "get_feature_store",
    "get_governance_engine", "get_model_registry", "get_model_service",
    "reset_event_bus", "reset_governance_singletons", "reset_model_singletons",
]