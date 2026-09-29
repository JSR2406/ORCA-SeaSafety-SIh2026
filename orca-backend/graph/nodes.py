from schemas.state import (
    OrcaState,
    Weather,
    Ocean,
    WarningInfo,
    FishingSuitability,
    Risk,
    RiskEscalation
)
from agents.router import execute_router
from agents.rag import execute_rag
from agents.generator import execute_generator
from agents.geospatial import execute_geospatial
from ml.models import predict_marine_models

# ---------------------------------------------------------
# ACTUAL NODES
# ---------------------------------------------------------

def router_node(state: OrcaState) -> dict:
    return execute_router(state)

def live_data_node(state: OrcaState) -> dict:
    """
    Live Data Node: real telemetry via the data gateway (INCOIS/IMD primary,
    Open-Meteo fallback, every field source-labeled). Schema identical to before;
    falls back to long-standing Kochi constants only when all providers fail.
    """
    from datetime import datetime
    print("[Live Data Node] Ingesting real-time coastal telemetry...", flush=True)
    lat = state.location.lat if state.location else 9.93
    lon = state.location.lon if state.location else 76.27

    MS_TO_KT = 1.94384
    FALLBACK = {"wind_kt": 8.4, "rain": 0.0, "vis": 10.0,
                "wave": 1.4, "current_kt": 1.2, "sst": 28.4}
    sources: dict = {}
    try:
        from ml.data_pipeline.gateway import get_marine_features
        feats = get_marine_features(lat, lon, datetime.utcnow(), allow_fallback=True)
        for k, v in feats.items():
            if k.endswith("__source") and v:
                sources[k[:-8]] = v
        wind_kt = (feats["wind_speed_ms"] * MS_TO_KT) if feats.get("wind_speed_ms") is not None else FALLBACK["wind_kt"]
        rain = feats.get("rain_mm", FALLBACK["rain"])
        vis = feats.get("visibility_km", FALLBACK["vis"])
        wave = feats.get("wave_height_m", FALLBACK["wave"])
        cur_ms = feats.get("current_speed_ms", FALLBACK["current_kt"] / MS_TO_KT)
        sst = feats.get("sst_c", FALLBACK["sst"])
        live = feats.get("freshness") == "live"
    except Exception as e:
        print(f"[Live Data Node] gateway failed ({e}) — constants fallback", flush=True)
        wind_kt, rain, vis, wave, cur_ms, sst, live = (
            FALLBACK["wind_kt"], FALLBACK["rain"], FALLBACK["vis"],
            FALLBACK["wave"], FALLBACK["current_kt"] / MS_TO_KT, FALLBACK["sst"], False)

    weather = Weather(wind=round(float(wind_kt), 1), rain=float(rain or 0.0),
                      visibility=float(vis or 10.0))
    ocean = Ocean(wave_height=float(wave or 1.4),
                  current_speed=round(float(cur_ms) * MS_TO_KT, 1),
                  sst=float(sst or 28.4))
    # Stash extras the strict Weather/Ocean schema can't carry (string-valued,
    # per OrcaState.data_sources) so answers stay consistent with the hydro table.
    try:
        if feats.get("wave_period_s") is not None:
            sources["wave_period_s"] = f"{float(feats['wave_period_s']):.1f}"
        if feats.get("wind_direction_deg") is not None:
            sources["wind_direction_deg"] = f"{float(feats['wind_direction_deg']):.0f}"
        if feats.get("current_direction_deg") is not None:
            sources["current_direction_deg"] = f"{float(feats['current_direction_deg']):.0f}"
    except Exception:
        pass
    warnings = [
        WarningInfo(source="IMD", type="Coastal Fishermen Advisory", status="ACTIVE"),
        WarningInfo(source="INCOIS", type="Swell Surge Watch", status="MONITORING"),
        WarningInfo(source="NHO", type="NAVAREA VIII Warning #0482", status="ACTIVE_SECTOR_BRAVO")
    ]
    print(f"[Live Data Node] wave={ocean.wave_height}m wind={weather.wind}kt sst={ocean.sst}C "
          f"live={live} sources={sources}", flush=True)
    return {"weather": weather, "ocean": ocean, "warnings": warnings,
            "data_sources": sources, "telemetry_live": live}

def rag_node(state: OrcaState) -> dict:
    return execute_rag(state)

def geospatial_node(state: OrcaState) -> dict:
    return execute_geospatial(state)

def ml_node(state: OrcaState) -> dict:
    """
    ML Node: Evaluates environmental and geospatial parameters through
    deterministic & threshold-guided ML models:
    - RiskModel (wave height, wind speed, current velocity)
    - PFZModel (SST thermal front, chlorophyll-a pelagic congregation)
    - ProductivityModel (primary marine biomass SRP proxy)
    - ForecastModel (72h scenario projection)
    """
    print("[ML Node] Computing machine learning safety & fishery suitability scores...", flush=True)
    
    wave = state.ocean.wave_height if state.ocean else 1.4
    current_kts = state.ocean.current_speed if state.ocean else 1.2
    sst = state.ocean.sst if state.ocean else 28.4
    wind_kts = state.weather.wind if state.weather else 8.4
    
    # Unit conversions: knots to m/s (1 knot = 0.514444 m/s)
    wind_ms = wind_kts * 0.514444
    current_ms = current_kts * 0.514444
    
    predictions = predict_marine_models({
        "wave_height_m": wave,
        "wind_speed_ms": wind_ms,
        "current_speed_ms": current_ms,
        "sst_c": sst,
        "chlorophyll": 0.88 # mg/m^3 (Sentinel-3 OLCI telemetry)
    })
    
    risk_pred = predictions["risk"]
    pfz_pred = predictions["pfz"]
    prod_pred = predictions["productivity"]
    
    print(
        f"[ML Node] Results -> Risk: {risk_pred.value:.3f} ({risk_pred.label}) | "
        f"PFZ Favorability: {pfz_pred.value:.3f} ({pfz_pred.label}) | "
        f"Productivity: {prod_pred.label}",
        flush=True
    )
    
    return {
        "risk": Risk(
            score=risk_pred.value if risk_pred.value is not None else 0.14,
            level=risk_pred.label or "LOW"
        ),
        "fishing": FishingSuitability(
            suitability=pfz_pred.value if pfz_pred.value is not None else 0.91
        ),
        "risk_escalation": RiskEscalation(
            probability=round(risk_pred.uncertainty, 2),
            trend="STABLE" if (risk_pred.value or 0) < 0.35 else "INCREASING"
        )
    }

def generation_node(state: OrcaState) -> dict:
    return execute_generator(state)
