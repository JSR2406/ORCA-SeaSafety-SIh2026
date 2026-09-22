# Risk briefing schemas
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class RiskComponent(BaseModel):
    name: str
    label: Literal["low", "moderate", "elevated", "unavailable"]
    reason: str
    source: str
    data_freshness: str


class RiskBriefingResponse(BaseModel):
    overall_label: Literal["low", "moderate", "elevated", "unavailable"]
    components: List[RiskComponent]
    confidence: dict
    advisory: str
    data_status: Literal["complete", "partial", "unavailable"]
    latest_data_timestamp: str