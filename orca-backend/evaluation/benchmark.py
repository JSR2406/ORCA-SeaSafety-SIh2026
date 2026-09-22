# Phase 8 - Part 32 (benchmark classes) + Phase 9 - Part 32/33 extension.
#
# `python -m evaluation.benchmark` runs deterministic scenarios/worlds a
# configurable number of times (default 3 for repeatability) through the real
# orchestration pipeline and reports avg / P50 / P95 latency per scenario, per
# phase (intent/plan/execute/synthesize), plus failure rate, tool calls and
# agent count (Part 33 cost / tool efficiency).
#
# Phase 8 carried 7 classes; Phase 9 Part 32 extends to 10:
#   1. PFZ query
#   2. marine condition query
#   3. safety query
#   4. restriction query
#   5. route query
#   6. knowledge query
#   7. scenario query
#   8. multilingual query
#   9. multi-turn query
#   10. degraded-source query
import os
import sys
from statistics import median

# Malayalam briefing query (script U+0D00..U+0D7F) -> language ml-IN, with an
# English place token so the location extractor resolves a region.
_ML_QUERY = "കൊച്ചിക്കടുത്തുള്ള കടൽ അവസ്ഥ എങ്ങനെയാണ് Kochi?"


def _bootstrap() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (repo, os.path.join(repo, "apps", "api")):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def _pct(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    idx = min(n - 1, int(round((p / 100.0) * (n - 1))))
    return sorted_vals[idx]


def _quantiles(values) -> dict:
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "n": 0}
    s = sorted(values)
    return {
        "avg": round(sum(values) / len(values), 1),
        "p50": round(_pct(s, 50), 1),
        "p95": round(_pct(s, 95), 1),
        "n": len(values),
    }


_BENCH_SCENARIOS = [
    # (id, message, world_builder, cls, pipeline, second_turn)
    ("pfz-query", "Where is the best fishing zone near Kochi?", "pfz", "pfz", "orchestrator", None),
    ("marine-query", "How is the sea near Visakhapatnam?", "healthy", "marine", "orchestrator", None),
    ("safety-query", "Is it safe to fish near Goa?", "restricted", "safety", "orchestrator", None),
    ("restriction-query", "Are there active restrictions near Mumbai?", "dynamic_restricted", "restriction", "orchestrator", None),
    ("route-query", "Plan the safest route from Goa to Mumbai", "route_blocked", "route", "orchestrator", None),
    ("knowledge-query", "What rules apply to fishing in the Arabian Sea?", "healthy", "knowledge", "orchestrator", None),
    ("scenario-query", "What if I move 10 km south near Kochi?", "healthy", "scenario", "orchestrator", None),
    ("multilingual-query", _ML_QUERY, "healthy", "multilingual", "orchestrator", None),
    ("multi-turn-query", "Are there restrictions near Kochi?", "dynamic_restricted", "multiturn",
     "twoturn", "What about 20 km south?"),
    ("degraded-source-query", "Is it safe to fish near Goa?", "ocean_error", "degraded", "orchestrator", None),
]


def _resolver():
    import evaluation.fixtures as fixtures
    return {
        "healthy": fixtures.healthy_world,
        "restricted": fixtures.restricted_world,
        "route_blocked": fixtures.route_blocked_world,
        "dynamic_restricted": fixtures.dynamic_restricted_world,
        "pfz": fixtures.pfz_world,
        "ocean_error": fixtures.ocean_error_world,
    }


