# 🌊 ORCA - Ocean Reasoning with Collaborative Agent Platform

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.1-green)]()
[![Next.js](https://img.shields.io/badge/Next.js-15-black)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue)]()
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-green)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

**ORCA** (Ocean Reasoning with Collaborative Agent) is a production-oriented marine intelligence platform that combines heterogeneous marine data sources, performs deterministic spatial-temporal reasoning, produces transparent risk assessments, and returns evidence-backed recommendations for marine operations.

---

## 🎯 Key Capabilities

### 🤖 Agent-Based Architecture
- **IntentAgent** - LLM-powered NLU with deterministic post-processing for 10 Indian coastal languages
- **Orchestrator** - DAG-based agent execution with provenance tracking
- **RouteAgent** - Great-circle route generation with hazard/geofence checking
- **ScenarioAgent** - What-if projections (departure time, route variants, weather, speed)
- **GeofenceAgent** - EEZ, MPA, restricted zone compliance checking

### 🌊 Marine Data Integration
- **ARGO Profiles** - Real-time data via argopy (GDAC/ERDDAP)
- **Weather** - Wind, air temperature, precipitation
- **Waves** - Height, period, direction
- **Currents** - Surface/subsurface current data
- **Hazards** - Cyclones, storms, warnings
- **Geofences** - EEZ boundaries, MPAs, restricted zones

### 🧠 Deterministic Reasoning
- **SpatialReasoner** - PostGIS operations (distance, bearing, bbox, buffer, point-in-polygon)
- **TemporalReasoner** - Deterministic relative time parsing
- **RiskEngine** - Transparent scoring (wave 35%, wind 30%, current 15%, hazard 15%, geofence 5%)
- **DataFusionEngine** - Multi-source evidence aggregation with conflict detection

### 🗣️ Multilingual Voice Interface
- **10 Indian Coastal Languages**: English, Hindi, Malayalam, Tamil, Telugu, Bengali, Gujarati, Marathi, Odia, Kannada
- **STT** - Sarvam AI (Indian language optimized)
- **TTS** - ElevenLabs (premium) + Sarvam (backup)
- **Translation** - Google Cloud Translation
- **Language Detection** - Unicode script-based auto-detection

### 🛡️ Transparency & Verification
- **EvidenceBundle** - Canonical internal structure with full provenance
- **ProvenanceService** - Audit trails, lineage tracking, source health monitoring
- **Verifier** - Proof-carrying verification on all numeric claims
- **ConfidenceEngine** - 5-component scoring (spatial, temporal, density, quality, method)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with PostGIS extension
- (Optional) Supabase/Neon for managed PostgreSQL

### Backend Setup
```bash
cd apps/api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and DB connection

# Run database migrations
alembic -c alembic.ini upgrade head

# Start backend
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

### Environment Variables
Create `.env` from `.env.example`:
```bash
# Database - PostgreSQL with PostGIS
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/floatchat

# LLM Provider (OpenRouter for free tier)
LLM_PROVIDER=openrouter
LLM_API_KEY=your_openrouter_key
LLM_MODEL=anthropic/claude-3.5-sonnet

# Voice Providers
STT_PROVIDER=sarvam
STT_API_KEY=your_sarvam_key
TTS_PROVIDER=elevenlabs
TTS_API_KEY=your_elevenlabs_key
TRANSLATION_PROVIDER=google
TRANSLATION_API_KEY=your_google_key

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["http://localhost:3000"]

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 🏗️ Architecture

```
orca/
├── apps/
│   ├── api/                    # FastAPI Backend
│   │   ├── app/
│   │   │   ├── agents/         # IntentAgent, Orchestrator, RouteAgent, ScenarioAgent, GeofenceAgent
│   │   │   ├── data/           # ARGO, Weather, Wave, Current, Hazard clients
│   │   │   ├── routers/        # /chat, /profiles, /voice, /risk, /scenarios, /route, /hazards
│   │   │   ├── schemas/        # Pydantic models (query, evidence, route, marine, hazard, scenario)
│   │   │   ├── services/       # RiskEngine, SpatialReasoner, TemporalReasoner, DataFusion, Provenance
│   │   │   ├── db/             # SQLAlchemy + PostGIS models
│   │   │   └── main.py         # FastAPI app entry
│   │   ├── requirements.txt
│   │   └── alembic.ini         # Database migrations
│   │
│   └── web/                    # Next.js 15 Frontend
│       ├── app/                # App Router pages
│       ├── components/
│       │   ├── chat/           # ChatInterface, VoiceRecorder
│       │   ├── dashboard/      # CommandCenterDashboard
│       │   ├── map/            # FloatMap, WaveLayer, WindLayer, HazardLayer, RouteLayer
│       │   └── charts/         # DepthProfileChart, TimeSeriesChart
│       └── lib/                # api-client, schemas
│
├── packages/
│   └── shared-types/           # TypeScript/Python shared schemas
│
├── docs/                       # Architecture, API contracts, data dictionary, safety policy
├── tests/                      # Unit tests
└── .github/workflows/          # CI/CD pipelines
```

---

## 📡 API Endpoints

### Chat
```
POST   /api/v1/chat              # Main chat endpoint
GET    /api/v1/chat/history      # Chat history
```

### Voice
```
POST   /api/v1/voice/transcribe  # STT (Sarvam)
POST   /api/v1/voice/synthesize  # TTS (ElevenLabs/Sarvam)
POST   /api/v1/voice/translate   # Translation (Google)
POST   /api/v1/voice/detect-language
GET    /api/v1/voice/providers
GET    /api/v1/voice/languages
```

### Marine Data
```
GET    /api/v1/profiles/search           # ARGO profile search
GET    /api/v1/datasets/status           # Dataset health & freshness
GET    /api/v1/query-runs/{id}           # Query run provenance
GET    /api/v1/exports/csv               # Export results as CSV
```

### Risk & Route
```
POST   /api/v1/risk/briefing       # Marine condition briefing
POST   /api/v1/route/analyze       # Route safety analysis
POST   /api/v1/hazards/search      # Hazard search
```

### Scenarios & Alerts
```
POST   /api/v1/scenarios/create          # Create what-if scenario
POST   /api/v1/scenarios/compare         # Compare scenarios
POST   /api/v1/alerts/rules              # Create alert rule
GET    /api/v1/alerts/rules              # List alert rules
POST   /api/v1/alerts/events/{id}/acknowledge
POST   /api/v1/alerts/events/{id}/resolve
POST   /api/v1/alerts/check              # Manual alert check
```

### Health
```
GET    /api/v1/health              # Health check
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Unit tests only
pytest tests/test_unit.py -v

# Run specific test
pytest tests/test_unit.py::TestRiskEngine::test_elevated_risk_conditions -v
```

---

## 📊 Verification & Compliance

### Definition of Done (Vertical Slice)
- ✅ `GET /health` returns 200
- ✅ `POST /api/v1/chat` returns structured query + map + charts + evidence card
- ✅ No unverified numeric claims in response
- ✅ All charts show units, sample counts, date ranges
- ✅ Unit tests passing

### Safety & Compliance
- **Official Warning Disclaimer** - All risk outputs include disclaimer
- **Conservative Scoring** - Risk engine biases toward safety
- **Evidence-First** - Every numeric claim backed by EvidenceBundle
- **Audit Trail** - Full provenance for every query execution

---

## 🔑 API Keys Required

| Provider | Purpose | Free Tier |
|----------|---------|-----------|
| **OpenRouter** | LLM (Claude 3.5 Sonnet) | ✅ Free tier available |
| **Sarvam AI** | STT/TTS (Indian languages) | ✅ Free tier |
| **ElevenLabs** | TTS (Premium voices) | ✅ Free tier |
| **Google Cloud** | Translation API | ✅ Free tier |

> All keys stored in `.env` - never committed to git (`.gitignore` enforced)

---

## 📁 Project Structure Highlights

### Key Files
```
apps/api/app/
├── agents/
│   ├── __init__.py              # BaseAgent, ExecutionContext, AgentRegistry
│   ├── intent_agent.py          # NLU + entity extraction
│   ├── orchestrator.py          # DAG-based orchestration
│   ├── scenario_agent.py        # What-if scenarios
│   ├── route_agent.py           # Route generation + safety
│   └── geofence_agent.py        # EEZ/MPA compliance
├── services/
│   ├── risk_engine.py           # Transparent risk scoring
│   ├── spatial_reasoner.py      # PostGIS operations
│   ├── temporal_reasoner.py     # Deterministic time parsing
│   ├── data_fusion.py           # Multi-source evidence fusion
│   ├── provenance.py            # Audit trails & lineage
│   ├── verifier.py              # Numeric claim verification
│   ├── confidence.py            # Confidence scoring
│   ├── query_planner.py         # NL → StructuredQuery
│   ├── query_executor.py        # SQL execution
│   └── voice_providers.py       # STT/TTS/Translation interfaces
├── schemas/
│   ├── query.py           # StructuredQuery, Intent, Region types
│   ├── evidence.py        # EvidenceRecord, ConfidenceScore
│   ├── provenance.py      # EvidenceBundle, ProvenanceRecord
│   ├── route.py           # RouteAnalysisRequest/Response
│   ├── marine.py          # MarineConditionResponse
│   ├── hazard.py          # HazardArea, HazardWarning
│   └── scenario.py        # ScenarioRequest, AlertRule, AlertEvent
└── routers/               # All API endpoints
```

---

## 🚢 Deployment

### Database (Supabase/Neon)
```sql
-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Run migrations via alembic
alembic -c apps/api/alembic.ini upgrade head
```

### Backend (Railway/Render/Fly.io)
```bash
# Set environment variables in platform dashboard
# Deploy from GitHub repo (apps/api subdirectory)
```

### Frontend (Vercel)
```bash
cd apps/web
vercel --prod
```

---

## 📚 Documentation

| Document | Location |
|----------|----------|
| Architecture | `docs/architecture.md` |
| API Contracts | `docs/api-contract.md` |
| Data Dictionary | `docs/data-dictionary.md` |
| Safety Policy | `docs/safety.md` |

---

## 🤝 Contributing

```bash
# Fork & clone
git clone https://github.com/your-org/floatchat.git

# Create feature branch
git checkout -b feature/amazing-feature

# Run tests
pytest tests/ -v

# Commit & push
git commit -m "feat: add amazing feature"
git push origin feature/amazing-feature

# Open PR
```

### Code Standards
- **Python**: Black, Ruff, type hints required
- **TypeScript**: ESLint, Prettier, strict mode
- **Commits**: Conventional commits (feat:, fix:, docs:, etc.)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **ARGO Program** - Global ocean observing network
- **INCOIS** - Indian National Centre for Ocean Information Services
- **Sarvam AI** - Indian language speech models
- **ElevenLabs** - High-quality multilingual TTS
- **OpenRouter** - Unified LLM API gateway

---

<div align="center">
  <strong>ORCA - Making the ocean transparent, one query at a time 🌊</strong>
</div>