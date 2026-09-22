import os
import sys

# Test env vars MUST be present before any app.config import (the settings
# singleton is cached at first import, so order across test modules matters).
os.environ.setdefault("LLM_API_KEY", "test-key-for-testing")
os.environ.setdefault("STT_API_KEY", "test-key-for-testing")
os.environ.setdefault("TTS_API_KEY", "test-key-for-testing")
os.environ.setdefault("TRANSLATION_API_KEY", "test-key-for-testing")

# Make the FastAPI package importable regardless of the pytest working directory.
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "apps", "api"))
# Repo root on the path so the Phase 7 `evaluation` package is importable.
sys.path.insert(0, _REPO)