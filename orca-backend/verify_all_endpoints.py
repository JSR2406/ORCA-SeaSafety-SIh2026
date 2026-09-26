import requests
import json

BASE = "http://localhost:8000/api/v1"

endpoints = [
    ("GET", f"{BASE}/health", None),
    ("GET", f"{BASE}/datasets/status", None),
    ("GET", f"{BASE}/ml/dashboard", None),
    ("GET", f"{BASE}/marine/ocean?lat=9.93&lon=76.27", None),
    ("GET", f"{BASE}/marine/weather-forecast?lat=9.93&lon=76.27", None),
    ("GET", f"{BASE}/marine/tides?lat=9.93&lon=76.27", None),
    ("GET", f"{BASE}/marine/pfz?lat=9.93&lon=76.27", None),
    ("GET", f"{BASE}/alerts", None),
    ("POST", f"{BASE}/risk/briefing", {"origin": {"lat": 9.93, "lon": 76.27}, "distance_km": 50}),
    ("POST", f"{BASE}/route/analyze", {"origin_lat": 9.93, "origin_lon": 76.27, "destination_lat": 10.15, "destination_lon": 75.85}),
    ("POST", f"{BASE}/scenarios/create", {"name": "Monsoon Swell Simulation"}),
    ("POST", f"{BASE}/chat", {"message": "Is it safe to fish tomorrow near Kochi?", "lat": 9.93, "lon": 76.27}),
]

print("=== STARTING FULL END-TO-END VERIFICATION ===")
all_passed = True
for method, url, body in endpoints:
    path = url.replace("http://localhost:8000", "")
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            r = requests.post(url, json=body, timeout=25)
        
        status = r.status_code
        ok = status == 200
        if not ok:
            all_passed = False
        print(f"[{'PASS' if ok else 'FAIL'}] {method} {path} -> HTTP {status}")
    except Exception as e:
        all_passed = False
        print(f"[ERROR] {method} {path} -> {e}")

print("=== VERIFICATION RESULT ===")
print("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED!")
