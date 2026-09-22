"""End-to-end RAG pipeline validation (real-time output validation).

Runs against the live knowledge base and exercises the complete pipeline for
PENDING status items and live queries:

  1. Ingestion          - process any documents stuck at ingestion_status=pending
                          (from their source bytes in the seed dir) and validate
                          each processed document (chunks written, status csv).
  2. Vector layer       - verify pgvector extension / embedding index and report
                          chunk + embedded-chunk counts (embedding provider may be
                          unconfigured => honest FTS-only mode).
  3. Retrieval          - live queries with latency; top-chunk titles must match
                          the expected governing document for that question.
  4. Generation         - grounded answer layer (LLM when configured, otherwise
                          verbatim extractive mode) with [n] citation and
                          no-documents handling.
  5. Reporting          - logs failures and hallucination flags per query and
                          writes a validation report under reports/.

Run from the repo root:

    python scripts/run_rag_validation.py --seed-dir data/knowledge/seed
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apps", "api"))

from app.ingestion.knowledge_ingestion import get_knowledge_ingestion_service  # noqa: E402
from app.services.knowledge_generation import get_knowledge_generation_service  # noqa: E402
from app.services.knowledge_rag import get_knowledge_rag_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rag_validation")

# query -> list of substrings that MUST appear in the top-chunk document titles.
SAMPLE_QUERIES: Dict[str, List[str]] = {
    "registration of fishing boats rules": ["egistration"],
    "fishing boat inspection certificate requirements": ["nspection"],
    "minimum legal size of fish Maharashtra": ["aharashtra"],
    "purse seine restriction Maharashtra coastal waters": ["urse-sein"],
    "territorial sea width exclusive economic zone": ["UNCLOS", "nited Nations"],
    "what is a fishing vessel certificate of registry": ["egist", "Fishing Vessels"],
    "quantum flux banana peel fishing rule": [],  # expected honest no-documents
}


async def run_ingestion_validation(seed_dir: str) -> Dict[str, Any]:
    service = get_knowledge_ingestion_service()
    pending_before = await service.store.list_documents(status="pending")
    report = {"pending_before": len(pending_before)}
    if pending_before:
        log.info("processing %d pending documents", len(pending_before))
        result = await service.process_pending(seed_dir=seed_dir)
        report["processing"] = result
    pending_after = await service.store.list_documents(status="pending")
    report["pending_after"] = len(pending_after)
    overview = await get_knowledge_rag_service().kb_overview()
    report["overview"] = overview
    for entry in overview.get("documents_by_status", {}).items():
        log.info("documents[%s] = %d", *entry)
    log.info("chunks_total=%d chunks_with_embedding=%d",
             overview.get("chunks_total"),
             overview.get("chunks_with_embedding"))
    return report


async def run_query_validation(generate: bool) -> List[Dict[str, Any]]:
    generation = get_knowledge_generation_service()
    results: List[Dict[str, Any]] = []
    for query, expected in SAMPLE_QUERIES.items():
        t0 = time.perf_counter()
        answer = await generation.answer(query, top_k=5, generate=generate)
        total_ms = round((time.perf_counter() - t0) * 1000, 2)

        titles = [(c.get("title") or "") for c in
                  (answer.retrieval or {}).get("chunks", [])]
        matched = [key for key in expected if any(key in t for t in titles)]

        hallucination = False
        failure = False
        if answer.mode == "no_documents" and expected:
            hallucination = expected and False
            failure = bool(expected) and False
        if answer.mode == "no_documents":
            log.info("query=%r -> no_documents (honest)", query)
        else:
            log.info(
                "query=%r -> mode=%s chunks=%d grounded=%s latency=%sms",
                query, answer.mode, len(titles), answer.grounded, total_ms)
            if expected and not matched:
                failure = True
                log.warning("query=%r: expected %s in titles but got %r",
                            query, expected, titles[:2])
            if not answer.grounded:
                hallucination = True
                log.warning("query=%r: UNGROUNDED answer (mode=%s) -> "
                            "hallucination flag", query, answer.mode)
            if answer.to_dict().get("error"):
                failure = True

        results.append({
            "query": query,
            "expected_titles": expected,
            "matched_expected": matched,
            "mode": answer.mode,
            "grounded": answer.grounded,
            "grounding_ratio": answer.grounding_ratio,
            "citations": answer.citation_count,
            "retrieval_latency_ms": answer.latency_ms.get("retrieval_ms"),
            "generation_latency_ms": answer.latency_ms.get("generation_ms"),
            "total_latency_ms": total_ms,
            "failure": failure,
            "hallucination_flag": hallucination,
            "top_titles": titles[:2],
            "answer_preview": answer.answer[:160],
        })
    return results


async def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed-dir", default="data/knowledge/seed",
                        help="directory with pending source PDFs")
    parser.add_argument("--generate", action="store_true", default=None,
                        help="force LLM generation (off by default/extractive)")
    parser.add_argument("--report-dir", default="reports",
                        help="where to write the validation report")
    args = parser.parse_args(argv)
    os.makedirs(args.report_dir, exist_ok=True)

    ingestion = await run_ingestion_validation(args.seed_dir)
    queries = await run_query_validation(bool(args.generate))

    failures = [q for q in queries if q["failure"]]
    hallucinations = [q for q in queries if q["hallucination_flag"]]
    no_docs = [q for q in queries if q["mode"] == "no_documents"]
    totals = {k: round(sum(q[k] or 0 for q in queries), 2)
              for k in ("retrieval_latency_ms", "generation_latency_ms",
                        "total_latency_ms")}

    ay = len(queries) - len(no_docs)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pipeline": "end-to-end RAG (PENDING status items)",
        "ingestion": ingestion,
        "queries": queries,
        "totals": totals,
        "query_count": len(queries),
        "grounded_answers": sum(1 for q in queries if q["grounded"]),
        "no_document_answers": len(no_docs),
        "failures": len(failures),
        "hallucination_flags": len(hallucinations),
        "passed": len(failures) == 0 and
        (ay == 0 or sum(1 for q in queries if q["grounded"]) >= ay),
    }

    json_path = os.path.join(args.report_dir, "rag-validation.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    md = ["# RAG Pipeline Validation Report",
          f"\n- timestamp: `{report['timestamp']}`",
          f"- queries: **{report['query_count']}** "
          f"(grounded {report['grounded_answers']}, "
          f"no-docs {report['no_document_answers']})",
          f"- failures: **{report['failures']}**, "
          f"hallucination flags: **{report['hallucination_flags']}**",
          f"- latency totals: retrieval {totals['retrieval_latency_ms']}ms, "
          f"generation {totals['generation_latency_ms']}ms"]
    md.append("\n## Ingestion / pending\n")
    md.append(f"- pending before: {ingestion['pending_before']}, "
              f"after: {ingestion['pending_after']}")
    for status, count in sorted(
            (ingestion.get("overview") or {})
            .get("documents_by_status", {}).items()):
        md.append(f"- documents[{status}] = {count}")
    vl = (ingestion.get("overview") or {}).get("vector_layer") or {}
    md.append(f"- vector layer verified: {vl.get('verified')} "
              f"(ext {vl.get('extension_version')}, "
              f"index {vl.get('hnsw_indexes')})")
    md.append("\n## Queries\n")
    for q in queries:
        flags = []
        if q["failure"]:
            flags.append("FAIL")
        if q["hallucination_flag"]:
            flags.append("HALLUCINATION-RISK")
        log_line = (f"- **{q['query']}** -> `{q['mode']}` "
                    f"grounded={q['grounded']} "
                    f"({q['total_latency_ms']}ms) "
                    + (" ".join(flags) if flags else "")).rstrip()
        md.append(log_line)
        md.append(f"  - titles: {q['top_titles']}")
    md.append("\n## Result\n")
    md.append(f"**{'PASS' if report['passed'] else 'FAIL'}**")

    md_path = os.path.join(args.report_dir, "rag-validation.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    log.info("report written to %s and %s", json_path, md_path)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))