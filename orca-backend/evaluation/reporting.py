# Phase 7 - JSON + markdown report writers.
import json
import os
from typing import Any, Dict, List


def _write_json(report: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def _verdict_badge(verdict: str) -> str:
    return {"pass": "PASS", "fail": "**FAIL**",
            "partial": "PARTIAL", "not_executed": "-"}[verdict]


def _markdown(report: Dict[str, Any]) -> str:
    scorecard = report["scorecard"]
    lines: List[str] = []
    lines.append("# Phase 7 - Adversarial Evaluation Report")
    lines.append("")
    lines.append(f"Generated: `{report.get('generated_at')}`")
    lines.append("")
    lines.append("## Scorecard (Part 43)")
    lines.append("")
    lines.append(f"**Overall:** {scorecard['overall_score']}%  |  "
                 f"**Safety score:** {scorecard['safety_score']}% "
                 "(Part 44, weighted safety-critical)")
    lines.append("")
    lines.append("| Part | Requirement | Verdict | Checks |")
    lines.append("|---|---|---|---|")
    for part in scorecard["parts"]:
        badge = _verdict_badge(part["verdict"])
        count = f"{part['passed_checks']}/{part['passed_checks'] + part['failed_checks']}"
        lines.append(f"| {part['part']} | {part['title']} | {badge} | {count} |")
    lines.append("")

    fails = [p for p in scorecard["parts"] if p["verdict"] == "fail"]
    if fails:
        lines.append("## Failures and hardening")
        lines.append("")
        for part in fails:
            lines.append(f"### Part {part['part']} - {part['title']}")
            lines.append("")
            for detail in part["details"]:
                lines.append(f"- {detail}")
            lines.append("")
    lines.append("## Golden scenarios (Part 42)")
    lines.append("")
    lines.append("| Case | Verdict |")
    lines.append("|---|---|")
    all_ok = True
    for golden in report["golden"]:
        ok = all(r["ok"] for r in golden["results"])
        all_ok = all_ok and ok
        lines.append(f"| {golden['case']} | {'PASS' if ok else '**FAIL**'} |")
    lines.append("")
    if not all_ok:
        lines.append("Golden-case failures:")
        lines.append("")
        for golden in report["golden"]:
            for r in golden["results"]:
                if not r["ok"]:
                    lines.append(f"- {golden['case']} {r['check']}: {r.get('detail')}")
        lines.append("")

    lines.append("## Adversarial scenarios (Parts 4-41)")
    lines.append("")
    lines.append("| Scenario | Case | Pass |")
    lines.append("|---|---|---|")
    for scenario in report["scenarios"]:
        ok = all(r["ok"] for r in scenario["results"])
        count = sum(1 for r in scenario["results"] if r["ok"])
        total = len(scenario["results"])
        lines.append(f"| {scenario['case']} ({scenario['world']}) "
                     f"| {count}/{total} | {'PASS' if ok else '**FAIL**'} |")
    lines.append("")
    for scenario in report["scenarios"]:
        failed = [r for r in scenario["results"] if not r["ok"]]
        if not failed:
            continue
        lines.append(f"### {scenario['case']} failures")
        lines.append("")
        for r in failed:
            lines.append(f"- `{r['check']}`: {r.get('detail')}")
        lines.append("")
    return "\n".join(lines)


def write_reports(report: Dict[str, Any], out_dir: str = "reports") -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    base = report.get("timestamp", "latest")
    json_path = os.path.join(out_dir, f"phase7-{base}.json")
    md_path = os.path.join(out_dir, f"phase7-{base}.md")
    _write_json(report, json_path)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_markdown(report))
    # Stable "latest" copies for CI/docs links.
    for latest, current in (("phase7-latest.json", json_path),
                            ("phase7-latest.md", md_path)):
        with open(os.path.join(out_dir, latest), "w", encoding="utf-8") as fh:
            fh.write(open(current, encoding="utf-8").read())
    return {"json": json_path, "markdown": md_path, "dir": out_dir}


def print_summary(report: Dict[str, Any]) -> None:
    scorecard = report["scorecard"]
    print("=" * 70)
    print(f"Phase 7 evaluation - overall {scorecard['overall_score']}% | "
          f"safety {scorecard['safety_score']}%")
    print(f"parts: pass={scorecard['part_totals']['pass']} "
          f"fail={scorecard['part_totals']['fail']} "
          f"partial={scorecard['part_totals']['partial']} "
          f"not_executed={scorecard['part_totals']['not_executed']}")
    print(f"golden cases: {sum(all(r['ok'] for r in g['results']) for g in report['golden'])}/13")
    print("=" * 70)