"""Anomaly inference stub — returns not-anomalous until a fitted model is registered."""
from ml.common.schemas import ModelPrediction


def predict_anomaly(feature_values: dict, version: str = "untrained") -> ModelPrediction:
    return ModelPrediction(model="marine_anomaly", version=version, probability=0.0,
                           label="unknown", feature_values=feature_values,
                           calibration={"status": "untrained-isolation-forest-stub"})
