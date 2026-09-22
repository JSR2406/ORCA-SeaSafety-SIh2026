# Confidence Scoring
# Transparent confidence calculation with explainable components

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.schemas.evidence import ConfidenceScore, ConfidenceComponents, ConfidenceLabel, DataFreshness

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """Calculates transparent confidence scores for query results."""

    def __init__(self, evidence: Dict[str, Any], query_result: Dict[str, Any]):
        self.evidence = evidence
        self.query_result = query_result
        self.metadata = query_result.get("metadata", {})
        self.profiles = query_result.get("profiles", [])

    def calculate(self) -> ConfidenceScore:
        """Calculate all confidence components and overall score."""
        components = ConfidenceComponents(
            spatial_coverage=self._calc_spatial_coverage(),
            temporal_freshness=self._calc_temporal_freshness(),
            sample_density=self._calc_sample_density(),
            measurement_quality=self._calc_measurement_quality(),
            method_stability=self._calc_method_stability(),
        )

        # Weighted average (can be adjusted)
        weights = {
            "spatial_coverage": 0.25,
            "temporal_freshness": 0.20,
            "sample_density": 0.20,
            "measurement_quality": 0.20,
            "method_stability": 0.15,
        }

        score = sum(
            getattr(components, k) * w
            for k, w in weights.items()
        )

        label = self._score_to_label(score)
        explanation = self._generate_explanation(components, score)
        limitations = self._identify_limitations(components)

        return ConfidenceScore(
            label=label,
            score=round(score, 2),
            components=components,
            explanation=explanation,
            limitations=limitations,
        )

    def _calc_spatial_coverage(self) -> float:
        """How well do the floats cover the requested region?"""
        if not self.profiles:
            return 0.0

        # For named regions, check coverage
        region = self.evidence.get("region", {})
        if region.get("type") == "named_region":
            # Simplified: score based on number of floats
            float_count = self.metadata.get("float_count", 0)
            if float_count >= 10:
                return 0.9
            elif float_count >= 5:
                return 0.7
            elif float_count >= 2:
                return 0.5
            elif float_count >= 1:
                return 0.3
            return 0.1

        # For bbox/radius, check if profiles span the region
        if region.get("type") in ["bbox", "radius"]:
            lats = [p["latitude"] for p in self.profiles]
            lons = [p["longitude"] for p in self.profiles]
            if not lats:
                return 0.0
            
            lat_span = max(lats) - min(lats)
            lon_span = max(lons) - min(lons)
            
            if region.get("type") == "bbox":
                req_lat_span = region.get("max_lat", 0) - region.get("min_lat", 0)
                req_lon_span = region.get("max_lon", 0) - region.get("min_lon", 0)
                lat_cov = min(lat_span / max(req_lat_span, 0.1), 1.0)
                lon_cov = min(lon_span / max(req_lon_span, 0.1), 1.0)
                return (lat_cov + lon_cov) / 2
            
            return 0.6  # radius - moderate coverage

        return 0.5

    def _calc_temporal_freshness(self) -> float:
        """How recent is the data?"""
        freshness = self.evidence.get("data_freshness", {})
        days_old = freshness.get("days_old", 999)
        source = freshness.get("source", "unknown")

        if source == "climatology":
            return 0.3  # Climatology is not current
        if source == "reanalysis":
            return 0.5
        if source == "demo":
            return 0.2

        if days_old <= 7:
            return 1.0
        elif days_old <= 30:
            return 0.8
        elif days_old <= 90:
            return 0.5
        elif days_old <= 180:
            return 0.3
        else:
            return 0.1

    def _calc_sample_density(self) -> float:
        """Are there enough profiles/observations for statistical significance?"""
        profile_count = self.metadata.get("profile_count", 0)
        obs_count = self.metadata.get("observation_count", 0)
        float_count = self.metadata.get("float_count", 0)

        # Score based on profile count (minimum for basic stats)
        if profile_count >= 100:
            profile_score = 1.0
        elif profile_count >= 50:
            profile_score = 0.8
        elif profile_count >= 20:
            profile_score = 0.6
        elif profile_count >= 10:
            profile_score = 0.4
        elif profile_count >= 5:
            profile_score = 0.2
        else:
            profile_score = 0.1

        # Float diversity bonus
        if float_count >= 10:
            float_score = 1.0
        elif float_count >= 5:
            float_score = 0.8
        elif float_count >= 2:
            float_score = 0.5
        else:
            float_score = 0.3

        return (profile_score + float_score) / 2

    def _calc_measurement_quality(self) -> float:
        """Quality of measurements (QC flags, completeness)."""
        if not self.profiles:
            return 0.0

        # Check QC status
        qc_filters = self.evidence.get("quality_filters", {})
        filters = qc_filters.get("filters", [])
        
        if "good_only" in filters:
            base_score = 1.0
        elif "recommended" in filters:
            base_score = 0.85
        else:
            base_score = 0.5

        # Check data completeness
        total_obs = sum(len(p.get("observations", [])) for p in self.profiles)
        if total_obs == 0:
            return 0.0

        # Count non-null measurements
        temp_obs = sum(1 for p in self.profiles for obs in p.get("observations", []) if obs.get("temperature_c") is not None)
        sal_obs = sum(1 for p in self.profiles for obs in p.get("observations", []) if obs.get("salinity_psu") is not None)
        
        completeness = (temp_obs + sal_obs) / (2 * total_obs) if total_obs > 0 else 0
        
        return base_score * (0.5 + 0.5 * completeness)

    def _calc_method_stability(self) -> float:
        """Stability of the analysis method (fixed for deterministic queries)."""
        # For deterministic query tools, method stability is high
        intent = self.evidence.get("intent", "unknown")
        if intent in ["profile_search", "timeseries_summary", "depth_profile_summary"]:
            return 0.95
        elif intent in ["anomaly_detection", "compare_baseline"]:
            return 0.8
        elif intent in ["scenario_projection"]:
            return 0.5  # Projections inherently uncertain
        elif intent == "marine_condition_briefing":
            return 0.6  # Depends on forecast availability
        return 0.7

    def _score_to_label(self, score: float) -> ConfidenceLabel:
        if score >= 0.75:
            return ConfidenceLabel.HIGH
        elif score >= 0.45:
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LOW

    def _generate_explanation(self, components: ConfidenceComponents, score: float) -> str:
        """Generate human-readable explanation."""
        parts = []
        
        if components.spatial_coverage >= 0.7:
            parts.append("Good spatial coverage")
        elif components.spatial_coverage >= 0.4:
            parts.append("Moderate spatial coverage")
        else:
            parts.append("Limited spatial coverage")

        if components.temporal_freshness >= 0.7:
            parts.append("Recent data")
        elif components.temporal_freshness >= 0.4:
            parts.append("Moderately recent data")
        else:
            parts.append("Older data")

        if components.sample_density >= 0.7:
            parts.append("Many profiles")
        elif components.sample_density >= 0.4:
            parts.append("Moderate number of profiles")
        else:
            parts.append("Few profiles")

        if components.measurement_quality >= 0.8:
            parts.append("High-quality measurements")
        elif components.measurement_quality >= 0.5:
            parts.append("Standard quality measurements")
        else:
            parts.append("Lower quality measurements")

        return f"{'; '.join(parts)}. Overall confidence: {score:.0%}."

    def _identify_limitations(self, components: ConfidenceComponents) -> List[str]:
        """Identify specific limitations."""
        limitations = []
        
        if components.spatial_coverage < 0.5:
            limitations.append("Sparse spatial coverage - results may not represent the full region")
        if components.temporal_freshness < 0.5:
            limitations.append("Data is not current - conditions may have changed")
        if components.sample_density < 0.4:
            limitations.append("Low sample count - statistical uncertainty is high")
        if components.measurement_quality < 0.6:
            limitations.append("Measurement quality concerns - some data may be unreliable")
        if components.method_stability < 0.6:
            limitations.append("Method has inherent uncertainty (e.g., projection, forecast)")

        # Data-specific limitations
        if self.metadata.get("float_count", 0) < 3:
            limitations.append("Very few floats (<3) - high spatial sampling uncertainty")
        
        return limitations