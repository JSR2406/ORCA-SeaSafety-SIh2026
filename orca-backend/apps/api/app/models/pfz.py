# Canonical PFZ (Potential Fishing Zone) contract.
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.common import GeographicPoint, QualityStatus, utcnow


class PFZZone(BaseModel):
    """A Potential Fishing Zone polygon.

    geometry is stored as GeoJSON dict on the canonical model; the persistence
    layer stores it as PostGIS geometry.
    """
    geometry: Dict  # GeoJSON geometry (Polygon/MultiPolygon)
    centroid: GeographicPoint
    generated_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    species: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict = Field(default_factory=dict)
    source_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=utcnow)

    source: str
    source_record_id: Optional[str] = None
    quality: QualityStatus = QualityStatus.VALID
    raw_payload: Optional[dict] = None