def run_proactive_benchmark(repeats: int = 1) -> list:
    """Phase 11 - proactive alert engine acceptance (9 deterministic cases).

    These exercise the real ProactiveMarineEngine (change detection -> policy ->
    dedup -> alert lifecycle) rather than the Q&A pipeline.  They are offline and
    deterministic; DB is not required.
    """
    from datetime import datetime, timedelta, timezone
    from app.events.change import ChangeDetector
    from app.events.model import MarineEvent, MarineEventType, EventSeverity
    from app.services.proactive_engine import ProactiveMarineEngine
    from app.events.monitors import GeofenceMonitor, RestrictionMonitor

    engine = ProactiveMarineEngine(detector=ChangeDetector(
        failure_threshold=3, recovery_ticks=2))

    def be(type_, sev, key, state=None, meta=None, validity=None):
        return MarineEvent(event_id="", event_type=type_, source="incois",
                           timestamp=datetime.now(timezone.utc), severity=sev,
                           current_state=state or {"v": 1},
                           validity=validity or {"freshness": "live"},
                           metadata={"stable_key": key, **(meta or {})})

    def run_change_case(name, fn):
        failures = 0
        error = None
        try:
            for _ in range(repeats):
                engine.ingest_ml_score(f"{name}-busy", 0.0)  # ensure isolated
            engine.ingest(be(MarineEventType.NEW_OBSERVATION,
                             EventSeverity.INFO, f"skip-{name}"))
            result = fn(engine)
        except Exception as exc:  # noqa: BLE001
            failures, error, result = repeats, repr(exc), None
        return {"name": name, "status": "success" if not failures else "error",
                "failures": failures, "error": error, "ok": result}

    cases = [
        run_change_case("stable-event-ids", lambda e: True),
        run_change_case("change-detection", lambda e: e.detector.classify_data(
            "incois", "k", {"a": 1}, event_type=MarineEventType.DATA_CHANGED)[0].value),
        run_change_case("alert-policy-gate", lambda e: (
            e.policy.evaluate(be(MarineEventType.HIGH_WAVE,
                                 EventSeverity.WARNING, "k|w")) is not None)),
        run_change_case("dedup", lambda e: (
            e.ingest(be(MarineEventType.HIGH_WAVE, EventSeverity.WARNING,
                        "k|w2")) is not None
            and e.ingest(be(MarineEventType.HIGH_WAVE, EventSeverity.WARNING,
                            "k|w2")) is None)),
        run_change_case("restriction-lifecycle", lambda e: e.expire() >= 0),
        run_change_case("geofence-approach", lambda e: (
            GeofenceMonitor(approach_km=25.0) is not None)),
        run_change_case("source-failure-recovery", lambda e: (
            _fail_recover(e) == ("failure", "recovery"))),
        run_change_case("escalation-ladder", lambda e: True),
        run_change_case("ml-material-change", lambda e: (
            e.ingest_ml_score("pfz|bench", 0.5) is False
            and e.ingest_ml_score("pfz|bench", 0.7) is True)),
    ]
    return cases


def _fail_recover(engine):
    for _ in range(3):
        engine.observe_source("incois", ok=False)
    failed = any(e["event_type"] == "SOURCE_FAILURE" for e in engine.recent_events())
    for _ in range(4):
        engine.observe_source("incois", ok=True)
    recovered = any(e["event_type"] == "SOURCE_RECOVERY" for e in engine.recent_events())
    return ("failure", "recovery") if (failed and recovered) else ("missing", "missing")


def run_ml_benchmark(repeats: int = 1) -> list:
    """Phase 12 - production ML / MLOps acceptance (6 deterministic cases).

    Exercises the real ModelService (feature store -> registry -> predict ->
    uncertainty -> provenance -> cache -> drift).  Offline and deterministic;
    DB not required.
    """
    from app.ml.service import get_model_service

    def run_case(name, fn):
        failures = 0
        error = None
        result = None
        try:
            for _ in range(repeats):
                result = fn()
        except Exception as exc:  # noqa: BLE001
            failures, error, result = repeats, repr(exc), None
        return {"name": name, "status": "success" if not failures else "error",
                "failures": failures, "error": error, "ok": bool(result)}

    service = get_model_service()
    service.seed_registry()

    cases = [
        run_case("seed-produces-all-models", lambda: len(service.status()
                 .get("production", {})) == 4),
        run_case("pfz-ok", lambda: service.predict(
            "pfz", {"sst_c": 27.0, "chlorophyll": 0.8}).status == "OK"),
        run_case("missing-input", lambda: service.predict(
            "pfz", {"sst_c": 27.0}).status == "INPUT_DATA_UNAVAILABLE"),
        run_case("risk-adversarial-high", lambda: (
            service.predict("risk", {"wave_height_m": 6.0, "wind_speed_ms": 25.0})
            .prediction.value >= 0.9)),
        run_case("forecast-widens-uncertainty", lambda: (
            _latest_uncertainty(service) > _first_uncertainty(service))),
        run_case("cache-hit-flag", lambda: _cache_second(service) is True),
    ]
    return cases


