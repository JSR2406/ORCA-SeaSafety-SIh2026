# ORCA — AI Marine Intelligence & Oceanographic Copilot Platform

<div align="center">
  <h3>Smart India Hackathon (SIH) Flagship Innovation</h3>
  <p><strong>Next-Generation Maritime Operations, Predictive Safety, and Oceanographic AI Copilot</strong></p>
</div>

---

## 🌊 Overview

**ORCA (FloatChat)** is an enterprise-grade, multilingual marine intelligence platform designed to empower maritime operators, fishermen, oceanographic researchers, and port authorities with actionable real-time insights, hazard alerts, cyclone tracking, and AI-driven navigation.

### Key Capabilities
- 🗺️ **High-Resolution Geospatial Engine**: Google Maps JavaScript & Tile API integration with hybrid satellite, roadmap, bathymetry, and cyclone tracking layers.
- 🤖 **Oceanographic AI Copilot**: Grounded multi-turn conversational agent with domain-specific Retrieval-Augmented Generation (RAG) and function-calling capabilities.
- 🎙️ **Multilingual Voice Support**: Native speech-to-text and text-to-speech engine powered by Sarvam AI supporting regional Indian languages.
- ⚠️ **Real-Time Hazard & Cyclone Warnings**: Aggregates metocean feeds from JTWC, GDACS, Open-Meteo, StormGlass, and CoastWatch.
- 🐟 **Potential Fishing Zone (PFZ) & Marine Insights**: Dynamic SST, chlorophyll-a, wind, swell, and tide tracking for optimal and safe catch planning.
- 🧠 **ML Governance & Continuous Learning**: Supervised marine models with ground-truth validation, continuous retraining, and evidence provenance logs.

---

## 📁 Repository Structure

```text
ORCA_Complete/
├── docs/                                          # Architectural specifications & feature guides
│   └── ORCA_FEATURES_GUIDE.md                     # Deep dive into platform features
├── orca-frontend/                                 # Next.js App Router Web Interface
│   ├── src/
│   │   ├── app/                                   # Next.js app routes and layouts
│   │   ├── components/                            # MarineMap, Topbar, Sidebar, Logo, etc.
│   │   ├── context/                               # BackendContext, LanguageContext
│   │   ├── services/                              # API client, WebSocket & mock fallback services
│   │   ├── views/                                 # Dashboard, Copilot, MarineExplorer, Safety, etc.
│   │   └── data/                                  # Translations, mock telemetry & dictionaries
│   ├── public/                                    # Static assets, branding, and icons
│   ├── .env.example                               # Frontend environment template
│   └── package.json                               # Frontend dependencies
├── orca-backend/                                  # FastAPI Asynchronous Microservice Architecture
│   ├── apps/api/app/                              # FastAPI core application
│   │   ├── agents/                                # Specialized maritime AI agents
│   │   ├── contracts/                             # Pydantic schemas & orchestration contracts
│   │   ├── datasources/                           # OpenWeather, StormGlass, JTWC, GDACS adapters
│   │   ├── ingestion/                             # Knowledge base & RAG document pipelines
│   │   ├── orchestration/                         # Intent routing & query planners
│   │   ├── routers/                               # Chat, alerts, voice, routes, and health endpoints
│   │   └── services/                              # Marine data providers, voice STT/TTS services
│   ├── data/                                      # Curated maritime regulation seeds & knowledge base
│   ├── tests/                                     # Comprehensive pytest test suite
│   ├── setup.ps1                                  # Windows PowerShell automated backend runner
│   ├── requirements.txt                           # Python dependencies
│   └── .env.example                               # Backend environment template
├── FloatChat — Frontend Engineering & Integration Specification.pdf
├── SIH-2026.pptx_20260910_171820_0000.pdf         # Official presentation slide deck
├── SIH_JUDGE_PREPARATION_GUIDE.md                 # Complete walkthrough and demo script for judges
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Node.js**: v18.17+ or v20+
- **Python**: 3.10+ (Python 3.11 recommended)
- **Git**

---

### 2. Backend Setup (`orca-backend`)

#### Option A: Automated Runner (Windows PowerShell)
```powershell
cd orca-backend
.\setup.ps1
```
The interactive runner provides options to install dependencies, copy environment variables, apply migrations, run tests, and start the development server.

#### Option B: Manual Setup
```bash
cd orca-backend

# 1. Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
# source venv/bin/activate

# 2. Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL/Supabase and API keys

# 4. Start backend API
uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API will be live at `http://localhost:8000`. Swagger documentation is available at `http://localhost:8000/docs`.

---

### 3. Frontend Setup (`orca-frontend`)

```bash
cd orca-frontend

# 1. Install dependencies
npm install

# 2. Configure environment
cp .env.example .env.local
# Set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY and NEXT_PUBLIC_API_URL=http://localhost:8000

# 3. Start development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser to view the ORCA dashboard.

---

## 🔑 Environment Variables Guide

### Backend (`orca-backend/.env`)
| Variable | Description |
| :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string (Supabase PostGIS + pgvector enabled) |
| `SUPABASE_URL` | Supabase API endpoint URL |
| `STORMGLASS_API_KEY` | Storm Glass marine & tide API key |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `LLM_PROVIDER` | LLM service (`openrouter`, `openai`, etc.) |
| `LLM_API_KEY` | API key for LLM provider |
| `SARVAM_API_KEY` | Sarvam AI key for multilingual STT and TTS |

### Frontend (`orca-frontend/.env.local`)
| Variable | Description |
| :--- | :--- |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Google Maps JavaScript & Tile API Key |
| `NEXT_PUBLIC_API_URL` | URL of the running FastAPI backend (`http://localhost:8000`) |

---

## 🧪 Testing & Verification

### Backend Tests
```powershell
cd orca-backend
.\setup.ps1 -Test
# Or directly via pytest:
pytest tests/ -q
```

### Smoke Test Running API
```powershell
cd orca-backend
.\setup.ps1 -Smoke
```

---

## 📜 Documentation & Presentations
- **SIH Judge Preparation Guide**: [SIH_JUDGE_PREPARATION_GUIDE.md](SIH_JUDGE_PREPARATION_GUIDE.md)
- **Features Deep Dive**: [docs/ORCA_FEATURES_GUIDE.md](docs/ORCA_FEATURES_GUIDE.md)
- **Presentation Deck**: [SIH-2026.pptx_20260910_171820_0000.pdf](SIH-2026.pptx_20260910_171820_0000.pdf)
- **Architecture & Frontend Specification**: [FloatChat — Frontend Engineering & Integration Specification.pdf](FloatChat%20—%20Frontend%20Engineering%20&%20Integration%20Specification.pdf)

---

## 🛡️ License
Proprietary & Confidential — Smart India Hackathon (SIH) 2026. Developed by the ORCA Development Team.
