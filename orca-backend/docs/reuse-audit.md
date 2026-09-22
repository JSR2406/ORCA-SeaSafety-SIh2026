# Repository Reuse Audit (Updated with Actual Findings)

## Overview
This document audits existing FloatChat and related repositories for reusable modules, following the reuse strategy in the project specification. Repositories have been cloned and inspected.

---

## A. vishalbarai007/FloatChat (MIT License)

| Field | Value |
|-------|-------|
| **Repository URL** | https://github.com/vishalbarai007/FloatChat |
| **License** | MIT ✅ |
| **Main Technologies** | Next.js 15 (App Router), TypeScript, React Three Fiber, FastAPI, xarray, SQLite, FAISS, Ollama (local LLM), Tailwind CSS |
| **Reusable Modules** | - **Frontend**: `src/components/` (chat UI, globe with Three.js, float markers, landing hero)<br>- **Frontend**: `src/app/` routes (chat, dashboard, globe, upload, profile)<br>- **Backend**: `server/app/processing.py` (NetCDF → xarray → pandas DataFrame)<br>- **Backend**: `server/app/visualizations.py` (Folium map generation)<br>- **Backend**: `server/app/database.py` (SQLite storage pattern)<br>- **Backend**: `server/main.py` (FastAPI endpoints: `/upload-data`, `/chatbot-response`) |
| **Incomplete/Unsafe Modules** | - ❌ **`server/app/ai_core.py`**: Unverified NL-to-SQL via local Ollama (phi3:3.8b) — **DO NOT USE**<br>- ❌ VectorDB using FAISS + Ollama embeddings for metadata — not suitable for numerical queries<br>- ❌ SQLite schema (not PostGIS/PostgreSQL)<br>- ❌ No QC filtering in NetCDF processing<br>- ❌ No provenance/evidence layer<br>- ❌ Hard-coded "data" table name |
| **Required Dependency Changes** | - Replace Ollama with structured LLM function calling (OpenAI/Anthropic)<br>- Replace SQLite with Supabase/PostgreSQL + PostGIS<br>- Add argopy for ARGO data fetching<br>- Add Pydantic v2 for query contracts<br>- Add verification layer |
| **Decision** | **Adapt** — Extract UI components (globe, chat, landing), NetCDF processing patterns, FastAPI structure. **Do not copy** AI core or database layer. |
| **Attribution** | MIT License — include in LICENSE |
| **Security Concerns** | - CORS `allow_origins=["*"]`<br>- No rate limiting<br>- Raw SQL execution from LLM<br>- No auth in original |
| **Compatibility** | ✅ Next.js 15, FastAPI, Vercel, Tailwind |

---

## B. World Bank Data AI Chatbot (Apache-2.0 + World Bank IGO Rider)

| Field | Value |
|-------|-------|
| **Repository URL** | https://github.com/worldbank/data-ai-chatbot |
| **License** | Apache-2.0 with World Bank IGO Rider — **review before redistribution** |
| **Main Technologies** | Next.js 15, FastAPI, LangGraph, MCP tools, PostgreSQL, Vercel AI SDK, vega-embed, @data360/mcp-ui |
| **Reusable Modules** | - **Proof-Carrying Numbers architecture** (CRITICAL for FloatChat):<br>  - `backend/app/ai/graph/nodes/narrator.py` — Injects RAW TOOL RESULTS into system prompt<br>  - `backend/app/ai/graph/nodes/quick_answer.py` — Programmatic card synthesis with `claim_id` fields<br>  - `frontend/components/data360/quick-answer.tsx` — `ClaimMark` components for provenance tooltips<br>  - `frontend/components/data360/chart-preview.tsx` — Vega-Lite chart embedding<br>- **Backend structure**: `backend/app/ai/graph/nodes/` (planner, researcher, narrator, quick_answer)<br>- **Frontend artifacts**: `frontend/artifacts/chart/client.tsx` (Vega-Lite rendering)<br>- **Streaming/SSE**: `backend/app/utils/stream.py`, `responses_stream.py` |
| **Incomplete/Unsafe Modules** | - World Bank Data360 specific MCP tools (`data360_get_data`, etc.)<br>- Azure-specific auth and prompt shields<br>- Complex LangGraph pipeline — over-engineered for MVP |
| **Required Dependency Changes** | - Replace Data360 tools with ARGO query tools (`search_profiles`, `aggregate_timeseries`, etc.)<br>- Adapt `claim_id` → ARGO `profile_id`/`observation_id`/`float_id`<br>- Replace vega-embed with Recharts/Plotly for simpler charts<br>- Simplify LangGraph → structured query planner + executor |
| **Decision** | **Adapt** — Core explainability patterns (RAW TOOL RESULTS injection, claim_id propagation, card synthesis). **Reimplement** for ARGO domain. |
| **Attribution** | Apache-2.0 + World Bank IGO Rider — include NOTICE, THIRD_PARTY_LICENSES |
| **Security Concerns** | Minimal — production-grade patterns |
| **Compatibility** | ✅ Next.js 15, FastAPI, Vercel, conceptual patterns |

---

## C. Vercel AI Chatbot (MIT License)

