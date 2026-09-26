# Subagents (/agents)

## Role in ORCA Architecture
This folder contains the specific worker agents triggered during a "Complex" query in the LangGraph workflow.

## The Agents:
- **Router (`router.py`):** The LLM node deciding 'simple' vs 'complex' intent.
- **RAG Agent (`rag.py`):** Uses an LLM to formulate a Hybrid Search query, then calls Supabase pgvector.
- **Geospatial Agent (`geospatial.py`):** Interacts with Supabase PostGIS to evaluate coordinate safety.
- **Generator (`generator.py`):** Takes the strictly aggregated state and generates the final user-facing text.
- **Live Data Agent (Pending):** Fetches active IMD warnings and real-time conditions.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you modify an agent's prompt, add a new agent, or change how they interact with tools/Supabase, UPDATE THIS FILE immediately.
