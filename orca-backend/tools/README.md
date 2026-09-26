# Tools Layer (/tools)

## Role in ORCA Architecture
These are the exact functions and API wrappers that the `/agents` call to interact with the outside world. This will serve as our **Model Context Protocol (MCP)** server layer.

## Intent
- Wraps external APIs (IMD, INCOIS, ISRO, Government Portals).
- Returns strict JSON data to the agents.

---
**🤖 AI ASSISTANT INSTRUCTION (CRITICAL - APPLY PER RUN):**
- Review the ORCA Root README for complete context.
- If you integrate a new external API or modify a tool's input/output schema, UPDATE THIS FILE immediately.
