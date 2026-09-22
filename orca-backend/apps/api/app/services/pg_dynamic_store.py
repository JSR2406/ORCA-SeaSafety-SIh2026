# Phase 5 - PostgreSQL-backed dynamic restriction store.
#
# Same interface as the in-memory store; swaps in where a live session factory
# is available.  Geometry values are stored via the DynamicRestriction ORM
# model; retrieval converts WKB (PostGIS) or JSON text back to GeoJSON.
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, update

from app.db.client import get_session
from app.db.models import DynamicRestriction as DynamicRestrictionModel
from app.db.marine_repository import active_window
from app.models.dynamic_restrictions import DynamicRestriction, detect_changes
from app.services.dynamic_restriction_store import DynamicRestrictionStore


def _geometry_to_geojson(value) -> Optional[Dict]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            from app.geo_utils import wkb_to_geojson
            return wkb_to_geojson(value)
        except Exception:
            return None
    try:
        return json.loads(str(value))
    except Exception:
        return None


class PgDynamicRestrictionStore(DynamicRestrictionStore):
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session

    async def upsert_many(self, items, fetched_at=None):
        fetched_at = fetched_at or datetime.utcnow()
        async with self.session_factory() as session:
            inserted = updated = changed = 0
            for item in items:
                row = (await session.execute(
                    select(DynamicRestrictionModel).where(
                        DynamicRestrictionModel.source == item.source,
                        DynamicRestrictionModel.source_record_id == item.source_record_id,
                    )
                )).scalars().first()
                payload = {
                    "restriction_id": item.restriction_id,
                    "name": item.name,
                    "restriction_type": item.restriction_type,
                    "severity": item.severity,
                    "valid_from": item.valid_from,
                    "valid_until": item.valid_until,
                    "issued_at": item.issued_at,
                    "official": item.official,
                    "data_class": item.data_class,
                    "description": item.description,
                    "metadata_json": item.metadata,
                    "refreshed_at": fetched_at,
                    "expired": item.expired,
                    "cancelled": item.cancelled,
                    "geometry": json.dumps(item.geometry),
                }
                if row is None:
                    session.add(DynamicRestrictionModel(
                        source=item.source, source_record_id=item.source_record_id,
                        ingested_at=fetched_at, **payload))
                    inserted += 1
                else:
                    old = self._to_dataclass(row)
                    fields = detect_changes(old, item)
                    if fields:
                        payload["updated_at"] = fetched_at
                        changed += 1
                    await session.execute(
                        update(DynamicRestrictionModel)
                        .where(DynamicRestrictionModel.id == row.id)
                        .values(**payload))
                    updated += 1
            await session.commit()
        return {"inserted": inserted, "updated": updated, "changed": changed}

    async def list_active(self, at=None):
        at = at or datetime.utcnow()
        async with self.session_factory() as session:
            rows = (await session.execute(
                select(DynamicRestrictionModel).where(
                    DynamicRestrictionModel.expired.is_(False),
                    DynamicRestrictionModel.cancelled.is_(False),
                    active_window(DynamicRestrictionModel.valid_from,
                                  DynamicRestrictionModel.valid_until, at),
                )
            )).scalars().all()
        return [self._to_dataclass(r) for r in rows]

    async def expire_unrefreshed(self, sources, at=None, grace_seconds=6 * 3600):
        at = at or datetime.utcnow()
        from sqlalchemy import and_, or_
        async with self.session_factory() as session:
            result = await session.execute(
                update(DynamicRestrictionModel)
                .where(
                    DynamicRestrictionModel.expired.is_(False),
                    DynamicRestrictionModel.source.in_(sources),
                    or_(DynamicRestrictionModel.refreshed_at.is_(None),
                        and_(DynamicRestrictionModel.refreshed_at.isnot(None),
                             DynamicRestrictionModel.refreshed_at <
                             at - timedelta(seconds=grace_seconds))),
                )
                .values(expired=True))
            count = result.rowcount or 0
            await session.commit()
        return count

    async def all(self):
        async with self.session_factory() as session:
            rows = (await session.execute(
                select(DynamicRestrictionModel)
            )).scalars().all()
        return [self._to_dataclass(r) for r in rows]

    @staticmethod
    def _to_dataclass(row) -> DynamicRestriction:
        return DynamicRestriction(
            source=row.source,
            source_record_id=row.source_record_id,
            restriction_id=row.restriction_id,
            name=row.name,
            restriction_type=row.restriction_type,
            severity=row.severity,
            geometry=_geometry_to_geojson(row.geometry) or {},
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            issued_at=row.issued_at,
            official=row.official,
            data_class=row.data_class,
            description=row.description,
            metadata=row.metadata_json or {},
            ingested_at=row.ingested_at,
            refreshed_at=row.refreshed_at,
            updated_at=row.updated_at,
            expired=row.expired,
            cancelled=row.cancelled,
        )