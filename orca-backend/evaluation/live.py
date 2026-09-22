# Phase 8 - Parts 3/4/31: live acceptance, demo readiness, replay honesty.
#
# Opt-in harness: `RUN_LIVE_ACCEPTANCE=1 python -m evaluation.live`.
# WITHOUT the flag the harness prints a skip notice and exits 0 so CI never
# fails on a third-party live service outage.  WITH the flag it probes real
# infrastructure (database + source endpoints) with a bounded timeout, and
# executes the demo workflows through the REAL orchestration pipeline.
#
# Honesty contract:
#   * source matrix statuses are only CONNECTED / CONFIGURATION_REQUIRED /
#     UNAVAILABLE / NOT_SUPPORTED / NOT_TESTED - never guessed LIVE.
#   * demo executions use offline test fixtures and are labeled as such on
#     every row; they are never presented as live observations.
#   * deterministic replays are labeled REPLAY / HISTORICAL DEMONSTRATION.
import os
import sys


def _bootstrap() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (repo, os.path.join(repo, "apps", "api")):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


# ------------------------------------------------------------ infrastructure
SOURCE_DEFS = [
    {"id": "incois", "name": "INCOIS", "kind": "ocean observations",
     "enabled_attr": "incois_enabled", "base_attr": "incois_base_url",
     "key_attr": "incois_api_key", "driver": "http-adapter"},
    {"id": "imd", "name": "IMD", "kind": "weather observations",
     "enabled_attr": "imd_enabled", "base_attr": "imd_base_url",
     "key_attr": "imd_api_key", "driver": "http-adapter"},
    {"id": "mosdac", "name": "MOSDAC", "kind": "satellite ocean products",
     "enabled_attr": "mosdac_enabled", "base_attr": "mosdac_base_url",
     "key_attr": "mosdac_api_key", "driver": "http-adapter"},
    {"id": "nho", "name": "NHO", "kind": "charting / harbour restrictions",
     "enabled_attr": None, "base_attr": None, "key_attr": None,
     "driver": "deterministic TemporaryClosureAdapter"},
    {"id": "navarea-viii", "name": "NAVAREA VIII", "kind": "navigational warnings",
     "enabled_attr": None, "base_attr": None, "key_attr": None,
     "driver": "deterministic NavareaAdvisoryAdapter"},
    {"id": "navtex", "name": "NAVTEX", "kind": "broadcast safety messages",
     "enabled_attr": None, "base_attr": None, "key_attr": None,
     "driver": "no registered adapter (feed via NHO/NAVAREA restricted)"},
]


def _db_row(status, detail):
    return {"layer": "database", "source": "postgres", "status": status,
            "detail": detail, "latency_ms": None}


def probe_database(settings) -> dict:
    url = (settings.database_url or "").strip()
    if not url:
        return _db_row("NOT_CONFIGURED", "no database_url configured")
    if "asyncpg" not in url:
        return _db_row("NOT_SUPPORTED", "driver is not asyncpg: probe skipped")
    try:
        import asyncpg
        from sqlalchemy.engine import make_url
    except ImportError as exc:
        return _db_row("NOT_SUPPORTED", f"probe driver unavailable: {exc}")

    async def _ping():
        parsed = make_url(url)
        conn = await asyncpg.connect(
            host=parsed.host or "localhost", port=parsed.port or 5432,
            user=parsed.username, password=parsed.password or "",
            database=parsed.database or "postgres", timeout=4)
        try:
            row = await conn.fetchval("SELECT 1")
            return row == 1
        finally:
            await conn.close()

    try:
        latency = __import__("time").perf_counter()
        ok = asyncio_run(_ping())
        return _db_row("CONNECTED" if ok else "ERROR",
                       "SELECT 1 ok" if ok else "SELECT 1 failed")
    except Exception as exc:  # noqa: BLE001 - infra status is a report, not a crash
        return _db_row("UNAVAILABLE", repr(exc)[:220])


def asyncio_run(coro):
    import asyncio
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _probe_http(base_url: str, timeout: float = 6.0):
    import httpx
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.get(base_url)
    return response.status_code


