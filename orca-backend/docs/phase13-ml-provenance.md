# Phase 13 — ML Provenance: Lineage, API & Frontend Contract

## 1. Why provenance

Every observable ML decision must be explainable later: which model and feature
version produced it, what the inputs were, how confident it was, and whether it
was ever validated against an observed outcome.  Provenance turns a black-box
score into an auditable, reproducible record.

## 2. Ledger lineage

`GovernanceEngine.prediction_provenance(prediction_id)` returns an envelope with:

- **prediction** — value, label, confidence, uncertainty, snapshot;
- **lineage.model** — `{ name, version }`;
- **lineage.feature_version** — exact feature vector version;
- **lineage.inputs** — recorded input snapshot at prediction time;
- **lineage.ledger_path** — `live data -> feature pipeline -> model -> prediction
  -> decision -> observed outcome`;
- **lineage.matched_outcomes** — VALIDATED outcomes matched to this prediction.

## 3. Structured explainability

`build_structured_explanation()` produces deterministic factors derived from the
model's own logic, so they can **never contradict** the model output:

- **top_features** — strongest drivers first;
- **feature_contributions** — per-feature `{ feature, direction, weight }`,
  sorted by descending weight;
- **confidence_factors** — e.g. input-coverage effect on confidence;
- **data_quality_factors** — missing features per prediction;
- **warnings** — surfaced missing inputs.

## 4. Frontend provenance contract

`build_ml_provenance_contract()` is a **stable envelope** so the UI can render
an ML result without coupling to internals:

```
prediction (value / label / confidence / valid_until)
confidence (score / uncertainty / threshold)
validity   (status / horizon_hours)
model      (name / version)
data_sources
provenance (raw lineage)
warnings   (degraded / unavailable signals)
```

An `INPUT_DATA_UNAVAILABLE` status is surfaced as a warning — never as a
fabricated value.

## 5. Provenance API (`app/routers/ml.py`, prefix `/api/v1/ml`)

All GET / read-only:

| Route | Purpose |
|-------|---------|
| `/models/{model_id}` | model card + current production version |
| `/models/{model_id}/versions` | version history |
| `/models/{model_id}/metrics` | rolling evaluation (daily/weekly/monthly) |
| `/models/{model_id}/health` | operational health (status / drift / performance) |
| `/predictions/{prediction_id}` | ledger record for one prediction |
| `/predictions/{prediction_id}/provenance` | full lineage envelope |
| `/dashboard` | consolidated operational dashboard contract |

There is **no** `train` / `deploy` / `promote` HTTP endpoint — promotion is a
controlled, gated backend operation.

## 6. MCP governance tools (`app/mcp/tools_ml_governance.py`)

Four READ_ONLY tools registered in `analytics_governance` (verified 33 total tools):

- `analytics.model_status`
- `analytics.model_health`
- `analytics.prediction_provenance`
- `analytics.model_metrics`

No `train_and_deploy` exists, so the conversational agent can observe governance
state but **cannot** mutate or promote models.

## 7. Files

- `app/routers/ml.py` (new) — provenance API.
- `app/mcp/tools_ml_governance.py` (new) — READ_ONLY governance tools.
- `app/mcp/register.py` (changed) — registers governance tools.
- `app/main.py` (changed) — includes the ml router + governance loop in lifespan.
- `app/ml/governance.py` (new) — lineage + contract + explainability builders.
- `tests/test_phase13_ml.py` (gitignored) — provenance, API, MCP, contract.