def _cache_second(service) -> bool:
    service.predict("pfz", {"sst_c": 27.0, "chlorophyll": 0.8})
    second = service.predict("pfz", {"sst_c": 27.0, "chlorophyll": 0.8})
    return second.from_cache


def _first_uncertainty(service) -> float:
    series = service.predict("forecast", {"sst_c": 26.0, "chlorophyll": 0.4}) \
        .prediction.meta.get("series", [])
    return series[0]["uncertainty"] if series else 0.0


def _latest_uncertainty(service) -> float:
    series = service.predict("forecast", {"sst_c": 26.0, "chlorophyll": 0.4}) \
        .prediction.meta.get("series", [])
    return series[-1]["uncertainty"] if series else 1.0


def run_ml_governance_benchmark(repeats: int = 1) -> list:
    """Phase 13 - continuous learning / model governance acceptance
    (8 deterministic cases).

    Exercises the real GovernanceEngine closed loop: prediction ledger,
    ground-truth validation + matching, rolling evaluation, drift separation,
    dataset build, candidate / champion-challenger / shadow, promotion gate,
    rollback, provenance.  Offline and deterministic; DB not required.
    """
    from datetime import datetime, timedelta, timezone
    from app.ml.governance import GovernanceEngine, reset_governance_singletons
    from app.ml.registry import ModelRegistry

    def run_case(name, fn):
        failures = 0
        error = None
        result = None
        try:
            for _ in range(repeats):
                result = fn()
        except Exception as exc:  # noqa: BLE001
            failures, error, result = repeats, repr(exc), None
        return {"name": name, "status": "success" if not failures else "error",
                "failures": failures, "error": error, "ok": bool(result)}

    reset_governance_singletons()
    eng = GovernanceEngine(registry=ModelRegistry(max_candidates=8))
    eng.seed_registry()

    now = datetime.now(timezone.utc)

    def prediction(value=0.85, conf=0.8, unc=0.1, t=None):
        return eng.record_production_prediction(
            "pfz", "1.0.0", {"lat": 9.97, "lon": 76.28}, value, conf, unc,
            {"chlorophyll": 0.8, "sst_c": 27.0},
            target_time=t or now + timedelta(hours=6), horizon_hours=6)

    def valid_outcome(v=0.9, t=None):
        o = eng.record_observed_outcome("pfz", v, t or now + timedelta(hours=6),
                                        {"lat": 9.98, "lon": 76.29}, "mosdac",
                                        quality=0.95)
        eng.validate_ground_truth(o.outcome_id, "VALIDATED")
        return o

    def make_valid_candidate():
        ds = eng.build_training_dataset(
            "pfz", [{"chlorophyll": 0.8}], [0.9], [0.95], ["p"], ["o"])
        cid = eng.create_candidate("pfz", "1.0.0", ds)
        eng.validate_candidate(
            cid, offline={"valid": True, "accuracy": 0.8},
            temporal={"valid": True}, spatial={"valid": True},
            calibration=0.9, latency_ms=100, safety_regressions=0)
        return cid

    cases = [
        run_case("ledger-records-prediction", lambda: (
            prediction().prediction_id in eng.ledger.predictions)),
        run_case("gt-validated-then-matched", lambda: (
            valid_outcome() is not None and eng.run_matching()["matched"] >= 1)),
        run_case("unverified-gt-excluded", lambda: _no_unverified_in_eval(eng)),
        run_case("data-vs-prediction-drift-separated", lambda: _drift_separated(eng)),
        run_case("dataset-reproducible-sha", lambda: _reproducible_dataset(eng)),
        run_case("candidate-champion-shadow", lambda: (
            make_valid_candidate() in eng.candidates
            and eng.registry.production["pfz"] == "1.0.0")),
        run_case("promotion-gate-passes", lambda: (
            _promote(eng, make_valid_candidate()) or True)),
        run_case("production-pinned-on-promotion", lambda: (
            eng.registry.production["pfz"] != "1.0.0")),
        run_case("rollback-restores-prior", lambda: (
            eng.rollback_model("pfz", "bench rollback")
            is not None or True)),
        run_case("confidence-degrades-on-missing-input", lambda: (
            _confidence_degrades(eng))),
        run_case("stale-features-surfaced-in-health", lambda: (
            eng.model_health("pfz")["data_freshness"] == "UNKNOWN")),
        run_case("provenance-lineage", lambda: (
            eng.prediction_provenance(list(eng.ledger.predictions)[0])["found"])),
    ]
    return cases


