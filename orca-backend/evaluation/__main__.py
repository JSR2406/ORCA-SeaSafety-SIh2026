# Phase 7 evaluation CLI: `python -m evaluation` from the repository root.
# Bootstraps sys.path for the app package, runs every golden case and
# adversarial scenario offline, scores the parts, writes JSON + markdown
# reports to reports/ and exits non-zero on any failed part.
import os
import sys


def _bootstrap() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (repo, os.path.join(repo, "apps", "api")):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def main() -> int:
    from datetime import datetime
    from evaluation.evaluators import run_all
    from evaluation.metrics import build_scorecard
    from evaluation.reporting import print_summary, write_reports

    runs = run_all()
    artifacts = {"docs_exist": False, "doc_text": ""}
    doc_path = os.path.join(os.getcwd(), "docs", "phase7-evaluation.md")
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as handle:
            artifacts["doc_text"] = handle.read()
        artifacts["docs_exist"] = True
    scorecard = build_scorecard(runs["golden"] + runs["scenarios"], artifacts)
    report = {
        "timestamp": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "generated_at": runs["generated_at"],
        "golden": runs["golden"],
        "scenarios": runs["scenarios"],
        "scorecard": scorecard,
    }
    paths = write_reports(report)
    print_summary(report)
    print(f"reports written: {paths['json']}, {paths['markdown']}")
    if scorecard["part_totals"]["fail"] or (
            scorecard["part_totals"]["pass"] < scorecard["part_totals"]["total"]):
        for part in scorecard["parts"]:
            if part["verdict"] == "fail":
                print(f"  FAIL Part {part['part']} - {part['title']}: "
                      f"{[d for d in part['details'][:3]]}")
        return 1
    return 0


if __name__ == "__main__":
    _bootstrap()
    raise SystemExit(main())