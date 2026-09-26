"""Prompt 2+3 tests: language detect, sessions, zones, geofence endpoints."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_detect_language_scripts():
    from core.sessions import detect_language
    assert detect_language("കടൽ") == "ml"
    assert detect_language("समुद्र") == "hi"
    assert detect_language("கடல்") == "ta"
    assert detect_language("sea state") == "en"
    assert detect_language("sea state", override="ml-IN") == "ml"


def test_sessions_roundtrip():
    from core.sessions import append_turn, get_history
    append_turn("t-sess", "user", "waves?")
    assert get_history("t-sess")[-1]["text"] == "waves?"
    assert get_history("nope") == []


def test_zones_bravo_and_clear():
    from ml.risk_engine.zones import check_point, check_route
    assert check_point(10.0, 76.12)["status"] == "VIOLATION"
    assert check_point(9.93, 76.27)["status"] == "CLEAR"
    assert len(check_route((9.9, 76.1), (10.1, 76.1))) > 0


def test_geofence_endpoints():
    from fastapi.testclient import TestClient
    from api.server import app
    c = TestClient(app)
    assert c.get("/api/v1/geofence/check?lat=10.0&lon=76.12").json()["status"] == "VIOLATION"
    j = c.post("/api/v1/route/analyze",
               json={"origin_lat": 9.9, "origin_lon": 76.3,
                     "destination_lat": 9.9, "destination_lon": 76.4}).json()
    assert j["risk_level"] == "LOW" and j["geofenceViolations"] == []
