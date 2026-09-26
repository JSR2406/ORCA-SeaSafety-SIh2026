# Database Integration (/database)

## Role in ORCA Architecture
ORCA strictly uses **Supabase** for all database needs.

## Key Capabilities:
- **`client.py`:** Initializes the authorized Supabase connection using settings from `/core`.
- **`postgis.py`:** Contains spatial intersection logic mapping to PostGIS functions.
- **pgvector (RAG):** Evaluated inside `agents/rag.py` via hybrid search RPC calls.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you write new complex SQL, change the pgvector schema, or alter PostGIS queries, UPDATE THIS FILE immediately.
