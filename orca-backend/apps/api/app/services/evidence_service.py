# MarineEvidenceService - durable evidence/provenance for every fact an agent
# asserts from live marine data.
#
# Stored rows mirror what was actually retrieved from the database layer - the
# service never invents values.  Recording is best-effort: a failed write only
# degrades observability, never the response path.
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.db.client import get_session
from app.db.models import MarineEvidence

logger = logging.getLogger(__name__)


class MarineEvidenceService:
    """Persist (and read back) marine evidence rows."""

    def __init__(self, session_factory: Optional[Callable] = None):
        if session_factory is None:
            session_factory = get_session
        self._session_factory = session_factory

    async def record(
        self,
        *,
        query_run_id: str,
        agent_name: str,
        tool_name: str,
        evidence_type: str,
        source: Optional[str] = None,
        source_record_id: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        observed_at: Optional[datetime] = None,
        severity: Optional[str] = None,
        confidence: Optional[float] = None,
        payload: Optional[dict] = None,
    ) -> int:
        """Insert one evidence row.  Returns the row id, or -1 on failure."""
        try:
            row = MarineEvidence(
                query_run_id=str(query_run_id)[:64],
                agent_name=str(agent_name)[:100],
                tool_name=str(tool_name)[:100],
                evidence_type=str(evidence_type)[:50],
                source=source,
                source_record_id=source_record_id,
                latitude=latitude,
                longitude=longitude,
                observed_at=observed_at,
                severity=severity,
                confidence=confidence,
                payload=payload or {},
                ingested_at=datetime.now(timezone.utc),
            )
            async with self._session_factory() as session:
                session.add(row)
                await session.flush()
                row_id = int(row.id)
                await session.commit()
            return row_id
        except Exception as exc:  # noqa: BLE001 - best-effort observability
            logger.warning("marine evidence record failed: %s", exc)
            return -1

    async def list_for_run(self, query_run_id: str) -> List[Dict[str, Any]]:
        """Return evidence rows for a query run, oldest first."""
        from sqlalchemy import select

        rows: List[Dict[str, Any]] = []
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(MarineEvidence)
                    .where(MarineEvidence.query_run_id == str(query_run_id))
                    .order_by(MarineEvidence.id.asc())
                )
                for obj in result.scalars().all():
                    rows.append(self._to_dict(obj))
        except Exception as exc:  # noqa: BLE001 - read path stays non-fatal
            logger.warning("marine evidence list failed: %s", exc)
        return rows

    async def count(self) -> int:
        """Total stored evidence rows (for health/observability)."""
        from sqlalchemy import func, select

        try:
            async with self._session_factory() as session:
                total = await session.scalar(select(func.count()).select_from(MarineEvidence))
                return int(total or 0)
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _to_dict(obj: MarineEvidence) -> Dict[str, Any]:
        return {
            "id": obj.id,
            "query_run_id": obj.query_run_id,
            "agent_name": obj.agent_name,
            "tool_name": obj.tool_name,
            "evidence_type": obj.evidence_type,
            "source": obj.source,
            "source_record_id": obj.source_record_id,
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "observed_at": obj.observed_at.isoformat() if obj.observed_at else None,
            "severity": obj.severity,
            "confidence": obj.confidence,
            "payload": obj.payload,
            "ingested_at": obj.ingested_at.isoformat() if obj.ingested_at else None,
        }


_evidence_service: Optional[MarineEvidenceService] = None


def get_marine_evidence_service() -> MarineEvidenceService:
    global _evidence_service
    if _evidence_service is None:
        _evidence_service = MarineEvidenceService()
    return _evidence_service