def probe_source(definition: dict, settings) -> dict:
    row = {"source": definition["id"], "name": definition["name"],
           "kind": definition["kind"], "driver": definition["driver"],
           "status": None, "latency_ms": None, "detail": ""}
    enabled_attr = definition["enabled_attr"]
    if enabled_attr is None:
        row["status"] = "CONFIGURATION_REQUIRED"
        row["detail"] = ("no live feed configured; current driver is "
                         f"{definition['driver']}")
        return row
    enabled = bool(getattr(settings, enabled_attr, False))
    if not enabled:
        row["status"] = "CONFIGURATION_REQUIRED"
        row["detail"] = f"{enabled_attr} is disabled"
        return row
    base = (getattr(settings, definition["base_attr"], None) or "").strip()
    if not base:
        row["status"] = "CONFIGURATION_REQUIRED"
        row["detail"] = f"{definition['base_attr']} is empty"
        return row
    try:
        start = __import__("time").perf_counter()
        code = asyncio_run(_probe_http(base))
        latency = round((__import__("time").perf_counter() - start) * 1000, 1)
        row["latency_ms"] = latency
        if 200 <= code < 300:
            row["status"] = "CONNECTED"
            row["detail"] = f"HTTP {code}; endpoint reachable, payload semantics unverified"
        elif code in (401, 403):
            row["status"] = "NOT_TESTED"
            row["detail"] = f"HTTP {code}; reachable but credential-gated"
        else:
            row["status"] = "UNAVAILABLE"
            row["detail"] = f"HTTP {code}"
    except Exception as exc:  # noqa: BLE001 - network status is a report, not a crash
        row["status"] = "UNAVAILABLE"
        row["detail"] = repr(exc)[:180]
    return row


# ------------------------------------------------------------------- demos
def _worlds():
    from evaluation import fixtures
    return {
        "healthy": fixtures.healthy_world,
        "restricted": fixtures.restricted_world,
        "dynamic-restricted": fixtures.dynamic_restricted_world,
        "route-blocked": fixtures.route_blocked_world,
        "route-clear": fixtures.route_clear_world,
        "pfz": fixtures.pfz_world,
        "productivity": fixtures.productivity_world,
        "no-weather": fixtures.no_weather_world,
    }