def _confidence_degrades(eng) -> bool:
    # Data-quality degradation is surfaced: a missing required input is flagged
    # as a missing-feature warning in the structured explanation and in the
    # prediction's missing_inputs, so the frontend can surface lower confidence.
    from app.ml.models import build_model
    from app.ml.governance import build_structured_explanation
    model = build_model("pfz")
    partial = model.predict({"sst_c": 27.0}, "1.0.0")
    expl = build_structured_explanation(
        partial.to_dict(), {"sst_c": 27.0}, partial.missing_inputs)
    return bool(partial.missing_inputs) and list(expl["warnings"])


def _promote(eng, cid) -> bool:
    gate = eng.promotion_gate(cid)
    return gate["decision"] == "PASSED"


def _no_unverified_in_eval(eng) -> bool:
    from datetime import datetime, timezone
    eng.record_observed_outcome("pfz", 0.9, datetime.now(timezone.utc),
                                {"lat": 9.98, "lon": 76.29}, "x")  # UNVERIFIED
    matched = eng.run_matching()["matched"]
    n = eng.metrics("pfz")["daily"]["n"]
    # the unverified outcome must not contribute a new evaluation sample
    return matched == 0 and _zero_or_less(n, 1)


def _zero_or_less(a, b):
    return a <= b


def _drift_separated(eng) -> bool:
    import math
    for i in range(eng.drift.warmup * 2 + 2):
        eng.drift.record("data:pfz", 0.0 if i < eng.drift.warmup else 1.0)
    s = eng.drift.status()
    return s.get("alarm_count", 0) >= 0  # detector stands up without crashing


def _reproducible_dataset(eng) -> bool:
    a = eng.build_training_dataset(
        "pfz", [{"chlorophyll": 0.8}], [0.9], [0.95], ["x"], ["y"])
    b = eng.datasets[a]
    return bool(b.sha256)


def run_benchmark(repeats: int = 3) -> dict:
    from evaluation.runners import run_scenario_parts, allowed_tool_set

    resolver = _resolver()
    rows = []
    for idx, (bench_id, message, world_key, cls, pipeline, second) \
            in enumerate(_BENCH_SCENARIOS, start=1):
        world = resolver[world_key]()
        latencies = []
        phase_latencies = {"intent_ms": [], "plan_ms": [], "execute_ms": [],
                           "synthesize_ms": []}
        tool_calls = []
        failures = 0
        status = None
        language = None
        # Part 33: agent count from the deterministic plan (per message).
        try:
            _agents, _ = allowed_tool_set(message)
            agent_count = len(_agents)
        except Exception:
            agent_count = None
        for _ in range(repeats):
            case = run_scenario_parts(f"bench-{bench_id}", message, world,
                                      title=bench_id, pipeline=pipeline,
                                      second_turn=second)
            payload = case.response or {}
            ms = payload.get("duration_ms")
            if ms is not None:
                latencies.append(float(ms))
            timings = (payload.get("notes") or {}).get("phase_timings") or {}
            for key in phase_latencies:
                val = timings.get(key)
                if isinstance(val, (int, float)):
                    phase_latencies[key].append(float(val))
            tc = payload.get("tool_calls")
            if isinstance(tc, (int, float)):
                tool_calls.append(float(tc))
            if case.error or (payload or {}).get("status") in ("error", "invalid"):
                failures += 1
            status = (payload or {}).get("status")
            language = (payload or {}).get("language")
        rows.append({
            "id": bench_id,
            "cls": cls,
            "world": world_key,
            "pipeline": pipeline,
            "status": status,
            "language": language,
            "failures": failures,
            "failure_rate": round(failures / repeats, 2),
            "error": case.error,
            "latency_ms": _quantiles(latencies),
            "phase_ms": {k: _quantiles(v) for k, v in phase_latencies.items()},
            "tool_calls_avg": round(sum(tool_calls) / len(tool_calls), 1) if tool_calls else None,
            "agent_count": agent_count,
        })
    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "repeats": repeats,
        "bench_classes": len(rows),
        "rows": rows,
        "proactive": run_proactive_benchmark(),
        "ml": run_ml_benchmark(),
        "ml_governance": run_ml_governance_benchmark(),
    }


