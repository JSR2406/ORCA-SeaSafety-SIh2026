"""Prompt 1 tests: live telemetry schema, evidence contract, RAG fallback."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_live_data_node_schema_and_sources():
    from schemas.state import OrcaState
    from graph.nodes import live_data_node
    out = live_data_node(OrcaState(query="test", location={"lat": 9.93, "lon": 76.27}))
    assert hasattr(out["ocean"], "wave_height") and hasattr(out["weather"], "wind")
    assert isinstance(out["data_sources"], dict) and isinstance(out["telemetry_live"], bool)
    if out["telemetry_live"]:
        assert out["data_sources"].get("wave_height_m") == "OPEN_METEO"


def test_rag_keyword_fallback_relevant():
    from schemas.state import OrcaState
    from agents.rag import execute_rag
    out = execute_rag(OrcaState(query="cyclone storm warning", location={"lat": 9.9, "lon": 76.2}))
    titles = [d.title for d in out["rag"]]
    assert any("Cyclone" in t for t in titles)


def test_chat_evidence_contract():
    from fastapi.testclient import TestClient
    from api.server import app
    c = TestClient(app)
    r = c.post("/api/v1/chat", json={"message": "hello", "lat": 9.93, "lon": 76.27})
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("evidence"), list) and j.get("intent_type") in ("simple", "complex")
    for e in j["evidence"]:
        assert set(e) >= {"claim", "source", "verified"}
