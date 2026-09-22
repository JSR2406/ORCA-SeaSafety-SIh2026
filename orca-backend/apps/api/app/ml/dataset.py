# Phase 13 - reproducible training dataset builder.
#
# A dataset is assembled from: prediction ledger + matched ground truth +
# historical features, with data-quality filters.  Every dataset records
# dataset_id / dataset_version / feature_version / source versions / time and
# spatial range / row count / quality statistics so a trained model can be
# reproduced from (dataset version, feature version, code version, config,
# training params).
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DatasetRow:
    model_name: str
    features: Dict[str, float]
    target: float
    quality: float
    prediction_id: str
    outcome_id: str


@dataclass
class TrainingDataset:
    dataset_id: str
    dataset_version: str
    feature_version: str
    model_name: str
    labels: List[str]
    features: List[Dict[str, float]]
    targets: List[float]
    rows: List[DatasetRow]
    time_range: Optional[Dict[str, str]] = None
    spatial_range: Optional[Dict[str, float]] = None
    quality_stats: Dict[str, Any] = field(default_factory=dict)
    source_versions: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "feature_version": self.feature_version,
            "model_name": self.model_name,
            "labels": self.labels,
            "row_count": len(self.rows),
            "time_range": self.time_range,
            "spatial_range": self.spatial_range,
            "quality_stats": self.quality_stats,
            "source_versions": self.source_versions,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat(),
        }


class DatasetBuilder:
    """Builds a bounded, reproducible training dataset from ledgers + features."""

    def __init__(self, feature_version: str = "1.0.0",
                 quality_min: float = 0.5) -> None:
        self.feature_version = feature_version
        self.quality_min = float(quality_min)
        self.datasets: Dict[str, TrainingDataset] = {}

    def build(self, model_name: str,
              features: List[Dict[str, Any]],
              targets: List[float],
              quality: List[float],
              prediction_ids: List[str],
              outcome_ids: List[str],
              *, labels: Optional[List[str]] = None,
              time_range: Optional[Dict[str, str]] = None,
              spatial_range: Optional[Dict[str, float]] = None,
              feature_version: Optional[str] = None,
              source_versions: Optional[Dict[str, str]] = None) -> TrainingDataset:
        ver = feature_version or self.feature_version
        rows = []
        for i, feat in enumerate(features):
            quality_val = quality[i] if i < len(quality) else 1.0
            if quality_val < self.quality_min:
                continue
            rows.append(DatasetRow(
                model_name=model_name,
                features=feat, target=targets[i], quality=quality_val,
                prediction_id=prediction_ids[i] if i < len(prediction_ids) else "",
                outcome_id=outcome_ids[i] if i < len(outcome_ids) else "",
            ))
        dataset = TrainingDataset(
            dataset_id=f"ds-{uuid.uuid4().hex[:12]}",
            dataset_version=ver,
            feature_version=ver,
            model_name=model_name,
            labels=labels or [],
            features=[r.features for r in rows],
            targets=[r.target for r in rows],
            rows=rows,
            time_range=time_range,
            spatial_range=spatial_range,
            quality_stats={
                "rows": len(rows),
                "filtered_out": len(features) - len(rows),
                "min_quality": round(min(quality, default=0.0), 3),
                "max_quality": round(max(quality, default=0.0), 3),
                "mean_quality": round(
                    sum(quality) / len(quality), 3) if quality else 0.0,
            },
            source_versions=source_versions or {},
            sha256=self._hash([r for r in rows]),
        )
        dataset.sha256 = self._hash([r for r in rows])
        self.datasets[dataset.dataset_id] = dataset
        return dataset

    @staticmethod
    def _hash(rows: List[DatasetRow]) -> str:
        payload = hashlib.sha256()
        for r in rows:
            payload.update(
                (f"{r.model_name}|{r.target}|{sorted(r.features.items())}"
                 f"|{r.quality}").encode("utf-8"))
        return payload.hexdigest()[:24]

    def get(self, dataset_id: str) -> Optional[TrainingDataset]:
        return self.datasets.get(dataset_id)