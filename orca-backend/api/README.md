# API Layer (/api)

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