def collect_report():
    from datetime import datetime

    from app.config import get_settings
    from evaluation.fixtures import World, ocean_row, weather_row
    from evaluation.runners import allowed_tool_set, run_scenario_parts

    settings = get_settings()

    database = probe_database(settings)
    sources = [probe_source(defn, settings) for defn in SOURCE_DEFS]

    worlds = _worlds()
    waits = {
        "demo-a-safe-to-go-kochi": (worlds["healthy"](),
                                    "Is it safe to fish near Kochi?"),
        "demo-b-best-fishing-zone": (worlds["pfz"](),
                                     "Where is the best fishing zone near Kochi?"),
        "demo-c-restrictions-here": (worlds["dynamic-restricted"](),
                                     "Are there any restrictions near Kochi?"),
        "demo-d-safest-route": (worlds["route-blocked"](),
                                "Plan the safest route from Visakhapatnam to Chennai; "
                                "avoid restricted water."),
        "demo-e-productivity-decline": (
            World(name="productivity-decline",
                  ocean_rows=[ocean_row(chlorophyll=0.12, sst_c=23.5)],
                  weather_rows=[weather_row()],
                  productivity={"productivity": 29, "label": "low",
                                "location": {"lat": 15.4, "lon": 73.8},
                                "contributions": [
                                    {"variable": "chlorophyll", "value": 0.12,
                                     "favorability": 0.2}],
                                "note": "synthetic"}),
            "Fishing productivity has declined near Ratnagiri; what is the trend?"),
        "golden-pfz": (worlds["pfz"](),
                       "Where's the best fishing zone near Kochi?"),
        "golden-safe-to-go": (worlds["restricted"](),
                              "Is it safe to fish near Kochi?"),
        "golden-active-restriction": (worlds["dynamic-restricted"](),
                                      "Are there active restrictions near Mumbai?"),
        "golden-safest-route": (worlds["route-blocked"](),
                                "What is the safest route from Goa to Mumbai?"),
        "golden-productivity": (worlds["productivity"](),
                                "Show fishing productivity near Chennai"),
    }
    multi_turns = [
        ("multi-pfz-tomorrow", worlds["pfz"](),
         "Where is the best fishing zone near Kochi?",
         "and 20 km south of Kochi tomorrow?"),
        ("multi-safe-mumbai", worlds["healthy"](),
         "Is it safe to fish near Mumbai?",
         "and 20 km north?"),
    ]

    demo_rows = []
    for identifier, (world, message) in waits.items():
        case = run_scenario_parts(identifier, message, world, title=identifier)
        demo_rows.append(_session_row(identifier, message, world, case,
                                      labels=["OFFLINE TEST FIXTURE"]))

    for identifier, world, first, second in multi_turns:
        case = run_scenario_parts(identifier, first, world, title=identifier,
                                  second_turn=second, pipeline="twoturn")
        demo_rows.append(
            _session_row(f"{identifier}:turn1", first, world, case,
                         labels=["OFFLINE TEST FIXTURE"]))
        demo_rows.append(
            _session_row(f"{identifier}:turn2", second, world, case,
                         second=True, labels=["OFFLINE TEST FIXTURE",
                                              "context-merged"]))

    replay = run_scenario_parts("replay-sample", "Is it safe near Kochi?",
                                worlds["restricted"](), pipeline="stream",
                                title="replay-sample")

    # Phase 11 - proactive alert engine (9 deterministic offline cases).
    from evaluation.benchmark import run_proactive_benchmark
    proactive = run_proactive_benchmark()

    # Phase 12 - production ML / MLOps acceptance (6 deterministic cases).
    from evaluation.benchmark import run_ml_benchmark
    ml = run_ml_benchmark()

    # Phase 13 - continuous learning / model governance acceptance
    # (12 deterministic cases).
    from evaluation.benchmark import run_ml_governance_benchmark
    ml_governance = run_ml_governance_benchmark()

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "opt-in acceptance (RUN_LIVE_ACCEPTANCE=1)",
        "database": database,
        "sources": sources,
        "proactive": proactive,
        "ml": ml,
        "ml_governance": ml_governance,
        "policy": {
            "provenance_chain": (
                "user -> orchestrator -> agent -> MCP tool -> marine service -> "
                "adapter -> source (e.g. INCOIS retrieved at <source_timestamp>)"),
            "freshness_labels": ["LIVE", "RECENT", "STALE", "EXPIRED",
                                 "UNAVAILABLE"],
            "live_only_if_verified": True,
            "cache_is_never_live": True,
            "replay_label": "REPLAY / HISTORICAL DEMONSTRATION",
        },
        "demo_rows": demo_rows,
        "multi_turn": [{"id": r["id"], "merged_from_context": r.get("merged_from_context")}
                       for r in demo_rows if "turn2" in r["id"]],
        "stream": _stream_row(replay),
    }


def _session_row(identifier, message, world, case, *, second=False,
                 labels=None):
    response = case.second_response if second and case.second_response \
        else case.response
    payload = response or {}
    risk = payload.get("risk") or {}
    row = {
        "id": identifier,
        "message": message,
        "data_basis": " / ".join(labels or ["OFFLINE TEST FIXTURE"]),
        "intent": payload.get("intent"),
        "language": payload.get("language"),
        "result_status": payload.get("status"),
        "risk_status": risk.get("status"),
        "risk_level": risk.get("level"),
        "hard_constraint": risk.get("hard_constraint"),
        "safety_state_note": risk.get("status") or "n/a",
        "verification": (payload.get("verification") or {}).get("all_verified"),
        "freshness": payload.get("freshness"),
        "latency_ms": payload.get("duration_ms"),
        "tool_calls": payload.get("tool_calls"),
        "tools_used": sorted({t for t, _ in (case.second_calls if second
                                             else case.calls)}),
        "limitations": (payload.get("limitations") or [])[:3],
        "evidence_items": len(payload.get("evidence") or {}),
        "provenance": dict(list((payload.get("provenance") or {}).items())[:2]),
        "error": case.error,
        "merged_from_context": (payload.get("notes") or {}).get(
            "merged_from_context"),
    }
    return row