| Field | Value |
|-------|-------|
| **Repository URL** | https://github.com/vercel/ai-chatbot |
| **License** | MIT ✅ |
| **Main Technologies** | Next.js 15 App Router, React 18, Vercel AI SDK, Tailwind CSS, shadcn/ui (Radix), PostgreSQL (Vercel Postgres), NextAuth, Playwright |
| **Reusable Modules** | - **Frontend foundation**: `app/`, `components/`, `hooks/`, `lib/`<br>- **Chat UI**: Streaming responses, message components, tool calling UI<br>- **Auth**: NextAuth with multiple providers<br>- **Database**: Drizzle ORM with PostgreSQL<br>- **Deployment**: Vercel-optimized |
| **Incomplete/Unsafe Modules** | - Generic chatbot — no scientific data domain<br>- AI SDK tools call database directly — **must route through FastAPI**<br>- No evidence/provenance UI |
| **Required Dependency Changes** | - Decouple scientific computation from chat UI<br>- Replace AI SDK tools with typed ARGO query contracts<br>- Add MapLibre, Recharts for ocean visualizations |
| **Decision** | **Adapt** — Use as frontend scaffolding (chat interface, auth, deployment). Replace chat logic with FloatChat query flow. |
| **Attribution** | MIT License |
| **Security Concerns** | Standard Next.js patterns |
| **Compatibility** | ✅ Next.js 15, Vercel, Tailwind, React 18 |

---

## D. euroargodev/argopy (EUPL-1.2 License)

| Field | Value |
|-------|-------|
| **Repository URL** | https://github.com/euroargodev/argopy |
| **License** | EUPL-1.2 — **treat as dependency, do not fork** |
| **Main Technologies** | Python, xarray, pandas, NetCDF, ERDDAP, Argovis |
| **Reusable Modules** | - **Use directly as dependency**: `pip install argopy`<br>- `DataFetcher().region([lon_min, lon_max, lat_min, lat_max, depth_min, depth_max, date_start, date_end]).to_xarray()`<br>- Built-in QC filtering, caching, source selection (GDAC, ERDDAP, Argovis)<br>- Profile/trajectory plotting |
| **Incomplete/Unsafe Modules** | N/A — use as library |
| **Required Dependency Changes** | None — use as-is |
| **Decision** | **Use directly** — Primary ARGO data access layer. Wrap in `app/data/argo_client.py`. |
| **Attribution** | EUPL-1.2 |
| **Security Concerns** | None |
| **Compatibility** | ✅ Python 3.11+, xarray, pandas |

---

## E. Argovis Demo Notebooks (Reference Only)

| Field | Value |
|-------|-------|
| **Repository URL** | https://github.com/argovis/demo_notebooks |
| **License** | Check repo |
| **Main Technologies** | Jupyter notebooks, Argovis API, Python |
| **Reusable Modules** | - Query examples for regional access<br>- Profile retrieval patterns<br>- QC filtering logic<br>- Colocation experiments |
| **Incomplete/Unsafe Modules** | - Notebook-only logic<br>- Hard-coded parameters<br>- Ad hoc visualization |
| **Decision** | **Reference only** — Convert useful patterns to tested services in `app/data/argovis_client.py` |
| **Compatibility** | ⚠️ Patterns only |

---

## F. euroargodev/erddap_usecases (Reference Only)

| Field | Value |
|-------|-------|
| **Repository URL** | https://github.com/euroargodev/erddap_usecases |
| **Main Technologies** | ERDDAP REST API, CSV/NetCDF retrieval |
| **Reusable Modules** | - ERDDAP URL construction patterns<br>- Query parameter conventions<br>- Subset downloading |
| **Decision** | **Reference only** — Create production wrapper `app/data/erddap_client.py` |
| **Compatibility** | ⚠️ Patterns only |

---

## Summary Decision Matrix (Updated)

| Repository | Fork | Adapt | Reference Only | Use as Dep | Priority |
|------------|------|-------|----------------|------------|----------|
| vishalbarai007/FloatChat | ❌ | ✅ UI + NetCDF processing | | | High |
| World Bank Data AI Chatbot | ❌ | ✅ Explainability (PCN) | | | **Critical** |
| Vercel AI Chatbot | ❌ | ✅ Frontend scaffolding | | | High |
| argopy | | | | ✅ Direct dependency | **Critical** |
| Argovis demos | | | ✅ Patterns | | Medium |
| ERDDAP use cases | | | ✅ Patterns | | Medium |

---

## Implementation Priority Order

1. **argopy** — Install as dependency, wrap in `argo_client.py`
2. **World Bank PCN patterns** — Reimplement narrator → `verifier.py`, quick_answer → `evidence_card` synthesis
3. **Vercel chatbot** — Fork as frontend foundation, replace chat logic
4. **FloatChat (vishalbarai)** — Extract UI components (globe, map, chat), NetCDF processing logic
5. **ERDDAP/Argovis** — Build production clients for fallback data sources

---

## License Compliance Checklist

- [ ] MIT components (FloatChat, Vercel): Include license in distribution
- [ ] Apache-2.0 + IGO Rider (World Bank): Include NOTICE, THIRD_PARTY_LICENSES, review IGO Rider
- [ ] EUPL-1.2 (argopy): Dynamic linking OK, include license if distributing
- [ ] Create `LICENSE` and `THIRD_PARTY_LICENSES.md` in FloatChat repo root