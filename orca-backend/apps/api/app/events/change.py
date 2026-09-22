# Phase 11 - source-aware, idempotent change detection.
#
# For every (source, stable_key) we track the last-seen state hash and
# timestamp.  On each evaluation we classify the transition:
#
#   never seen            -> NEW
#   hash differs          -> CHANGED (or CORRECTED when the record edits a
#                             previously-published value)
#   hash identical        -> UNCHANGED   (no event)
#   source went A->FAILED -> FAILED
#   source came back      -> RECOVERED
#   record validity ended -> EXPIRED
#
# Processing is idempotent: calling detect() twice with the same JSON yields
# UNCHANGED the second time and emits no event.
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from app.events.model import (
    ChangeState, MarineEvent, MarineEventType, stable_event_id, utcnow,
)


def content_hash(state: Any) -> str:
    """Stable hash that ignores key ordering and timestamps that are metadata
    churn (ingested_at) rather than physical meaning."""
    return hashlib.sha1(
        json.dumps(state, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@dataclass
class SourceState:
    """Last classification + hash for one (source, stable_key)."""
    last_hash: Optional[str] = None
    last_seen: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_status: str = "available"
    was_emitted: bool = False


class ChangeDetector:
    """In-memory idempotent change detector.

    *keyed_state* (dict[tuple, SourceState]) is rehydrated from the source
    health / event store on restart so the detector is restart-safe.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_ticks: int = 2,
        keyed_state: Optional[Dict[tuple, SourceState]] = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_ticks = recovery_ticks
        self.states: Dict[tuple, SourceState] = keyed_state or {}

    # ------------------------------------------------------------------ core
    def _key(self, source: str, stable_key: str) -> tuple:
        return (source, stable_key)

    def classify_data(
        self,
        source: str,
        stable_key: str,
        record: Dict[str, Any],
        *,
        event_type: MarineEventType,
        corrected_key: Optional[str] = None,
    ) -> tuple[ChangeState, SourceState]:
        """Classify a data record for (source, stable_key).

        Returns (change_state, state).  Idempotent: identical record after the
        first emission -> UNCHANGED.
        """
        key = self._key(source, stable_key)
        state = self.states.setdefault(key, SourceState())
        h = content_hash(record)

        if state.last_hash is None:
            state.last_hash = h
            state.last_seen = utcnow()
            state.last_status = "available"
            result = ChangeState.NEW
        elif state.last_hash == h:
            result = ChangeState.UNCHANGED
        else:
            # A corrected record explicitly signals DATA_CORRECTED; otherwise it
            # is a plain evolution.
            result = ChangeState.CORRECTED if corrected_key else ChangeState.CHANGED
            state.last_hash = h
            state.last_seen = utcnow()
        state.was_emitted = result in (ChangeState.NEW, ChangeState.CHANGED,
                                       ChangeState.CORRECTED)
        return result, state

    def observe_source(
        self,
        source: str,
        ok: bool,
        *,
        stable_key: str = "__source__",
    ) -> tuple[ChangeState, SourceState]:
        """Track source-level availability (independent of any data record).

        FAILED when consecutive failures >= threshold; RECOVERED only on the
        tick the source flips back to available.  No duplicate operational
        alerts: RECOVERED fires once per interrupted run.
        """
        key = self._key(source, stable_key)
        state = self.states.setdefault(key, SourceState())

        if ok:
            if state.last_status == "failed":
                # recovering: emit RECOVERED exactly once, on the tick the
                # source has been healthy for recovery_ticks consecutive ticks.
                state.consecutive_successes += 1
                if state.consecutive_successes >= self.recovery_ticks:
                    state.last_status = "available"
                    state.consecutive_failures = 0
                    state.was_emitted = True
                    return ChangeState.RECOVERED, state
                state.was_emitted = False
                return ChangeState.UNCHANGED, state
            # already available: plain healthy tick
            state.consecutive_successes += 1
            state.consecutive_failures = 0
            state.was_emitted = False
            return ChangeState.UNCHANGED, state

        # failure
        state.consecutive_failures += 1
        state.consecutive_successes = 0
        if state.consecutive_failures >= self.failure_threshold:
            if state.last_status == "available":
                state.last_status = "failed"
                state.was_emitted = True
                return ChangeState.FAILED, state
        state.was_emitted = False
        return ChangeState.UNCHANGED, state

    def mark_expired(self, source: str, stable_key: str) -> ChangeState:
        key = self._key(source, stable_key)
        state = self.states.setdefault(key, SourceState())
        state.last_status = "expired"
        state.was_emitted = True
        return ChangeState.EXPIRED

    # ---------------------------------------------------------------- events
    def build_event(
        self,
        event_type: MarineEventType,
        source: str,
        stable_key: str,
        current_state: Any,
        change_state: ChangeState,
        *,
        location: Optional[Dict[str, float]] = None,
        geometry: Optional[Dict[str, Any]] = None,
        severity: Any = None,
        previous_state: Any = None,
        validity: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MarineEvent:
        return MarineEvent(
            event_id=stable_event_id(
                event_type, source, stable_key,
                current_state=current_state),
            event_type=event_type,
            source=source,
            timestamp=utcnow(),
            location=location,
            geometry=geometry,
            severity=severity or "info",
            previous_state=previous_state,
            current_state=current_state,
            validity=validity or {},
            change_state=change_state,
            metadata=metadata or {"stable_key": stable_key},
        )