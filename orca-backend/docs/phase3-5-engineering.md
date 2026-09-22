# Phase 3.5 Engineering Report

Phase 3.5 is the knowledge-engine floor between the decision-tool work
(Phase 3, see `phase3-engineering.md`) and the agentic orchestrator
(Phase 4, see `phase4-agentic-orchestration.md`): a real ingestion pipeline
for marine advisories and a validity-aware hybrid retrieval upgrade. All
additive; existing APIs and the pre-existing test suite were preserved.

Governing rule, unchanged: **the system only surfaces values that exist in
real stored data, and retrieval reports exactly which pipeline produced
each result.**

## 1. Schema (migration `1a2b3c4d5e6f`)

`app/db/models.py`:

- `KnowledgeDocument` gained ingestion metadata: `authority`, `document_type`,
  `publication_date`, `effective_date`, `expiry_date`, `active`, `version`,
  `source_reference`, plus a `sha256` content checksum.
- `KnowledgeChunk` gained structural + embedding bookkeeping: `section`,
  `page`, `heading`, `chunk_hash`, `embedding_model`, `embedding_version`,
  `embedding_dimensions`, `embedded_at`.
- New orchestration tables for Phase 4 multi-turn memory and run telemetry:
  `ConversationContext`, `ExecutionRun`, `ExecutionTask`, `ExecutionEvent`
  (`MarineEvidence` already existed from Phase 2).

`python -m alembic heads` confirms `1a2b3c4d5e6f (head)`.

## 2. Ingestion pipeline (`app/ingestion/`)

- **Parsers** (`document_parsers.py`): `ParsedDocument`/`ParsedSection`;
  `TextParser`, `HtmlParser2` (clean heading/body separation without title
  leakage), and a minimal `PdfParser` (FlateDecode). `parser_for()` dispatches
  by mime type, falling back to file extension for `application/octet-stream`/
  binary uploads; unknown formats raise `UnsupportedFormatError`.
- **Normalization** (`document_normalization.py`): `normalize_text` strips
  leading whitespace per line; `drop_repeated_frame_lines` removes edge frame
  lines (edge occurrence >= 2 and total occurrence >= 3) that messengers use as
  text-only separators; document `full_text` includes headings so headings are
  searchable.
- **Chunking** (`chunker.py`): greedy, sentence-aware chunking with a soft
  character budget, deterministic `stable_id`/`chunk_hash`, hard-splitting for
  oversized single sentences, and a min-chars fallback so non-empty content
  never produces zero chunks. Overlap is a configurable `ChunkOptions` value.
- **Metadata extraction** (`knowledge_metadata.py`): document checksum,
  `publication_datetime`, `effective_date`/`expiry_date` (`is_expired`), and a
  title heuristic that skips reference lines, pure-number lines, and authority
  header lines.
- **Ingestion service** (`knowledge_ingestion.py`): `KnowledgeStore`/
  `PgKnowledgeStore` + `KnowledgeIngestionService.ingest_document(...)` —
  idempotent by content `sha256`; chunk hashes are persisted with every
  embedding write so re-embedding is skipped whenever hashes match.

## 3. Validity-aware retrieval (`app/services/knowledge_rag.py`)

- `_validity_filters()`: retrieval considers only documents that are `active`
  and within their `effective_date`/`expiry_date` window.
- `search_fts` / `search_vector` now select the full document context for each
  chunk (`section`, `page`, `heading`, `chunk_hash`, `authority`,
  `document_type`, publication/effective/expiry dates, `active`, `version`,
  `source_reference`, `language`, `tags`).
- `document_validity()` precedence: `not_yet_effective` > `expired` > `active`,
  so expired advisories can never surface as current guidance.
- `_chunk_view` exposes `retrieval_source` (`fts`/`vector`/`hybrid`), `rank`,
  `score` and `combined_score`; citations stream the verbatim excerpt.

## 4. Tests

`tests/test_knowledge_ingestion.py` (new) + updated `tests/test_knowledge_rag.py`
fakes cover parsers, normalization rules, chunker determinism, metadata/expiry,
ingestion idempotency, unsupported formats, embedding write/re-embed skip and
force paths, the `embedding_unavailable` note, and validity state annotations.

Debug fixes landed along the way: leading-space stripping in normalization, the
frame-line edge rule, HTML title leakage and `_flush_part` level capture,
octet-stream mime fallback, chunker min-chars fallback, metadata title
heuristic, `document_validity` precedence, citation score key, reembed hash
import, and `validity_only` compatibility on existing RAG test fakes.

**Regression:** `python -m pytest tests -q` reached **161 passed, 2 skipped**
after Phase 3.5 (baseline 135).

## 5. Compliance

- No fabricated values: every fused/retrieval value comes from real stored rows.
- Retrieval mode (`hybrid` vs `fts_only`) is reported on every answer.
- Embeddings are optional; without a configured provider, retrieval is FTS-only
  and never pretends otherwise (`NotConfiguredEmbedder` returns None).
- Ingestion is idempotent and never duplicates documents on re-upload.