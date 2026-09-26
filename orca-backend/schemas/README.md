# Data Schemas (/schemas)

## Role in ORCA Architecture
This is the central nervous system for data typing. Since ORCA relies on a massive, highly structured JSON context to feed the final LLM, strict validation is required.

## Purpose
- Uses **Pydantic** to define API Request/Response models.
- Defines the **LangGraph State (`state.py`)** tracking `query`, `location`, `weather`, `ocean`, `warnings`, `fishing`, `risk`, `route`, and `rag` arrays.
- Enforces data integrity before it reaches the ML models or LLMs.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you add a new field to the LangGraph state or alter the final JSON structure, UPDATE THIS FILE immediately.
