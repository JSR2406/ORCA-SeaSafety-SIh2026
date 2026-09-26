# ORCA (Oceanic Resource & Condition Assistant) - Backend Architecture

## System Overview (360-Degree Context)
ORCA is an agentic, multimodal, data-driven marine assistant designed for fishermen, researchers, and government officials.
We are building the backend system using an **Intent-Driven Multi-Agent Architecture**.

### System Entry & Configuration:
- **`main.py`**: The Uvicorn entry point that runs the FastAPI server.
- **`.env`**: Stores the verified `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `OPENROUTER_API_KEY`.
- **Database**: The Supabase instance is fully provisioned with `pgvector` and `postgis` extensions.

### The Core Flow:
1. **The Gateway (Orchestrator):** A user query comes in (via `/api`). A lightweight LLM router (Nemotron 3.4B via OpenRouter) determines if the intent is "Simple" or "Complex".
2. **Path A (Simple):** Directly routes to the final LLM for a standard Q&A answer.
3. **Path B (Complex - Agentic Pipeline):** The Orchestrator delegates to specialized Subagents running in parallel via **LangGraph**:
   - **Live Data Agent:** Fetches real-time weather, ocean states, and warnings.
   - **RAG Agent:** Queries a **Supabase pgvector** database containing categorized knowledge using Hybrid Search.
   - **Geospatial Agent:** Uses **Supabase PostGIS** to analyze routes and Potential Fishing Zones (PFZ).
4. **Machine Learning Layer:** The raw data fetched by agents is piped into ML models (XGBoost/LightGBM) to generate predictive scores.
5. **Context Aggregation:** All data is stitched into a massive, strictly typed JSON object (The LangGraph State).
6. **Final Generation:** The massive JSON is passed to the final LLM (Nemotron) to generate a grounded, human-friendly response.

## Tech Stack
- **Framework:** Python, FastAPI, Uvicorn
- **Agent Orchestration:** LangGraph, LangChain
- **Database:** Supabase (pgvector for RAG, PostGIS for spatial data). NO OTHER DB IS USED.
- **ML:** XGBoost, LightGBM, GeoPandas, scikit-learn
- **LLM Provider:** OpenRouter (Nemotron models)

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- **360-Degree Context:** You are part of the ORCA multi-agent system. Understand how your current task impacts the Orchestrator, Subagents, ML models, and Supabase integration.
- **Update Rule:** If you make ANY changes to the architecture, logic, or dependencies during your run, you MUST update this README to reflect the current state of the codebase.
- **Dependency Rule:** If a version conflict occurs and you install a different version, update `requirements.txt` AND log the version constraint here.