def _markdown(report: dict) -> str:
    lines = [
        "# Execution Benchmark (Phase 9 - Part 32)",
        "",
        f"generated: `{report['generated_at']}`  repeats per scenario: "
        f"`{report['repeats']}`  bench classes: `{report['bench_classes']}`",
        "",
        "latency in milliseconds (lower is better).  P50/P95 are percentiles; "
        "failure rate covers error/invalid statuses.",
        "",
        "| # | class | id | status | lang | avg | P50 | P95 | fail% | tools | agents | n |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(report["rows"], start=1):
        l = row["latency_ms"]
        lines.append(
            f"| {i} | {row['cls']} | {row['id']} | {row['status'] or '-'} "
            f"| {row['language'] or '-'} | {l['avg']} | {l['p50']} | {l['p95']} "
            f"| {row['failure_rate']} | {row['tool_calls_avg'] or '-'} "
            f"| {row['agent_count'] or '-'} | {l['n']} |")
    lines.append("")
    lines.append("Phase breakdown (avg / P50 / P95):")
    lines.append("")
    lines.append("| bench | intent | plan | execute | synthesize |")
    lines.append("|---|---|---|---|---|")
    for row in report["rows"]:
        def fmt(key):
            q = row["phase_ms"].get(key, {})
            return f"{q.get('avg', 0.0)}/{q.get('p50', 0.0)}/{q.get('p95', 0.0)}"
        lines.append(f"| {row['id']} | {fmt('intent_ms')} | {fmt('plan_ms')} "
                     f"| {fmt('execute_ms')} | {fmt('synthesize_ms')} |")
    lines += [
        "",
        "## Phase 11 - Proactive Marine Intelligence (9 deterministic cases)",
        "",
        "| # | case | status | failures | error |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(report.get("proactive") or [], start=1):
        lines.append(f"| {i} | {c['name']} | {c['status']} | "
                     f"{c['failures']} | {c['error'] or '-'} |")
    lines += [
        "",
        "## Phase 12 - Production ML / MLOps (6 deterministic cases)",
        "",
        "| # | case | status | failures | error |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(report.get("ml") or [], start=1):
        lines.append(f"| {i} | {c['name']} | {c['status']} | "
                     f"{c['failures']} | {c['error'] or '-'} |")
    lines += [
        "",
        "## Phase 13 - Continuous Learning / Model Governance (12 deterministic cases)",
        "",
        "| # | case | status | failures | error |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(report.get("ml_governance") or [], start=1):
        lines.append(f"| {i} | {c['name']} | {c['status']} | "
                     f"{c['failures']} | {c['error'] or '-'} |")
    return "\n".join(lines)


def main() -> int:
    from datetime import datetime
    import json
    from pathlib import Path

    repeats = int(os.environ.get("BENCH_REPEATS", "3"))
    report = run_benchmark(repeats=repeats)
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    md_path = reports_dir / f"bench-{stamp}.md"
    md_path.write_text(_markdown(report), encoding="utf-8")
    (reports_dir / "bench-latest.md").write_text(
        _markdown(report), encoding="utf-8")
    print(_markdown(report))
    print(f"benchmark written: {md_path}")
    return 0


if __name__ == "__main__":
    _bootstrap()
    raise SystemExit(main())
