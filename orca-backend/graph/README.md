# LangGraph Orchestrator (/graph)

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
