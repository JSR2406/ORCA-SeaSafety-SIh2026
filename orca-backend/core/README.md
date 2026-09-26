# Core Configuration (/core)

## Role in ORCA Architecture
Handles all foundational setup, environment variables, and observability.

## Intent
- **`config.py`:** Uses `pydantic-settings` to safely manage Supabase URLs, OpenRouter keys, and LangSmith telemetry configuration from the `.env` file.
- Configures global logging and tracing.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you introduce a new environment variable or change LangSmith configs, UPDATE THIS FILE and `.env` immediately.
