"""Verify alert-write endpoints require an authority token (SEC-001)."""
import os
import sys

sys.path.insert(0, "/app/orca-backend/apps/api")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings

settings.auth_jwt_secret = "test-secret-for-verification-only"
settings.auth_operator_email = "harbour.authority@orca.gov.in"
settings.auth_operator_password = "OrcaHarbour#2026"

from app.routers import alerts, auth  # noqa: E402

app = FastAPI()
app.include_router(auth.router)
app.include_router(alerts.router)
client = TestClient(app)

payload = {"title": "FAKE cyclone warning", "desc": "injected", "level": "HIGH"}

r = client.post("/api/v1/alerts", json=payload)
print("anonymous create ->", r.status_code)
assert r.status_code in (401, 403), r.text

r = client.post("/api/v1/alerts/ALT-1/acknowledge")
print("anonymous acknowledge ->", r.status_code)
assert r.status_code in (401, 403), r.text

r = client.post("/api/v1/alerts", json=payload, headers={"Authorization": "Bearer not-a-real-token"})
print("forged token create ->", r.status_code)
assert r.status_code == 401, r.text

r = client.post("/api/v1/auth/login", json={"email": "attacker@example.com", "password": "guess"})
print("wrong credentials login ->", r.status_code)
assert r.status_code == 401, r.text

r = client.post("/api/v1/auth/login", json={
    "email": settings.auth_operator_email,
    "password": settings.auth_operator_password,
})
print("operator login ->", r.status_code)
assert r.status_code == 200, r.text
token = r.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}
r = client.post("/api/v1/alerts", json=payload, headers=headers)
print("authorized create ->", r.status_code, r.json()["alert"]["published_by"])
assert r.status_code == 200, r.text

r = client.post("/api/v1/alerts", json={"title": "x" * 500}, headers=headers)
print("oversized title ->", r.status_code)
assert r.status_code == 422, r.text

r = client.post("/api/v1/alerts", json={"title": "bad coords", "lat": 999}, headers=headers)
print("out of range lat ->", r.status_code)
assert r.status_code == 422, r.text

r = client.get("/api/v1/alerts")
print("public list ->", r.status_code, r.json()["total"])
assert r.status_code == 200, r.text

settings.auth_jwt_secret = ""
r = client.post("/api/v1/alerts", json=payload, headers=headers)
print("unconfigured secret create ->", r.status_code)
assert r.status_code == 503, r.text

print("\nALL SECURITY CHECKS PASSED")
