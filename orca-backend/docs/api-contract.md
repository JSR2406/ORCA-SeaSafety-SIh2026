# FloatChat API Contract

## Overview
All endpoints return JSON. Errors follow RFC 7807 Problem Details format.

---

## Common Types

```typescript
// Request ID header on all responses
X-Request-ID: string (UUID)

// Error Response
interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  request_id: string;
}

// Pagination
interface PaginationParams {
  limit?: number;      // default 100, max 1000
  offset?: number;     // default 0
}

interface PaginatedResponse<T> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
}
```

---

## 1. Health Check

### GET `/health`

**Response 200**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "demo_mode": false,
  "database": "connected",
  "timestamp": "2026-08-20T12:00:00Z"
}
```

---

## 2. Chat Endpoint

### POST `/api/v1/chat`

**Request**
```json
{
  "message": "Show temperature profiles in the Arabian Sea during July 2025",
  "session_id": "optional-uuid",
  "language": "en-IN",
  "mode": "researcher", // "fisherfolk" | "researcher"
  "context": {}
}
```

**Response 200**
```json
{
  "query_run_id": "uuid",
  "answer": "Found 47 temperature profiles from 12 floats in the Arabian Sea during July 2025...",
  "language": "en-IN",
  "structured_query": {
    "intent": "profile_search",
    "region": { "type": "named_region", "name": "Arabian Sea" },
    "time_range": { "start": "2025-07-01", "end": "2025-07-31" },
    "variables": ["temperature"],
    "quality_filter": "recommended"
  },
  "visualizations": {
    "map": { /* MapLibre GeoJSON */ },
    "charts": [
      { "type": "depth_profile", "data": [...], "config": {...} },
      { "type": "time_series", "data": [...], "config": {...} }
    ]
  },
  "evidence": {
    "float_ids": [1901234, 1901235, ...],
    "profile_count": 47,
    "observation_count": 12340,
    "region": { "min_lat": 8.0, "max_lat": 22.0, "min_lon": 65.0, "max_lon": 78.0 },
    "depth_range_m": { "min": 0, "max": 2000 },
    "time_range": { "start": "2025-07-02", "end": "2025-07-29" },
    "quality_filters": ["recommended"],
    "data_freshness": { "latest_profile": "2025-07-29", "days_old": 22 },
    "confidence": {
      "label": "high",
      "score": 0.87,
      "components": {
        "spatial_coverage": 0.9,
        "temporal_freshness": 0.8,
        "sample_density": 0.85,
        "measurement_quality": 0.9,
        "method_stability": 0.88
      },
      "explanation": "Good spatial coverage with 12 floats across the region. Data is 22 days old. High measurement quality with recommended QC.",
      "limitations": ["No data for last 3 days of July", "Sparse coverage near coast"]
    },
    "query_steps": [
      { "step": 1, "tool": "search_profiles", "params": {...}, "result_count": 47 },
      { "step": 2, "tool": "depth_profile_summary", "params": {...}, "result_count": 50 }
    ],
    "limitations": ["Coastal zone under-sampled", "No real-time data"],
    "source_identifiers": {
      "dataset": "argo_indian_ocean_2015_2025",
      "snapshot": "2026-08-15",
      "doi": "10.17882/42182"
    }
  },
  "audio_url": null
}
```

**Response 200 (Needs Clarification)**
```json
{
  "query_run_id": "uuid",
  "status": "needs_clarification",
  "clarification_question": "To check conditions 40 km offshore, I need your departure location (port or coordinates). Where will you depart from?",
  "partial_query": {
    "intent": "marine_condition_briefing",
    "distance_km": 40,
    "region": null,
    "time_range": { "start": "2026-08-21", "end": "2026-08-21" }
  }
}
```

---

## 3. Query Planning

### POST `/api/v1/query/plan`

**Request**
```json
{
  "message": "Show temperature profiles in the Arabian Sea during July 2025",
  "language": "en-IN"
}
```

**Response 200**
```json
{
  "status": "ready",
  "intent": "profile_search",
  "language": "en-IN",
  "query": {
    "intent": "profile_search",
    "language": "en-IN",
    "region": { "type": "named_region", "name": "Arabian Sea" },
    "time_range": { "start": "2025-07-01", "end": "2025-07-31" },
    "depth_range_m": { "min": 0, "max": 2000 },
    "variables": ["temperature"],
    "quality_filter": "recommended",
    "aggregation": "profile",
    "limit": 500
  },
  "clarification_question": null,
  "warnings": []
}
```

---

## 4. Query Execution

### POST `/api/v1/query/execute`

**Request**
```json
{
  "query": {
    "intent": "profile_search",
    "region": { "type": "bbox", "min_lat": 8.0, "max_lat": 22.0, "min_lon": 65.0, "max_lon": 78.0 },
    "time_range": { "start": "2025-07-01", "end": "2025-07-31" },
    "depth_range_m": { "min": 0, "max": 2000 },
    "variables": ["temperature", "salinity"],
    "quality_filter": "recommended",
    "aggregation": "profile",
    "limit": 500
  },
  "session_id": "uuid"
}
```

**Response 200**
```json
{
  "query_run_id": "uuid",
  "execution_status": "success",
  "results": {
    "profiles": [
      {
        "profile_id": 12345,
        "platform_number": 1901234,
        "cycle_number": 156,
        "profile_time": "2025-07-15T06:30:00Z",
        "latitude": 12.5,
        "longitude": 72.3,
        "observations": [
          { "depth_m": 10, "temperature_c": 28.5, "salinity_psu": 35.2, "temperature_qc": 1, "salinity_qc": 1 },
          { "depth_m": 50, "temperature_c": 27.8, "salinity_psu": 35.3, "temperature_qc": 1, "salinity_qc": 1 }
        ]
      }
    ],
    "metadata": {
      "float_count": 12,
      "profile_count": 47,
      "observation_count": 12340,
      "time_range": { "start": "2025-07-02", "end": "2025-07-29" },
      "depth_range_m": { "min": 0, "max": 1980 },
      "region": { "min_lat": 8.0, "max_lat": 22.0, "min_lon": 65.0, "max_lon": 78.0 }
    }
  },
  "evidence": { /* same as chat response evidence */ }
}
```

---

## 5. Voice Endpoints

### POST `/api/v1/voice/transcribe`

**Request** (multipart/form-data)
- `audio`: file (WAV, MP3, WebM, max 10MB)
- `language_hint`: "ml-IN" | "hi-IN" | "en-IN" | "auto"

**Response 200**
```json
{
  "transcript": "നാളെ 40 കിലോമീറ്റർ കടലിലേക്ക് പോകുന്നത് സുരക്ഷിതമാണോ?",
  "language": "ml-IN",
  "confidence": 0.92,
  "duration_seconds": 3.2
}
```

### POST `/api/v1/voice/synthesize`

**Request**
```json
{
  "text": "നാളെ കടൽ അവസ്ഥ മിതമാണെങ്കിലും, அதிகൃത മുന്നറിയിപ്പ് പരിശോധിക്കുക.",
  "language": "ml-IN",
  "voice": "female" // optional
}
```

**Response 200**
```json
{
  "audio_url": "https://storage.supabase.co/floatchat-audio/uuid.mp3",
  "duration_seconds": 4.1,
  "format": "mp3"
}
```

---

## 6. Profile Search

### POST `/api/v1/profiles/search`

**Request**
```json
{
  "region": { "type": "radius", "lat": 10.0, "lon": 76.0, "radius_km": 100 },
  "time_range": { "start": "2025-01-01", "end": "2025-12-31" },
  "depth_range_m": { "min": 0, "max": 1000 },
  "variables": ["temperature", "salinity", "oxygen"],
  "quality_filter": "recommended",
  "limit": 200
}
```

**Response 200**
```json
{
  "profiles": [...],
  "metadata": { /* same as query execute */ }
}
```

---

## 7. Anomaly Detection

### POST `/api/v1/anomalies/detect`

**Request**
```json
{
  "variable": "temperature",
  "region": { "type": "named_region", "name": "Arabian Sea" },
  "depth_m": 100,
  "reference_period": { "start": "2015-01-01", "end": "2020-12-31" },
  "analysis_period": { "start": "2021-01-01", "end": "2025-12-31" },
  "threshold_std": 2.0
}
```

**Response 200**
```json
{
  "anomaly_detected": true,
  "variable": "temperature",
  "depth_m": 100,
  "region": { "name": "Arabian Sea" },
  "reference_baseline": {
    "mean": 27.2,
    "std": 0.8,
    "sample_count": 15420
  },
  "analysis_period": {
    "mean": 28.1,
    "std": 0.9,
    "sample_count": 8930
  },
  "difference": 0.9,
  "difference_std": 1.12,
  "threshold_exceeded": true,
  "affected_locations": [
    { "lat": 12.5, "lon": 72.3, "anomaly_c": 1.2, "profiles": 45 }
  ],
  "confidence": { "label": "medium", "score": 0.72, ... },
  "limitations": ["Sparse deep measurements before 2018", "Seasonal aliasing possible"]
}
```

---

## 8. Scenario Projection

### POST `/api/v1/scenarios/project`

**Request**
```json
{
  "variable": "temperature",
  "region": { "type": "named_region", "name": "Arabian Sea" },
  "depth_m": 100,
  "trend_window": { "start": "2015-01-01", "end": "2025-12-31" },
  "projection_years": 5,
  "model": "linear_trend",
  "assumptions": ["Linear trend continues", "No policy intervention", "Natural variability unchanged"]
}
```

**Response 200**
```json
{
  "scenario": {
    "variable": "temperature",
    "region": { "name": "Arabian Sea" },
    "depth_m": 100,
    "historical_trend": {
      "slope_per_year": 0.032,
      "intercept": 27.1,
      "r_squared": 0.68,
      "p_value": 0.001,
      "residual_std": 0.15
    },
    "projection": {
      "years": [2026, 2027, 2028, 2029, 2030],
      "values": [28.4, 28.43, 28.46, 28.49, 28.52],
      "uncertainty_lower": [28.1, 28.1, 28.1, 28.05, 28.05],
      "uncertainty_upper": [28.7, 28.75, 28.8, 28.85, 28.9]
    },
    "model": "linear_trend",
    "assumptions": ["Linear trend continues", "No policy intervention", "Natural variability unchanged"],
    "uncertainty_method": "prediction_interval_95",
    "label": "SCENARIO — Not a forecast. Assumes linear continuation of observed trend.",
    "confidence": { "label": "low", "score": 0.45, ... }
  }
}
```

---

## 9. Risk Briefing

### POST `/api/v1/risk/briefing`

**Request**
```json
{
  "origin": { "lat": 9.93, "lon": 76.27 }, // Kochi
  "destination": { "lat": 9.5, "lon": 75.5 }, // 40km offshore
  "departure_time": "2026-08-21T06:00:00Z",
  "vessel_type": "fishing_boat",
  "include_forecast": true
}
```

**Response 200**
```json
{
  "overall_label": "moderate",
  "components": [
    {
      "name": "waves",
      "label": "moderate",
      "reason": "Significant wave height 1.5-2.0m from ARGO-derived climatology",
      "source": "ARGO climatology + ERA5 reanalysis",
      "data_freshness": "climatology"
    },
    {
      "name": "wind",
      "label": "low",
      "reason": "Wind speed 8-12 knots from historical July averages",
      "source": "ERA5 reanalysis",
      "data_freshness": "2024 climatology"
    },
    {
      "name": "currents",
      "label": "moderate",
      "reason": "Surface current 0.5-1.0 knots westward",
      "source": "ARGO trajectory analysis",
      "data_freshness": "2025 observations"
    },
    {
      "name": "warnings",
      "label": "unavailable",
      "reason": "No official INCOIS warning data integrated",
      "source": "none",
      "data_freshness": "unavailable"
    },
    {
      "name": "data_coverage",
      "label": "partial",
      "reason": "3 floats within 50km in last 30 days",
      "source": "ARGO",
      "data_freshness": "12 days old"
    }
  ],
  "confidence": {
    "label": "medium",
    "score": 0.62,
    "components": {...},
    "explanation": "Moderate confidence. Wave data from climatology, not forecast. No official warnings available.",
    "limitations": ["No real-time forecast", "No official warning integration", "Climatology only"]
  },
  "advisory": "Follow the latest official INCOIS warning before departure. This briefing is based on historical observations only.",
  "data_status": "partial",
  "latest_data_timestamp": "2026-08-08T12:00:00Z"
}
```

---

## 10. CSV Export

### POST `/api/v1/exports/csv`

**Request**
```json
{
  "query_run_id": "uuid",
  "format": "profiles" // "profiles" | "observations" | "summary"
}
```

**Response 200** (streams CSV)
```
Content-Type: text/csv
Content-Disposition: attachment; filename="floatchat_export_20260820.csv"

