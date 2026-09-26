# Machine Learning Layer (/ml)

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
