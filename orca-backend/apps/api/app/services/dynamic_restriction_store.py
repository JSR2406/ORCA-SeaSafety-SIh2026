# Phase 5 - dynamic restriction stores.
#
# The store is the durability seam.  upsert is IDEMPOTENT on the natural key
# (source, source_record_id); refresh marks freshness; expire_unrefreshed
# removes anything a source stopped publishing so expired restrictions never
# linger in the 'active' view.
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from app.models.common import utcnow
from app.models.dynamic_restrictions import DynamicRestriction, detect_changes
from app.models.warnings import WarningStatus


class DynamicRestrictionStore(ABC):

    @abstractmethod
    async def upsert_many(
        self, items: List[DynamicRestriction], fetched_at: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Insert or update; returns {inserted, updated, changed}.

        `changed` counts refreshed records whose safety-relevant fields
        (geometry/validity/severity/description/status) differed from the
        stored row, so a source edit is detected, never blindly appended.
        """

    @abstractmethod
    async def list_active(
        self, at: Optional[datetime] = None
    ) -> List[DynamicRestriction]:
        """Only records evaluated ACTIVE at `at` (valid window + not expired)."""

    @abstractmethod
    async def expire_unrefreshed(
        self, sources: List[str], at: Optional[datetime] = None,
        grace_seconds: int = 6 * 3600,
    ) -> int:
        """Mark records a source stopped refreshing as expired. Returns count."""

    @abstractmethod
    async def all(self) -> List[DynamicRestriction]:
        """Every stored record (including expired) for observability."""


class InMemoryDynamicRestrictionStore(DynamicRestrictionStore):
    """Deterministic in-memory store (tests / offline demos).

    Idempotent: re-upserting the same (source, record) only updates fields and
    resets the refresh stamp; it never duplicates.
    """

    def __init__(self) -> None:
        self._rows: Dict[tuple, DynamicRestriction] = {}

    async def upsert_many(self, items, fetched_at=None):
        fetched_at = fetched_at or utcnow()
        inserted = 0
        updated = 0
        changed = 0
        for item in items:
            key = item.natural_key()
            if key in self._rows:
                old = self._rows[key]
                item.refreshed_at = fetched_at
                if not item.expired:
                    item.expired = False
                if not item.cancelled:
                    item.cancelled = False
                self._rows[key] = item
                updated += 1
                if detect_changes(old, item):
                    changed += 1
                    item.updated_at = fetched_at
            else:
                item.ingested_at = fetched_at
                item.refreshed_at = fetched_at
                self._rows[key] = item
                inserted += 1
        return {"inserted": inserted, "updated": updated, "changed": changed}

    async def list_active(self, at=None):
        at = at or utcnow()
        return [r for r in self._rows.values() if r.status(at) == WarningStatus.ACTIVE]

    async def expire_unrefreshed(self, sources, at=None, grace_seconds=6 * 3600):
        at = at or utcnow()
        count = 0
        for key, row in self._rows.items():
            if row.source not in sources:
                continue
            refreshed = row.refreshed_at or row.ingested_at or at
            if refreshed is None:
                continue
            if (at - refreshed).total_seconds() > grace_seconds and not row.expired:
                row.expired = True
                count += 1
        return count

    async def all(self):
        return list(self._rows.values())