profile_id,platform_number,cycle_number,profile_time,latitude,longitude,temperature_c,salinity_psu,depth_m
12345,1901234,156,2025-07-15T06:30:00Z,12.5,72.3,28.5,35.2,10
...
```

---

## 11. Dataset Status

### GET `/api/v1/datasets/status`

**Response 200**
```json
{
  "datasets": [
    {
      "name": "argo_indian_ocean_2015_2025",
      "region": "Indian Ocean (30°S-30°N, 30°E-120°E)",
      "start_time": "2015-01-01",
      "end_time": "2025-12-31",
      "source": "ARGO GDAC",
      "source_version": "2026-07",
      "record_count": 2847392,
      "profile_count": 156432,
      "float_count": 2847,
      "ingested_at": "2026-08-15T10:30:00Z",
      "status": "active",
      "checksum": "sha256:..."
    }
  ],
  "demo_mode": false
}
```

---

## 12. Query Run Details

### GET `/api/v1/query-runs/{query_run_id}`

**Response 200**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "user_input": "Show temperature profiles...",
  "detected_language": "en-IN",
  "normalized_intent": "profile_search",
  "structured_query": {...},
  "tool_calls": [...],
  "execution_status": "success",
  "created_at": "2026-08-20T12:00:00Z",
  "evidence": {...},
  "narratives": [...],
  "scenarios": [...]
}
```