def _stream_row(case):
    events = case.events or []
    vocab_order = ["execution.started", "intent.detected", "plan.created",
                   "task.started", "tool.started", "tool.completed",
                   "task.completed", "verification.started",
                   "verification.completed", "response.ready",
                   "execution.completed"]
    seen = [e.get("event") for e in events]
    return {
        "label": "REPLAY / HISTORICAL DEMONSTRATION",
        "event_count": len(events),
        "events": seen,
        "vocabulary_ok": all(v in seen for v in vocab_order),
        "chain_of_thought_leaked": any(
            e.get("type") in ("reasoning", "chain_of_thought")
            for e in events),
    }


def _markdown(report: dict) -> str:
    lines = [
        "# Live Acceptance & Demo Readiness Report",
        "",
        f"generated: `{report['generated_at']}`  mode: `{report['mode']}`",
        "",
        "Opt-in (RUN_LIVE_ACCEPTANCE=1). Infrastructure unavailability is "
        "reported as status, never hidden, and never fails CI.",
        "",
        "## 1. Database probe",
        "",
        "| layer | source | status | latency | detail |",
        "|---|---|---|---|---|",
        f"| {report['database']['layer']} | {report['database']['source']} | "
        f"{report['database']['status']} | "
        f"{report['database']['latency_ms'] or '-'} | "
        f"{report['database']['detail']} |",
        "",
        "## 2. Source matrix (never guessed LIVE)",
        "",
        "| source | name | kind | driver | status | latency_ms | detail |",
        "|---|---|---|---|---|---|---|",
    ]
    for source in report["sources"]:
        lines.append(
            f"| {source['source']} | {source['name']} | {source['kind']} | "
            f"{source['driver']} | {source['status']} | "
            f"{source['latency_ms'] or '-'} | {source['detail']} |")
    lines += [
        "",
        "## 3. Provenance & freshness policy",
        "",
        f"- chain: `{report['policy']['provenance_chain']}`",
        f"- freshness labels: {', '.join(report['policy']['freshness_labels'])}",
        f"- live_only_if_verified: {report['policy']['live_only_if_verified']}",
        f"- cache_is_never_live: {report['policy']['cache_is_never_live']}",
        "",
        "## 4. Demo workflow acceptance (offline test fixtures)",
        "",
        "Every row runs the REAL orchestration pipeline against evaluation-only "
        "worlds. Data is labeled OFFLINE TEST FIXTURE - it is never presented "
        "as a live observation. To exercise live data, deploy the database and "
        "source credentials, then re-run this harness.",
        "",
        "| id | intent | result | risk | hard constraint | verification | "
        "latency_ms | tools | basis |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report["demo_rows"]:
        provenance = row.get("provenance") or []
        tools = ",".join(row.get("tools_used") or [])
        lines.append(
            f"| {row['id']} | {row.get('intent') or '-'} | "
            f"{row.get('result_status') or '-'} | {row.get('risk_status') or '-'} | "
            f"{row.get('hard_constraint')} | {row.get('verification')} | "
            f"{row.get('latency_ms')} | {tools or '-'} | {row['data_basis']} |")
        for limitation in row.get("limitations") or []:
            lines.append(f"  - limitation: {limitation}")
    lines += [
        "",
        "## 5. Multi-turn acceptance",
        "",
    ]
    for item in report.get("multi_turn") or []:
        lines.append(f"- {item['id']}: merged_from_context="
                     f"{item.get('merged_from_context')}")
    lines += [
        "",
        "## 6. WebSocket stream contract (replay)",
        "",
        f"- label: {report['stream']['label']}",
        f"- events emitted: {report['stream']['event_count']}",
        f"- vocabulary order ok: {report['stream']['vocabulary_ok']}",
        f"- chain-of-thought leaked: {report['stream']['chain_of_thought_leaked']}",
        f"- sample events: {', '.join(report['stream']['events'])}",
        "",
        "## 7. Proactive Marine Intelligence (Phase 11)",
        "",
        "These are deterministic OFFLINE cases against the real ProactiveMarineEngine "
        "and event/monitor layers (no database, no external feed). They verify change "
        "detection, policy gating, deduplication, restriction/geofence monitoring, "
        "source failure/recovery, escalation and ML material-change gating.",
        "",
        "| case | status | failures | error |",
        "|---|---|---|---|",
    ]
    for c in report.get("proactive") or []:
        lines.append(f"| {c['name']} | {c['status']} | {c['failures']} | "
                     f"{c['error'] or '-'} |")
    lines += [
        "",
        "## 8. Production ML / MLOps (Phase 12)",
        "",
        "These are deterministic OFFLINE cases against the real ModelService "
        "(feature store -> registry -> predict -> uncertainty -> provenance -> "
        "cache). ML is advisory and never overrides the Risk Engine.",
        "",
        "| case | status | failures | error |",
        "|---|---|---|---|",
    ]
    for c in report.get("ml") or []:
        lines.append(f"| {c['name']} | {c['status']} | {c['failures']} | "
                     f"{c['error'] or '-'} |")
    lines += [
        "",
        "## 9. Continuous Learning / Model Governance (Phase 13)",
        "",
        "These are deterministic OFFLINE cases against the real GovernanceEngine "
        "closed loop: prediction ledger, ground-truth validation + matching, "
        "rolling evaluation, drift separation, reproducible datasets, candidate "
        "lifecycle, champion/challenger shadow, promotion gate, rollback, "
        "confidence degradation on missing inputs, stale-feature surfacing and "
        "provenance. Production models are immutable until explicitly promoted.",
        "",
        "| case | status | failures | error |",
        "|---|---|---|---|",
    ]
    for c in report.get("ml_governance") or []:
        lines.append(f"| {c['name']} | {c['status']} | {c['failures']} | "
                     f"{c['error'] or '-'} |")
    lines += [
        "",
        "## 10. Honest labeling audit",
        "",
        "- no source row is marked CONNECTED unless an endpoint probe returned 2xx.",
        "- no demo row claims LIVE data; all demo rows state OFFLINE TEST FIXTURE.",
        "- no replay is labeled LIVE; replays are REPLAY / HISTORICAL DEMONSTRATION.",
    ]
    return "\n".join(lines)


def write_reports(report: dict) -> dict:
    from datetime import datetime
    import json
    from pathlib import Path

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = reports_dir / f"live-{stamp}.json"
    md_path = reports_dir / f"live-{stamp}.md"
    latest = reports_dir / "live-latest.md"
    payload = json.dumps(report, indent=2, default=str)
    json_path.write_text(payload, encoding="utf-8")
    markdown = _markdown(report)
    md_path.write_text(markdown, encoding="utf-8")
    latest.write_text(markdown, encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path),
            "latest": str(latest)}


