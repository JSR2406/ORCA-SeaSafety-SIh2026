# Phase 5 - deterministic freshness evaluation + data classification.
from datetime import datetime
from typing import Optional, Tuple

from app.models.common import utcnow
from app.models.marine_contract import DataClass, DataFreshness

AGING_MULTIPLE = 2.0


def evaluate_freshness(
    observation_time: Optional[datetime],
    threshold_seconds: Optional[float],
    now: Optional[datetime] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
) -> Tuple[DataFreshness, str]:
    """Freshness of a record at `now`.

    - EXPIRED: validity window ended before now
    - UNKNOWN: record not yet in effect or missing the inputs needed
    - FRESH:   age within the freshness threshold
    - AGING:   age within twice the threshold (usable but flagged)
    - STALE:   age well beyond the threshold (still real data, clearly flagged)
    """
    t = now or utcnow()
    if valid_until is not None and t >= valid_until:
        return DataFreshness.EXPIRED, "validity window has ended"
    if valid_from is not None and t < valid_from:
        return DataFreshness.UNKNOWN, "validity window has not begun"
    if observation_time is None:
        return DataFreshness.UNKNOWN, "no observation time recorded"
    if threshold_seconds is None or threshold_seconds <= 0:
        return DataFreshness.UNKNOWN, "no freshness threshold configured"
    age = max(0.0, (t - observation_time).total_seconds())
    if age <= threshold_seconds:
        return DataFreshness.FRESH, f"{age:.0f}s old within threshold"
    if age <= threshold_seconds * AGING_MULTIPLE:
        return DataFreshness.AGING, f"{age:.0f}s old beyond threshold"
    return DataFreshness.STALE, f"{age:.0f}s old well beyond threshold"


def freshness_from_freshness(
    threshold_seconds: Optional[float],
    age_seconds: Optional[float],
    latest_data_timestamp: Optional[datetime],
    now: Optional[datetime] = None,
) -> Tuple[DataFreshness, str]:
    """Map an existing Freshness (age + threshold) to the Phase 5 states."""
    t = now or utcnow()
    if age_seconds is None:
        return evaluate_freshness(latest_data_timestamp, threshold_seconds, now=t)
    if threshold_seconds is None or threshold_seconds <= 0:
        return DataFreshness.UNKNOWN, "no freshness threshold configured"
    age = max(0.0, age_seconds)
    if age <= threshold_seconds:
        return DataFreshness.FRESH, f"{age:.0f}s old within threshold"
    if age <= threshold_seconds * AGING_MULTIPLE:
        return DataFreshness.AGING, f"{age:.0f}s old beyond threshold"
    return DataFreshness.STALE, f"{age:.0f}s old well beyond threshold"


def classify_data(
    *,
    is_forecast: bool = False,
    is_advisory: bool = False,
    is_derived: bool = False,
    is_model: bool = False,
) -> DataClass:
    if is_model:
        return DataClass.MODEL_PREDICTION
    if is_forecast:
        return DataClass.FORECAST
    if is_advisory:
        return DataClass.ADVISORY
    if is_derived:
        return DataClass.DERIVED_ANALYTICS
    return DataClass.OBSERVATION