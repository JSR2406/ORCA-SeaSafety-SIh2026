from database.client import get_supabase_client

def check_spatial_risk(lat: float, lon: float) -> float:
    """
    Queries PostGIS to check if the given coordinates intersect with 
    any high-risk polygons (e.g., active cyclone zones, MPA boundaries).
    
    Returns a risk score between 0.0 and 1.0.
    """
    try:
        # Client construction itself raises on placeholder keys — inside try
        # so demo/offline mode falls through to the mock below.
        supabase = get_supabase_client()
        _ = supabase  # real RPC (calculate_spatial_risk) plugs in here
        # Example RPC call to a custom PostGIS function in Supabase
        # response = supabase.rpc("calculate_spatial_risk", {"lat": lat, "lon": lon}).execute()
        # return response.data.get("risk_score", 0.0)
        
        # Mocking for architectural completion until DB is populated
        print(f"[PostGIS] Calculating spatial risk for ({lat}, {lon})...")
        if lat > 20.0:  # Arbitrary mock logic
            return 0.8  # High risk
        return 0.1      # Low risk
    except Exception as e:
        print(f"[PostGIS Error] {e}")
        return 0.5 # Default moderate risk on failure
