"""SMS dispatch tests: demo mode without keys, validation, log, auto-trigger skip."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient


def _client():
    from api.server import app
    return TestClient(app)


def test_dispatch_demo_mode_no_keys():
    for k in ("FAST2SMS_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"):
        os.environ.pop(k, None)
    c = _client()
    r = c.post("/api/v1/alerts/dispatch-sms",
               json={"phone": "+910000000000", "message": "test", "severity": "INFO"})
    assert r.status_code == 200
    d = r.json()["dispatch"]
    assert d["status"] == "demo" and d["demo"] is True and d["sent"] is False


def test_dispatch_requires_phone_message():
    c = _client()
    assert c.post("/api/v1/alerts/dispatch-sms",
                  json={"phone": "", "message": "x"}).status_code == 400


def test_sms_log_records_dispatch():
    c = _client()
    c.post("/api/v1/alerts/dispatch-sms",
           json={"phone": "+911111111111", "message": "log-check", "severity": "LOW"})
    log = c.get("/api/v1/alerts/sms-log").json()
    assert log["status"] == "success" and log["total"] >= 1
    assert any("log-check" in e.get("message", "") for e in log["data"])


def test_auto_trigger_skipped_without_emergency_number():
    os.environ.pop("EMERGENCY_SMS_NUMBER", None)
    c = _client()
    r = c.post("/api/v1/alerts/dispatch-sms",
               json={"phone": "+910000000000", "message": "high alert",
                     "severity": "HIGH", "wave_height_m": 3.0, "wave_threshold_m": 2.0})
    assert r.json()["auto_trigger"]["status"] == "skipped"
