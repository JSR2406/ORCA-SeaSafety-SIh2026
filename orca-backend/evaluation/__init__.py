# Phase 7 - adversarial evaluation, safety hardening & production readiness.
#
# Repo-root package, runnable as `python -m evaluation` from the repository
# root (a small sys.path bootstrap in __main__.py adds apps/api).  The same
# modules are imported directly by tests/test_phase7_evaluation.py, which binds
# a database/network-free subset of the harness to the pytest suite.
#
# Framework layout mirrors the Phase 7 evaluation plan:
#   parts.py       machine-readable part catalog (Parts 1-52)
#   fixtures.py    deterministic world builders + fake MCP tool registry
#   datasets.py    golden dataset + ExpectedBehavior model + scenarios A..M
#   scenarios.py   adversarial scenario library mapped to Parts 4-41
#   runners.py     run a scenario against the real orchestrator stack
#   evaluators.py  deterministic checks over execution artifacts
#   metrics.py     scorecard + safety score aggregation
#   reporting.py   JSON + markdown report writers
#   __main__.py    CLI entry point
__version__ = "1.0.0"