# Execution context repository (Phase 4 / Phase 6).
#
# InMemory  -> tests and single-process dev.
# Postgres  -> production multi-turn memory (pg.ConversationContext row).
#
# Phase 6 turns context into a first-class multi-turn memory: besides location
# and language it carries resolved_time and the last intent, and the Postgres
# store persists the message history (JSON column added by migration
# e9a8f7c6b5d4).  The Pg store degrades gracefully to an in-memory mirror when
# the database is unavailable so a live conversation never crashes.
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ------------------------------------------------------------- data models
class StoredContext:
    def __init__(self, conversation_id: str, resolved_location: Optional[Dict] = None,
                 language: str = "en-IN", history: Optional[list] = None,
                 resolved_time: Optional[Dict] = None,
                 last_intent: Optional[Dict] = None):
        self.conversation_id = conversation_id
        self.resolved_location = resolved_location
        self.language = language
        self.history = history if history is not None else []
        self.resolved_time = resolved_time
        self.last_intent = last_intent


class ContextError(RuntimeError):
    pass


# ------------------------------------------------------------ in-memory
class InMemoryContextRepository:
    def __init__(self):
        self._store: Dict[str, StoredContext] = {}

    def _entry(self, conversation_id: str) -> StoredContext:
        if conversation_id not in self._store:
            self._store[conversation_id] = StoredContext(conversation_id)
        return self._store[conversation_id]

    async def save_turn(self, conversation_id: str, turn: Dict[str, Any]) -> None:
        entry = self._entry(conversation_id)
        entry.history.append(turn)
        if turn.get("language"):
            entry.language = turn["language"]

    async def get_context(self, conversation_id: str) -> Optional[StoredContext]:
        return self._store.get(conversation_id)

    async def update_location(self, conversation_id: str,
                              location: Dict[str, Any]) -> None:
        self._entry(conversation_id).resolved_location = location

    async def update_language(self, conversation_id: str, language: str) -> None:
        self._entry(conversation_id).language = language

    async def update_time(self, conversation_id: str,
                          time: Dict[str, Any]) -> None:
        self._entry(conversation_id).resolved_time = time

    async def update_intent(self, conversation_id: str,
                            intent_name: str) -> None:
        self._entry(conversation_id).last_intent = {
            "name": intent_name,
            "at": datetime.now(timezone.utc).isoformat(),
        }

    async def clear(self) -> None:
        self._store.clear()


# --------------------------------------------------------------- postgres
class PgContextRepository:
    """Production store built on the `conversation_contexts` row.

    Uses the application's async session factory (app.db.client.get_session);
    every operation falls back to an in-memory mirror when the database is
    down so a live turn is never lost to a connectivity blip.
    """

    def __init__(self, get_session=None,
                 fallback: Optional[InMemoryContextRepository] = None,
                 history_limit: int = 40):
        if get_session is None:
            from app.db.client import get_session as _session_factory
            get_session = _session_factory
        self._get_session = get_session
        self._memory = fallback or InMemoryContextRepository()
        self.history_limit = history_limit

    # ------------------------------------------------------------ internal
    async def _row_to_context(self, row) -> StoredContext:
        return StoredContext(
            conversation_id=row.conversation_id,
            resolved_location=row.resolved_location,
            language=row.language or "en-IN",
            history=row.history or [],
            resolved_time=row.resolved_time,
            last_intent=row.last_intent)

    async def _get_row_or_none(self, session, conversation_id):
        from sqlalchemy import select
        from app.db.models import ConversationContext
        result = await session.execute(
            select(ConversationContext).where(
                ConversationContext.conversation_id == conversation_id))
        return result.scalars().first()

    async def _upsert_row(self, session, conversation_id: str,
                          **fields) -> None:
        from sqlalchemy import select
        from app.db.models import ConversationContext
        row = None
        try:
            row = await self._get_row_or_none(session, conversation_id)
        except Exception:  # noqa: BLE001 - connection may be flaky
            return False
        if row is None:
            row = ConversationContext(conversation_id=conversation_id)
            session.add(row)
        for key, value in fields.items():
            if value is not None:
                setattr(row, key, value)
        return True

    # --------------------------------------------------------------- public
    async def save_turn(self, conversation_id: str, turn: Dict[str, Any]) -> None:
        try:
            async with self._get_session() as session:
                created = await self._upsert_row(
                    session, conversation_id, language=turn.get("language"))
                row = await self._get_row_or_none(session, conversation_id)
                if created and row is not None:
                    history = list(row.history or [])
                    history.append(turn)
                    row.history = history[-self.history_limit:]
                    row.updated_at = datetime.now(timezone.utc)
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            pass
        await self._memory.save_turn(conversation_id, turn)

    async def get_context(self, conversation_id: str) -> Optional[StoredContext]:
        try:
            async with self._get_session() as session:
                row = await self._get_row_or_none(session, conversation_id)
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            row = None
        if row is None:
            return await self._memory.get_context(conversation_id)
        return await self._row_to_context(row)

    async def update_location(self, conversation_id: str,
                              location: Dict[str, Any]) -> None:
        try:
            async with self._get_session() as session:
                await self._upsert_row(session, conversation_id,
                                       resolved_location=location,
                                       updated_at=datetime.now(timezone.utc))
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            pass
        await self._memory.update_location(conversation_id, location)

    async def update_language(self, conversation_id: str, language: str) -> None:
        try:
            async with self._get_session() as session:
                await self._upsert_row(session, conversation_id,
                                       language=language,
                                       updated_at=datetime.now(timezone.utc))
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            pass
        await self._memory.update_language(conversation_id, language)

    async def update_time(self, conversation_id: str,
                          time: Dict[str, Any]) -> None:
        try:
            async with self._get_session() as session:
                await self._upsert_row(session, conversation_id,
                                       resolved_time=time,
                                       updated_at=datetime.now(timezone.utc))
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            pass
        await self._memory.update_time(conversation_id, time)

    async def update_intent(self, conversation_id: str,
                            intent_name: str) -> None:
        record = {"name": intent_name,
                  "at": datetime.now(timezone.utc).isoformat()}
        try:
            async with self._get_session() as session:
                await self._upsert_row(session, conversation_id,
                                       last_intent=record,
                                       updated_at=datetime.now(timezone.utc))
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            pass
        await self._memory.update_intent(conversation_id, intent_name)

    async def clear(self) -> None:
        try:
            async with self._get_session() as session:
                from sqlalchemy import delete
                from app.db.models import ConversationContext
                await session.execute(delete(ConversationContext))
        except Exception:  # noqa: BLE001 - graceful in-memory mirror
            pass
        await self._memory.clear()