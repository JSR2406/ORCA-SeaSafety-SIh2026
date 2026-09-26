"""Fishing suitability features. Inference list MUST equal training list."""
from ml.common.schemas import FISHING_FEATURES, FishingFeatureVector

__all__ = ["FISHING_FEATURES", "FishingFeatureVector", "build_fishing_vector"]


def build_fishing_vector(**kwargs) -> FishingFeatureVector:
    return FishingFeatureVector(**kwargs)
