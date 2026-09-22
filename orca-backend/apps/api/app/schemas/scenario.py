# Scenario Schema
# What-if projection and scenario comparison schemas

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class ScenarioType(str, Enum):
    """Types of what-if scenarios."""
    DEPARTURE_TIME_CHANGE = "departure_time_change"
    ROUTE_VARIANT = "route_variant"
    WEATHER_VARIATION = "weather_variation"
    SPEED_ADJUSTMENT = "speed_adjustment"
    CLIMATE_PROJECTION = "climate_projection"
    STORM_AVOIDANCE = "storm_avoidance"


class ScenarioParameter(BaseModel):
    """Individual parameter for scenario."""
    name: str
    value: Any
    unit: Optional[str] = None
    description: str


class ScenarioRequest(BaseModel):
    """Request to create a what-if scenario."""
    scenario_type: ScenarioType
    base_query: Dict[str, Any]  # Original route/query parameters
    parameters: List[ScenarioParameter]
    name: Optional[str] = None
    description: Optional[str] = None


class ScenarioResult(BaseModel):
    """Result of a scenario projection."""
    scenario_id: str
    scenario_type: ScenarioType
    name: Optional[str]
    created_at: datetime
    
    # Projected changes
    projected_risk_score: float
    projected_time_hours: Optional[float] = None
    projected_fuel_consumption: Optional[float] = None
    
    # Comparison with baseline
    risk_delta: float
    time_delta_hours: Optional[float] = None
    fuel_delta: Optional[float] = None
    
    # Environmental projections
    projected_conditions: Dict[str, Any]
    
    # Confidence
    confidence: float
    uncertainty_factors: List[str]
    
    # Recommendations
    recommendations: List[str]


class ScenarioComparison(BaseModel):
    """Comparison between multiple scenarios."""
    comparison_id: str
    base_scenario: ScenarioResult
    alternative_scenarios: List[ScenarioResult]
    created_at: datetime
    
    # Summary
    best_scenario_id: str
    worst_scenario_id: str
    key_differences: List[str]
    
    # Trade-offs
    tradeoffs: List[Dict[str, Any]]


# Alert Schema
class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class AlertRule(BaseModel):
    """Rule for triggering alerts."""
    rule_id: str
    name: str
    description: str
    
    # Trigger conditions
    hazard_types: Optional[List[str]] = None
    severity_threshold: Optional[str] = None
    region: Optional[Dict[str, float]] = None  # lat, lon, radius_km
    route_id: Optional[str] = None
    
    # Schedule
    active_from: Optional[datetime] = None
    active_to: Optional[datetime] = None
    check_interval_minutes: int = 60
    
    # Actions
    notify_channels: List[str] = Field(default_factory=list)  # email, sms, push, webhook
    auto_resolve: bool = True
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str
    enabled: bool = True


class AlertEvent(BaseModel):
    """Individual alert occurrence."""
    event_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    
    # Trigger details
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    trigger_reason: str
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Location
    location: Optional[Dict[str, float]] = None  # lat, lon
    
    # Resolution
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    # Notification tracking
    notifications_sent: List[Dict[str, Any]] = Field(default_factory=list)


# Global storage
_alert_rules: Dict[str, AlertRule] = {}
_alert_events: Dict[str, AlertEvent] = {}
_scenario_results: Dict[str, ScenarioResult] = {}
_scenario_comparisons: Dict[str, ScenarioComparison] = {}


def create_alert_rule(rule: AlertRule) -> AlertRule:
    _alert_rules[rule.rule_id] = rule
    return rule


def get_alert_rule(rule_id: str) -> Optional[AlertRule]:
    return _alert_rules.get(rule_id)


def list_alert_rules(enabled_only: bool = True) -> List[AlertRule]:
    rules = list(_alert_rules.values())
    if enabled_only:
        rules = [r for r in rules if r.enabled]
    return rules


def create_alert_event(event: AlertEvent) -> AlertEvent:
    _alert_events[event.event_id] = event
    return event


def get_alert_event(event_id: str) -> Optional[AlertEvent]:
    return _alert_events.get(event_id)


def list_alert_events(
    status: Optional[AlertStatus] = None,
    severity: Optional[str] = None,
    limit: int = 100,
) -> List[AlertEvent]:
    events = list(_alert_events.values())
    
    if status:
        events = [e for e in events if e.status == status]
    if severity:
        events = [e for e in events if e.severity == severity]
    
    events.sort(key=lambda e: e.triggered_at, reverse=True)
    return events[:limit]


def acknowledge_alert(event_id: str, user: str) -> Optional[AlertEvent]:
    event = _alert_events.get(event_id)
    if event:
        event.status = AlertStatus.ACKNOWLEDGED
        event.acknowledged_at = datetime.utcnow()
        event.acknowledged_by = user
    return event


def resolve_alert(event_id: str, user: str, notes: Optional[str] = None) -> Optional[AlertEvent]:
    event = _alert_events.get(event_id)
    if event:
        event.status = AlertStatus.RESOLVED
        event.resolved_at = datetime.utcnow()
        event.resolution_notes = notes
    return event


# Scenario storage
def create_scenario_result(result: ScenarioResult) -> ScenarioResult:
    _scenario_results[result.scenario_id] = result
    return result


def get_scenario_result(scenario_id: str) -> Optional[ScenarioResult]:
    return _scenario_results.get(scenario_id)


def create_scenario_comparison(comparison: ScenarioComparison) -> ScenarioComparison:
    _scenario_comparisons[comparison.comparison_id] = comparison
    return comparison


def get_scenario_comparison(comparison_id: str) -> Optional[ScenarioComparison]:
    return _scenario_comparisons.get(comparison_id)