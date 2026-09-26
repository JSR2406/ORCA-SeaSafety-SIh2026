import os

readme_contents = {
    '.': """# ORCA (Oceanic Resource & Condition Assistant) - Backend Architecture

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
""",

    'api': """# API Layer (/api)

## Role in ORCA Architecture
This directory houses the **FastAPI** endpoints that act as the front door for the entire ORCA system.
- `server.py`: Initializes the FastAPI application.
- `routes.py`: Contains the `POST /query` endpoint which initializes the LangGraph state and triggers the workflow.

## Structure & Intent
Instead of handling business logic, these endpoints immediately pass the user's query and context (location, time) to the LangGraph Orchestrator and return the final generated `final_response`.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context. 
- If you add a new endpoint, change response schemas, or alter how FastAPI triggers LangGraph, UPDATE THIS FILE immediately in the same run.
""",

    'graph': """# LangGraph Orchestrator (/graph)

## Role in ORCA Architecture
This is the **brain of the workflow**. It defines the deterministic state machine using `LangGraph`.

## Flow Definition (`workflow.py` & `nodes.py`):
1. **State:** Defined by Pydantic models (located in `/schemas`), holding the massive JSON.
2. **Router Node:** Calls Nemotron to classify intent.
3. **Conditional Edges:** Splits traffic to `Simple Generation` or `Parallel Subagents`.
4. **Subagent Nodes:** Triggers the Live Data, RAG, and Geospatial agents concurrently.
5. **ML Node:** Waits for agent data, runs it through models (from `/ml`), and appends scores to the state.
6. **Generator Node:** Takes the fully populated state and calls the LLM for the final human-friendly response.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- Any changes to node definitions, edge routing, parallel execution logic, or LangChain/LangGraph versions MUST be documented in this file immediately.
""",

    'agents': """# Subagents (/agents)

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
""",

    'tools': """# Tools Layer (/tools)

## Role in ORCA Architecture
These are the exact functions and API wrappers that the `/agents` call to interact with the outside world. This will serve as our **Model Context Protocol (MCP)** server layer.

## Intent
- Wraps external APIs (IMD, INCOIS, ISRO, Government Portals).
- Returns strict JSON data to the agents.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you integrate a new external API or modify a tool's input/output schema, UPDATE THIS FILE immediately.
""",

    'ml': """# Machine Learning Layer (/ml)

## Role in ORCA Architecture
ORCA relies on deterministic ML models, not just LLMs, for safety. This folder contains the ML pipelines.

## Purpose
- **Predictive Scoring:** Takes tabular data and outputs `fishing_suitability`, `risk_score`, and `route_risk`.
- **Tech:** Uses XGBoost / LightGBM for fast tabular inference. Uses GeoPandas for spatial calculations.
- **Execution:** Loaded directly into memory (via `joblib`) during the LangGraph execution to ensure millisecond latency.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you swap a model type, alter feature engineering pipelines, or change spatial logic, UPDATE THIS FILE immediately.
""",

    'database': """# Database Integration (/database)

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
""",

    'schemas': """# Data Schemas (/schemas)

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
""",

    'core': """# Core Configuration (/core)

## Role in ORCA Architecture
Handles all foundational setup, environment variables, and observability.

## Intent
- **`config.py`:** Uses `pydantic-settings` to safely manage Supabase URLs, OpenRouter keys, and LangSmith telemetry configuration from the `.env` file.
- Configures global logging and tracing.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you introduce a new environment variable or change LangSmith configs, UPDATE THIS FILE and `.env` immediately.
"""
}

for folder, content in readme_contents.items():
    file_path = os.path.join(folder, 'README.md')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("All READMEs updated with the latest implementation details.")
