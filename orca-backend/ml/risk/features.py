"""Marine risk features. Returns probability + calibration metadata; never a safety verdict."""
from ml.common.schemas import RISK_FEATURES, RiskFeatureVector

__all__ = ["RISK_FEATURES", "RiskFeatureVector", "build_risk_vector"]


def build_risk_vector(**kwargs) -> RiskFeatureVector:
    return RiskFeatureVector(**kwargs)