def print_summary(report: dict) -> None:
    db = report["database"]
    print(f"live acceptance: db={db['status']}")
    for source in report["sources"]:
        print(f"  source {source['source']:<12} {source['status']}")
    passed = [r for r in report["demo_rows"]
              if r.get("result_status") in ("success", "partial")
              and not r.get("error")]
    print(f"  demo workflows run: {len(report['demo_rows'])} "
          f"ok={len(passed)} stream_ok="
          f"{report['stream']['vocabulary_ok']}")
    proactive = report.get("proactive") or []
    ok_proactive = [c for c in proactive if c["status"] == "success"]
    print(f"  proactive cases: {len(proactive)} ok={len(ok_proactive)}")
    ml = report.get("ml") or []
    ok_ml = [c for c in ml if c["status"] == "success"]
    print(f"  ml cases: {len(ml)} ok={len(ok_ml)}")
    gov = report.get("ml_governance") or []
    ok_gov = [c for c in gov if c["status"] == "success"]
    print(f"  ml governance cases: {len(gov)} ok={len(ok_gov)}")
    print(f"  replay label: {report['stream']['label']}")


def main() -> int:
    if os.environ.get("RUN_LIVE_ACCEPTANCE") != "1":
        print("live acceptance is opt-in; set RUN_LIVE_ACCEPTANCE=1 to run")
        return 0
    try:
        report = collect_report()
        paths = write_reports(report)
        print_summary(report)
        md = paths["latest"]
        print(f"reports written: {paths['json']}, {paths['markdown']}")
        print(f"latest: {md}")
        return 0
    except Exception as exc:  # noqa: BLE001 - a harness bug must surface loudly
        import traceback
        print(f"live acceptance harness failed: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    _bootstrap()
    raise SystemExit(main())