---

## Structured Query Schema (Reference)

```json
{
  "intent": "profile_search | timeseries_summary | depth_profile_summary | anomaly_detection | scenario_projection | marine_condition_briefing | dataset_explanation | export_results",
  "language": "en-IN | ml-IN | hi-IN | mr-IN",
  "region": {
    "type": "bbox | radius | polygon | named_region | route",
    "min_lat": 0.0, "max_lat": 0.0, "min_lon": 0.0, "max_lon": 0.0,
    "lat": 0.0, "lon": 0.0, "radius_km": 0.0,
    "coordinates": [[lon, lat], ...],
    "name": "Arabian Sea | Bay of Bengal | Kerala Coast"
  },
  "time_range": {
    "start": "2025-07-01",
    "end": "2025-07-31"
  },
  "depth_range_m": { "min": 0, "max": 2000 },
  "variables": ["temperature", "salinity", "oxygen", "chlorophyll"],
  "quality_filter": "all | recommended | good_only",
  "aggregation": "profile | daily | weekly | monthly | depth_bin",
  "limit": 500,
  "distance_km": 40,
  "origin": { "lat": 0.0, "lon": 0.0 },
  "destination": { "lat": 0.0, "lon": 0.0 },
  "departure_time": "2026-08-21T06:00:00Z",
  "vessel_type": "fishing_boat"
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/chat` | 30/min |
| `/voice/transcribe` | 10/min |
| `/voice/synthesize` | 20/min |
| `/query/execute` | 60/min |
| `/exports/csv` | 5/min |

---

## Versioning

- API version in path: `/api/v1/`
- Breaking changes → new version
- Deprecation notice: 3 months