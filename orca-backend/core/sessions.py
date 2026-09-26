"""Demo session store: last N turns per session_id (in-memory; single worker).

Production would persist to Postgres; the generator contract (state.history)
is storage-agnostic.
"""
from collections import deque
from typing import Deque, Dict, List

MAX_TURNS = 6
_store: Dict[str, Deque[Dict[str, str]]] = {}


def detect_language(text: str, override: str | None = None) -> str:
    """Explicit `language` wins; else unicode-script detect (ml/ta/hi); default en."""
    if override and override[:2].lower() in ("en", "ml", "hi", "ta"):
        return override[:2].lower()
    for ch in text:
        o = ord(ch)
        if 0x0D00 <= o <= 0x0D7F:
            return "ml"
        if 0x0B80 <= o <= 0x0BFF:
            return "ta"
        if 0x0900 <= o <= 0x097F:
            return "hi"
    return "en"


LANG_NAMES = {"en": "English", "ml": "Malayalam", "hi": "Hindi", "ta": "Tamil"}


def get_history(session_id: str | None) -> List[Dict[str, str]]:
    if not session_id:
        return []
    return list(_store.get(session_id, []))


def append_turn(session_id: str | None, role: str, text: str) -> None:
    if not session_id:
        return
    dq = _store.setdefault(session_id, deque(maxlen=MAX_TURNS))
    dq.append({"role": role, "text": text[:1000]})
