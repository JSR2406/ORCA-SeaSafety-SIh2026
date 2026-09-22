# Backend Configuration
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Dict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Single source of truth: the repo-root .env, resolved by ABSOLUTE
        # path so the app behaves identically regardless of the working
        # directory the process is launched from.  (A relative ".env" would
        # silently load a different file based on CWD.)
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # Operator authentication for maritime-authority writes (alert publish /
    # acknowledge).  Empty secret or credentials => those endpoints fail closed.
    auth_jwt_secret: str = ""
    auth_operator_email: str = ""
    auth_operator_password: str = ""

    # Database - PostgreSQL with PostGIS
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/floatchat"
    geom_srid: int = 4326

    # Supabase (managed PostgreSQL/PostGIS)
    supabase_url: str = ""
    supabase_project_ref: str = ""
    supabase_publishable_key: str = ""
    supabase_jwks_url: str = ""

    # LLM - OpenRouter for free tier access
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_model: str = "nvidia/nemotron-3.5-lightning:free"
    llm_temperature: float = 0.1

    # Voice Providers - Sarvam + ElevenLabs
    stt_provider: str = "sarvam"
    stt_api_key: str = ""
    tts_provider: str = "elevenlabs"
    tts_api_key: str = ""
    translation_provider: str = "google"
    translation_api_key: str = ""

    # Data Sources
    argo_gdac_url: str = "https://data-argo.ifremer.fr/argo"
    erddap_url: str = "https://erddap.ifremer.fr/erddap"
    argovis_url: str = "https://argovis.colorado.edu"
    # Legacy ARGO/Parquet cache location (CacheManager, ArgoClient).
    cached_data_path: str = "data/cached"

    # Real-time marine sources (INCOIS / IMD / MOSDAC).
    # Keep DISABLED by default: they are unreliable (IMD needs IP whitelisting,
    # MOSDAC's geoserver is retired, INCOIS ERDDAP tides are ARGO-only), so the
    # live stack relies on Open-Meteo / CoastWatch / Storm Glass / OpenWeather /
    # JTWC.  Leave API keys empty -> adapter reports "not connected" (no fake
    # data).  Enable individually when an endpoint is reachable.
    incois_base_url: str = "https://incois.gov.in"
    incois_api_key: str = ""
    incois_enabled: bool = False
    imd_base_url: str = "https://api.imd.gov.in"
    imd_api_key: str = ""
    imd_enabled: bool = False
    mosdac_base_url: str = "https://mosdac.gov.in"
    mosdac_api_key: str = ""
    mosdac_enabled: bool = False

    # Open-source scraping endpoints
    incois_erddap_url: str = "https://erddap.incois.gov.in"
    incois_las_url: str = "https://las.incois.gov.in"
    incois_pfz_url: str = "https://incois.gov.in/MarineFisheries/TextDataHome"
    incois_rsmc_url: str = "https://incois.gov.in/oceanservices/rsmc.jsp"
    nho_navarea_url: str = "https://hydrobharat.gov.in/navarea-warnings"
    mosdac_geoserver_url: str = "https://mosdac.gov.in/geoserver/wms"
    # IMD public API base (separate from general IMD site)
    imd_public_api_url: str = "https://api.imd.gov.in/api/v1"
    # Open-Meteo keyless forecast APIs (fallback when gov APIs are unavailable)
    open_meteo_marine_url: str = "https://marine-api.open-meteo.com/v1/marine"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_enabled: bool = True

    # NOAA CoastWatch ERDDAP - keyless near-real-time satellite products.
    # Point-queryable real lat/lon axes (MUR SST, VIIRS chl where allowed).
    # Used as fallback for MOSDAC's dead geoserver and PFZ front detection.
    coastwatch_erddap_url: str = "https://coastwatch.pfeg.noaa.gov/erddap"
    coastwatch_mur_sst_dataset: str = "jplMURSST41"        # near-real-time SST
    coastwatch_chl_dataset: str = "nesdisVHNchlaDaily"     # VIIRS chl (may 403)
    coastwatch_enabled: bool = True

    # Storm Glass (keyed API) - global tide extremes (high/low + height).
    # Global coverage, free tier = 10 requests/day (non-commercial).  One
    # request returns a multi-day extremes window, so the scheduler seeds a
    # small set of coastal anchor points on a daily cadence.
    stormglass_base_url: str = "https://api.stormglass.io/v2"
    stormglass_api_key: str = ""
    stormglass_enabled: bool = True

    # JTWC (Joint Typhoon Warning Center) - keyless cyclone warnings feed.
    # Public RSS (jtwc.rss) + per-storm warning bulletins on metoc.navy.mil.
    # Bulletin products section 403s some networks; GDACS is the reliable
    # keyless warnings fallback with full geometry.
    jtwc_base_url: str = "https://www.metoc.navy.mil"
    jtwc_enabled: bool = True

    # GDACS (EU public framework feed, CC BY 4.0) - keyless cyclone alerts.
    # RSS carries center point, affected-area bbox, validity window, severity.
    gdacs_base_url: str = "https://www.gdacs.org"
    gdacs_enabled: bool = True

    # OpenWeatherMap (keyed API) - secondary fallback + gap filling.
    # 1.3 free: /data/2.5/weather, /data/2.5/forecast, /data/3.0/onecall.
    # API key must be provided to enable; otherwise this source reports
    # NOT_CONFIGURED (no fabricated weather).
    openweather_base_url: str = "https://api.openweathermap.org/data"
    openweather_api_key: str = ""
    openweather_enabled: bool = True
    openweather_units: str = "metric"  # metric|imperial|standard

    # TEST-MOCK / sample data sources (evaluation only, never LIVE).
    # Synthetic marine data used to exercise the pipeline until real
    # government API keys are approved.  Report explicitly as TEST_MOCK.
    mock_marine_enabled: bool = False
    mock_weather_enabled: bool = False
    mock_warnings_enabled: bool = False

    # Data acquisition behaviour
    data_timeout_seconds: float = 30.0
    data_retry_limit: int = 3
    data_retry_backoff_seconds: float = 2.0
    # Default poll interval seconds (used when a source has no specific interval).
    data_poll_interval_seconds: int = 900
    # Per-source poll interval overrides, e.g. {"incois": 1800, "imd": 3600}
    # Storm Glass is capped at 10 req/day on the free tier -> daily poll of the
    # anchored ports; coastwatch/openmeteo are keyless so can poll harder.
    source_poll_interval_seconds: Dict[str, int] = {
        "stormglass": 24 * 3600,
        "coastwatch": 6 * 3600,
        "openmeteo": 1 * 3600,
        "openweather": 3 * 3600,
        "jtwc": 3 * 3600,
        "gdacs": 3 * 3600,
    }

    # Minimal polling scheduler
    scheduler_enabled: bool = True
    scheduler_idle_wait_seconds: int = 60

    # Freshness thresholds (seconds) - data older than the threshold is STALE.
    ocean_freshness_seconds: int = 6 * 3600        # 6h
    weather_freshness_seconds: int = 3 * 3600      # 3h
    wave_freshness_seconds: int = 6 * 3600         # 6h
    tide_freshness_seconds: int = 24 * 3600        # 24h
    pfz_freshness_seconds: int = 24 * 3600         # 24h
    warning_freshness_seconds: int = 3 * 3600      # 3h

    # Physical plausibility bounds for validation (configurable)
    sst_min_c: float = -2.5
    sst_max_c: float = 45.0
    wave_max_m: float = 20.0
    wind_max_ms: float = 70.0
    current_max_ms: float = 5.0

    # Embeddings (hybrid RAG). Leave empty -> retrieval is FTS-only.
    embeddings_api_key: str = ""
    embeddings_endpoint: str = ""
    embeddings_model: str = "text-embedding-3-small"
    embeddings_dimensions: int = 1536

    # RAG generation layer (Phase 3.5 Q&A).  When no LLM key is configured the
    # answer layer falls back to an honest extractive summary of the retrieved
    # chunks (never fabricated prose).
    rag_generation_enabled: bool = True
    rag_generation_timeout_seconds: float = 30.0
    rag_max_context_chars: int = 4000         # retrieved-context budget per prompt
    rag_max_citations: int = 5                 # citation markers the LLM may use
    rag_grounding_min_tokens: int = 3          # min answer tokens to judge grounding
    rag_min_top_coverage: float = 0.5          # top-chunk query-token coverage
                                               # below which -> no_documents

    # Orchestration (Phase 4) execution bounds.
    orchestrator_max_tasks: int = 12
    orchestrator_max_tool_calls: int = 30
    orchestrator_max_retries: int = 2
    orchestrator_max_total_retries: int = 6
    orchestrator_max_repairs: int = 2
    orchestrator_parallel: int = 4
    orchestrator_timeout_seconds: float = 60.0
    orchestrator_task_timeout_seconds: float = 30.0
    orchestrator_planner_llm_enabled: bool = False

    # Phase 7 input guards - bound request size at the edge so no single
    # message can create unbounded parsing/embedding work.
    orchestrator_max_message_chars: int = 4000
    websocket_max_message_chars: int = 4000

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    max_audio_size_mb: int = 10
    rate_limit_rpm: int = 60
    cors_origins: List[str] = ["http://localhost:3000"]

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # ------------------------------------------------------------------
    # Phase 11 - Proactive marine intelligence & autonomous operations.
    # ------------------------------------------------------------------
    # Bounded proactive engine (event/alert scheduling).  One worker processes
    # the event queue deterministically; multiple workers would duplicate work,
    # so this must be 1 in production or run behind a leader lock.
    proactive_enabled: bool = True
    proactive_worker_queue_size: int = 128
    proactive_tick_seconds: int = 60            # event/alert evaluation cadence
    proactive_source_refresh_seconds: int = 900 # source refresh cadence

    # Geofence monitoring
    geofence_approach_km: float = 25.0          # distance at which APPROACHING fires
    geofence_refresh_seconds: int = 120
    geofence_max_active: int = 64               # bounded set of monitored vessels

    # Restriction monitoring
    restriction_scan_seconds: int = 300
    restriction_max_active: int = 256

    # Alert lifecycle bounds
    alert_dedupe_window_seconds: int = 3600     # identical events deduped within
    alert_default_ttl_seconds: int = 24 * 3600  # default validity if none given
    alert_max_escalations: int = 3              # CAUTION->WARNING->HIGH->CRITICAL
    alert_escalation_step_seconds: int = 3600   # min time before an escalation

    # Material-change threshold (Phase 12 ML integration): do not raise an alert
    # purely because an ML score changed by less than this (0..1).
    alert_ml_material_change: float = 0.10

    # Source health : consecutive failures that flip AVAILABLE -> FAILED.
    source_failure_threshold: int = 3
    source_recovery_ticks: int = 2               # successful ticks to flip RECOVERED

    # User alert preferences default mode per category.
    alert_default_mode: str = "important_only"   # immediate|important_only|digest|disabled

    # ------------------------------------------------------------------
    # Phase 12 - Production ML, Forecasting & MLOps.
    # ------------------------------------------------------------------
    # Feature store: keep features warm for a bounded horizon (in hours) so the
    # store is never a stale or unbounded cache.
    features_cache_hours: int = 24
    ml_enabled: bool = True                     # master switch for model service
    model_registry_max_candidates: int = 8      # bounded candidate window

    # Model freshness / caching
    ml_cache_ttl_seconds: int = 300             # prediction cache TTL (5 min)
    ml_cache_max_entries: int = 256
    ml_forecast_horizon_days: int = 7           # scenario forecast horizon

    # Drift detection
    ml_drift_warmup_samples: int = 50           # samples before drift checks arm
    ml_drift_threshold: float = 0.30            # PSI/KS drift alarm threshold
    ml_drift_ttl_seconds: int = 600             # re-check cadence

    # Uncertainty budgets (conflict/uncertain outcomes)
    ml_default_confidence: float = 0.85
    ml_uncertain_confidence_threshold: float = 0.60  # below -> PREDICTION_UNCERTAIN

    # ------------------------------------------------------------------
    # Phase 13 - Continuous learning, model governance & ML provenance.
    # ------------------------------------------------------------------
    ml_governance_enabled: bool = True   # master switch for the governance loop
    ml_learning_enabled: bool = True     # master switch for retraining/candidates

    # Prediction ledger bounds (bounded, never unbounded growth).
    ml_ledger_max_predictions: int = 2000
    ml_outcome_max_entries: int = 2000

    # Prediction -> outcome matching geometry (Kochi 09:00 +6h -> 15:00 hull).
    ml_match_spatial_km: float = 25.0          # max lateral distance to match
    ml_match_temporal_window_hours: float = 3.0  # tolerance around target_time

    # Rolling evaluation windows (seconds).  daily/weekly/monthly.
    ml_eval_histogram_daily_seconds: int = 24 * 3600
    ml_eval_histogram_weekly_seconds: int = 7 * 24 * 3600
    ml_eval_histogram_monthly_seconds: int = 30 * 24 * 3600

    # Retraining policies.
    ml_retrain_schedule_enabled: bool = True
    ml_retrain_schedule_days: int = 7         # scheduled candidate cadence
    ml_retrain_min_ground_truth: int = 30     # GT rows before a retrain is legal
    ml_retrain_performance_degrade_mae_ratio: float = 1.25  # MAE > 1.25x baseline

    # Promotion gate thresholds (candidate -> production).
    ml_promotion_min_accuracy: float = 0.60
    ml_promotion_min_calibration: float = 0.85
    ml_promotion_max_latency_ms: float = 250.0
    ml_promotion_require_safety_regression_zero: bool = True

    # Ground-truth ingestion and shadow cadence.
    ml_ground_truth_default_quality: float = 0.9  # when no explicit quality given
    ml_shadow_enabled: bool = True          # shadow predictions recorded for challengers

    # ------------------------------------------------------------------
    # Phase 16 - trained (supervised) models: fit first, then promote & serve.
    # ------------------------------------------------------------------
    ml_trained_enabled: bool = True            # master switch for fitted models
    ml_artifact_dir: str = "data/ml/artifacts"  # fitted-estimator persistence
    ml_registry_path: str = "data/ml/registry.json"  # registry state snapshot
    ml_ledger_path: str = "data/ml/ledger.json"      # prediction+outcome ledger snapshot
    ml_feature_store_path: str = "data/ml/feature_store.json"  # feature-store snapshot
    ml_train_default_samples: int = 2000        # pilot dataset rows per model
    ml_train_seed: int = 42                     # deterministic generator seed
    ml_train_noise: float = 0.08                # label noise (realistic)
    ml_promotion_beats_baseline_ratio: float = 0.95  # candidate cv-rmse must be
                                                     # <= 95% of production rmse.


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()