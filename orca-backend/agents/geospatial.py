from schemas.state import OrcaState, RouteInfo
from database.postgis import check_spatial_risk

def execute_geospatial(state: OrcaState) -> dict:
    """
    Geospatial Agent: PostGIS mock + real demo-zone evaluation.
    Zone VIOLATION forces high route risk; CAUTION raises it moderately.
    """
    print("[Geospatial Agent] Starting spatial analysis...")

    risk_score = 0.0

    if state.location:
        # Legacy PostGIS mock (kept until polygons land in PostGIS)
        risk_score = check_spatial_risk(state.location.lat, state.location.lon)
        try:
            from ml.risk_engine.zones import check_point
            res = check_point(state.location.lat, state.location.lon)
            if res["status"] == "VIOLATION":
                risk_score = max(risk_score, 0.9)
            elif res["status"] == "CAUTION":
                risk_score = max(risk_score, 0.5)
            print(f"[Geospatial Agent] zones={res['status']} hits={len(res['hits'])}")
        except Exception as e:
            print(f"[Geospatial Agent] zone check failed: {e}")
        print(f"[Geospatial Agent] Computed Route/Spatial Risk: {risk_score}")
    else:
        print("[Geospatial Agent] No location provided, skipping spatial check.")
        
    # Update the LangGraph state with the calculated route risk
    return {"route": RouteInfo(risk=risk_score)}
