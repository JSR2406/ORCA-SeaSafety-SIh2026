"""Metric contract for time-based benchmarking. No random-split-only validation."""
from typing import Dict, List

REQUIRED_METRICS: List[str] = [
    "roc_auc", "pr_auc", "f1", "precision", "recall", "brier", "confusion_matrix",
]


def time_split_note(train: str, valid: str, test: str) -> Dict[str, str]:
    return {"train": train, "validation": valid, "test": test,
            "policy": "time-based split; random split alone is not sufficient (spatial/temporal leakage)"}


def empty_report(model: str, version: str = "untrained") -> Dict:
    return {"model": model, "version": version, "status": "untrained",
            "metrics": {k: None for k in REQUIRED_METRICS}}
