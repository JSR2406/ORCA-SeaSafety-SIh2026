# KnowledgeIngestionService - the production knowledge ingestion pipeline.
#
# Responsibilities (all DB-path pluggable for offline unit tests):
#   * parse raw bytes (text/html/pdf) into a structured ParsedDocument;
#   * normalize without rewriting content;
#   * derive conservative metadata (fields only set when actually found);
#   * deterministic sentence-aware chunking with reproducible chunk hashes;
#   * idempotent persistence keyed on document SHA-256 checksum;
#   * real embedding only when an embedding provider is configured.
# The service never fabricates data, dates, or vectors.
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("knowledge_ingestion")

from app.ingestion.chunker import (
    Chunk, ChunkOptions, _chunk_hash, chunk_document)
from app.ingestion.document_normalization import normalize_document
from app.ingestion.document_parsers import (
    ParsedDocument, UnsupportedFormatError, parser_for)
from app.ingestion.knowledge_metadata import (
    DocumentMetadata, compute_checksum, extract_document_metadata, to_datetime)
from app.services.knowledge_rag import (
    BaseEmbedder, KnowledgeChunkStore, NotConfiguredEmbedder, PgChunkStore)
from app.services.knowledge_rag import get_knowledge_rag_service  # noqa: F401


@dataclass
class IngestionReport:
    status: str  # inserted | updated | unchanged | unsupported_format | error
    filename: str
    document_id: Optional[int] = None
    checksum: Optional[str] = None
    chunks_total: int = 0
    embedded: int = 0
    skipped_embed: int = 0
    format: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    note: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KnowledgeStore:
    """Write-path abstraction over knowledge documents and chunks."""

    async def find_document_by_hash(self, checksum: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def find_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def list_documents(self, status: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def list_chunks(self, document_id: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def insert_document(self, document: Dict[str, Any]) -> int:
        raise NotImplementedError

    async def insert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    async def update_document_status(self, document_id: int, status: str,
                                     fields: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError

    async def update_chunk_embedding(self, chunk_id: int, embedding: str,
                                     model: str, version: str,
                                     dimensions: int,
                                     chunk_hash: Optional[str] = None) -> None:
        raise NotImplementedError


class PgKnowledgeStore(KnowledgeStore):
    """PostgreSQL-backed store using the SQLAlchemy models."""

    def __init__(self, session_factory=None):
        from app.db.client import get_session

        self._session_factory = session_factory or get_session

    @staticmethod
    def _doc_to_dict(doc) -> Dict[str, Any]:
        return {
            "id": doc.id,
            "title": doc.title,
            "source_url": doc.source_url,
            "source_type": doc.source_type,
            "tags": list(doc.tags or []),
            "language": doc.language,
            "document_hash": doc.document_hash,
            "ingestion_status": doc.ingestion_status,
            "authority": doc.authority,
            "document_type": doc.document_type,
            "publication_date": (doc.publication_date.isoformat()
                                 if doc.publication_date else None),
            "effective_date": (doc.effective_date.isoformat()
                               if doc.effective_date else None),
            "expiry_date": (doc.expiry_date.isoformat()
                            if doc.expiry_date else None),
            "active": doc.active,
            "version": doc.version,
            "source_reference": doc.source_reference,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }

    async def find_document_by_hash(self, checksum: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select

        from app.db.models import KnowledgeDocument

        async with self._session_factory() as session:
            result = await session.execute(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.document_hash == checksum))
            doc = result.scalar_one_or_none()
            return self._doc_to_dict(doc) if doc else None

    async def list_documents(self, status: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        from app.db.models import KnowledgeDocument

        async with self._session_factory() as session:
            stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.id)
            if status is not None:
                stmt = stmt.where(
                    KnowledgeDocument.ingestion_status == status)
            result = await session.execute(stmt.limit(limit))
            return [self._doc_to_dict(doc) for doc in result.scalars()]

    async def find_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select

        from app.db.models import KnowledgeDocument

        async with self._session_factory() as session:
            result = await session.execute(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.id == document_id))
            doc = result.scalar_one_or_none()
            return self._doc_to_dict(doc) if doc else None

    @staticmethod
    def _chunk_to_dict(chunk) -> Dict[str, Any]:
        return {
            "id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "section": chunk.section,
            "page": chunk.page,
            "heading": chunk.heading,
            "chunk_hash": chunk.chunk_hash,
            "embedding": chunk.embedding,
            "embedding_model": chunk.embedding_model,
            "embedding_version": chunk.embedding_version,
            "metadata": chunk.metadata_json or {},
        }

    async def list_chunks(self, document_id: int) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        from app.db.models import KnowledgeChunk, KnowledgeDocument

        if document_id is None:
            return []
        async with self._session_factory() as session:
            result = await session.execute(
                select(KnowledgeChunk)
                .join(KnowledgeDocument,
                      KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(KnowledgeChunk.document_id == document_id)
                .order_by(KnowledgeChunk.chunk_index))
            return [self._chunk_to_dict(row) for row in result.scalars()]

    async def insert_document(self, document: Dict[str, Any]) -> int:
        from app.db.models import KnowledgeDocument

        async with self._session_factory() as session:
            row = KnowledgeDocument(
                title=document["title"],
                source_url=document.get("source_url"),
                source_type=document.get("source_type") or "document",
                tags=document.get("tags") or [],
                language=document.get("language") or "en-IN",
                document_hash=document["document_hash"],
                ingestion_status=document.get("ingestion_status") or "pending",
                authority=document.get("authority"),
                document_type=document.get("document_type") or "other",
                publication_date=to_datetime(document.get("publication_date")),
                effective_date=to_datetime(document.get("effective_date")),
                expiry_date=to_datetime(document.get("expiry_date")),
                active=document.get("active", True),
                version=document.get("version") or 1,
                source_reference=document.get("source_reference"),
            )
            session.add(row)
            await session.flush()
            new_id = row.id
        return new_id

    async def insert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        from app.db.models import KnowledgeChunk

        async with self._session_factory() as session:
            for item in chunks:
                session.add(KnowledgeChunk(
                    document_id=item["document_id"],
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    section=item.get("section"),
                    page=item.get("page"),
                    heading=item.get("heading"),
                    chunk_hash=item.get("chunk_hash"),
                    embedding=item.get("embedding"),
                    embedding_model=item.get("embedding_model"),
                    embedding_version=item.get("embedding_version"),
                    embedding_dimensions=item.get("embedding_dimensions"),
                    embedded_at=item.get("embedded_at"),
                    metadata_json=item.get("metadata") or {},
                ))

    async def update_document_status(self, document_id: int, status: str,
                                     fields: Optional[Dict[str, Any]] = None) -> None:
        from sqlalchemy import update

        from app.db.models import KnowledgeDocument

        values: Dict[str, Any] = {"ingestion_status": status}
        if fields:
            for key, value in fields.items():
                if key in ("publication_date", "effective_date", "expiry_date"):
                    values[key] = to_datetime(value)
                else:
                    values[key] = value
        async with self._session_factory() as session:
            await session.execute(
                update(KnowledgeDocument)
                .where(KnowledgeDocument.id == document_id)
                .values(**values))

    async def update_chunk_embedding(self, chunk_id: int, embedding: str,
                                     model: str, version: str,
                                     dimensions: int,
                                     chunk_hash: Optional[str] = None) -> None:
        from sqlalchemy import update

        from app.db.models import KnowledgeChunk

        values = dict(embedding=embedding, embedding_model=model,
                      embedding_version=version,
                      embedding_dimensions=dimensions,
                      embedded_at=datetime.now(timezone.utc))
        if chunk_hash:
            values["chunk_hash"] = chunk_hash
        async with self._session_factory() as session:
            await session.execute(
                update(KnowledgeChunk)
                .where(KnowledgeChunk.id == chunk_id)
                .values(**values))


def _chunk_dicts(document_id: int, checksum: str, chunks: List[Chunk]) -> List[Dict[str, Any]]:
    return [
        {
            "document_id": document_id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "section": c.section,
            "page": c.page,
            "heading": c.heading,
            "chunk_hash": c.chunk_hash,
            "stable_id": c.stable_id,
            "metadata": c.metadata,
        }
        for c in chunks
    ]


class KnowledgeIngestionService:
    def __init__(self, store: Optional[KnowledgeStore] = None,
                 embedder: Optional[BaseEmbedder] = None):
        self.store = store or PgKnowledgeStore()
        self.embedder = embedder or self._default_embedder()

    @staticmethod
    def _default_embedder() -> BaseEmbedder:
        try:
            from app.config import get_settings

            settings = get_settings()
            if settings.embeddings_api_key and settings.embeddings_endpoint:
                from app.services.knowledge_rag import OpenAICompatibleEmbedder

                return OpenAICompatibleEmbedder(
                    api_key=settings.embeddings_api_key,
                    endpoint=settings.embeddings_endpoint,
                    model=settings.embeddings_model,
                    dimensions=settings.embeddings_dimensions,
                )
        except Exception:  # noqa: BLE001 - settings access must not break ingestion
            pass
        return NotConfiguredEmbedder()

    # ------------------------------------------------------------ main entry
    async def ingest_document(
        self, content: bytes, *,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[dict] = None,
        chunk_options: Optional[ChunkOptions] = None,
    ) -> IngestionReport:
        checksum = compute_checksum(content)
        report = IngestionReport(status="pending", filename=filename or "document",
                                 checksum=checksum)

        try:
            parser = parser_for(filename=filename, mime_type=mime_type)
        except UnsupportedFormatError as exc:
            report.status = "unsupported_format"
            report.error = str(exc)
            return report

        try:
            parsed = parser.parse_bytes(content)
        except UnsupportedFormatError as exc:
            report.status = "unsupported_format"
            report.error = str(exc)
            return report

        normalized = normalize_document(parsed)
        meta = extract_document_metadata(normalized.text, filename, metadata)
        report.format = parsed.format
        report.limitations = list(parsed.limitations)
        report.metadata = meta.to_dict()
        if not parsed.sections:
            report.status = "error"
            report.error = "document produced no readable content"
            return report

        existing = await self.store.find_document_by_hash(checksum)
        if existing:
            document_id = existing["id"]
            report.document_id = document_id
            chunks = await self.store.list_chunks(document_id)

            if existing.get("ingestion_status") == "completed" and chunks:
                report.status = "unchanged"
                report.chunks_total = len(chunks)
                if self.embedder.available and any(
                        not c.get("embedding") for c in chunks):
                    try:
                        report.embedded = await self._embed_chunks(chunks)
                        report.note = "backfilled missing embeddings"
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("embedding backfill failed: %s", exc)
                        report.note = f"embedding backfill skipped: {exc}"
                return report

            # Existing but incomplete document (crash / provider failure left it
            # pending). Reuse its stored chunks - never re-insert them, that
            # trips uq_knowledge_chunk_index. Finish the pipeline on the same
            # rows: mark completed and embed whatever is still missing.
            if not chunks:
                await self._write_chunks(document_id, checksum, normalized,
                                         chunk_options)
                chunks = await self.store.list_chunks(document_id)
            await self.store.update_document_status(document_id, "completed")
            report.status = "unchanged"
            report.chunks_total = len(chunks)
            if self.embedder.available:
                try:
                    report.embedded = await self._embed_chunks(chunks)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("embedding step failed: %s", exc)
                    report.note = f"chunks stored; embedding skipped: {exc}"
            if not report.note:
                report.note = ("document already present; stored chunks "
                               "reused without re-insert")
            return report

        document_id = await self.store.insert_document({
            "title": meta.title or "untitled",
            "document_hash": checksum,
            "ingestion_status": "pending",
            "source_url": meta.source_url,
            "source_type": meta.source_type,
            "tags": meta.tags,
            "language": meta.language,
            "authority": meta.authority,
            "document_type": meta.document_type,
            "publication_date": meta.publication_date,
            "effective_date": meta.effective_date,
            "expiry_date": meta.expiry_date,
            "active": True,
            "version": meta.version,
            "source_reference": meta.source_reference,
        })
        report.document_id = document_id

        chunks = await self._write_chunks(document_id, checksum, normalized,
                                          chunk_options)
        await self.store.update_document_status(document_id, "completed")
        stored_chunks = await self.store.list_chunks(document_id)
        report.status = "inserted"
        report.chunks_total = len(stored_chunks)
        try:
            report.embedded = await self._embed_chunks(stored_chunks)
        except Exception as exc:  # noqa: BLE001 - embed failure must not corrupt
            logger.warning("embedding step failed after storage: %s", exc)
            report.note = f"chunks stored; embedding skipped: {exc}"
        if not self.embedder.available:
            report.note = ("no embedding provider configured; chunks stored "
                           "without vectors (FTS-only retrieval)")
        elif report.embedded == 0 and not report.note:
            report.note = ("chunks stored without vectors "
                           "(provider returned no embeddings)")
        return report

    async def _write_chunks(self, document_id: int, checksum: str,
                            parsed: ParsedDocument,
                            chunk_options: Optional[ChunkOptions]) -> List[Chunk]:
        chunks = chunk_document(checksum, parsed, chunk_options)
        items = _chunk_dicts(document_id, checksum, chunks)
        await self.store.insert_chunks(items)
        return chunks

    # -------------------------------------------------------------- embedding
    async def _embed_chunks(self, chunks: List[Dict[str, Any]],
                            force: bool = False,
                            chunk_hash: Optional[str] = None) -> int:
        if not self.embedder.available:
            return 0
        embedded = 0
        for item in chunks:
            if not force and item.get("embedding"):
                continue
            vector = await self.embedder.embed(item["content"])
            if not vector:
                continue
            hash_value = chunk_hash(item["id"]) if callable(chunk_hash) else chunk_hash
            await self.store.update_chunk_embedding(
                item["id"],
                json.dumps([float(v) for v in vector]),
                self.embedder.name,
                f"md:{self.embedder.name}:{self.embedder.dimensions}",
                self.embedder.dimensions,
                chunk_hash=hash_value,
            )
            embedded += 1
        return embedded

    async def embed_document(self, document_id: int) -> IngestionReport:
        """Embed (or re-embed) every chunk of a document unconditionally."""
        chunks = await self.store.list_chunks(document_id)
        report = IngestionReport(
            status="completed", filename="", document_id=document_id,
            chunks_total=len(chunks),
            embedded=await self._embed_chunks(chunks, force=True),
        )
        if not self.embedder.available:
            report.status = "embedding_unavailable"
            report.note = ("no embedding provider configured; chunks stored "
                           "without vectors (FTS-only retrieval)")
        return report

    # --------------------------------------------------- pending status driver
    async def validate_ingested(self, document):
        """Validate that a source document was processed correctly: chunks were
        written and (when an embedder is available) embeddings were produced."""
        if isinstance(document, int) or (
                isinstance(document, str) and document.isdigit()):
            fetched = await self.store.find_document_by_id(int(document))
            document = fetched if fetched else {"id": int(document)}
        if isinstance(document, dict):
            if not document.get("id"):
                document = {"id": document.get("id"),
                            "ingestion_status": "pending"}
            checks = {
                "id": document.get("id"),
                "status": document.get("ingestion_status"),
                "has_hash": bool(document.get("document_hash")),
                "has_title": bool(document.get("title")),
            }
            chunks = await self.store.list_chunks(document["id"])
        else:
            checks = {"id": document.id, "status": document.ingestion_status,
                      "has_hash": bool(document.document_hash),
                      "has_title": bool(document.title)}
            chunks = await self.store.list_chunks(document.id)
        checks["chunks_total"] = len(chunks)
        checks["chunks_written"] = len(chunks) > 0
        checks["chunk_hashes"] = all(bool(c.get("chunk_hash")) for c in chunks)
        if self.embedder.available:
            checks["embedded_reported"] = sum(
                1 for c in chunks if c.get("embedding"))
        checks["processed_ok"] = (
            checks.get("has_hash", False)
            and checks.get("has_title", False)
            and checks["chunks_written"]
            and checks["chunk_hashes"]
            and not (self.embedder.available and checks.get("chunks_total")
                     and checks.get("embedded_reported", 0) == 0))
        return {"document": checks, "chunk_count": len(chunks)}

    async def process_pending(self, seed_dir: Optional[str] = None,
                              items: Optional[List[Dict[str, Any]]] = None,
                              chunk_options: Optional[ChunkOptions] = None,
                              ) -> Dict[str, Any]:
        """Drive every PENDING document through the full pipeline.

        A PENDING document is one that was registered (insert_document wrote the
        row) but whose chunks were never written - e.g. a crash mid-ingestion.
        This driver re-ingests them from their source bytes (from ``items`` or
        by match against a seed directory) so they reach "completed", then
        validates each was processed correctly.

        Returns a report with per-document validation, never fabricating output
        for documents whose source content cannot be located.
        """
        loader = _build_seed_loader(seed_dir) if seed_dir else None
        pending = await self.store.list_documents(status="pending")
        processed, failures, skipped = [], [], []

        for doc in pending:
            content = None
            filename = None
            if items:
                for item in items:
                    if (item.get("title") == doc.get("title")
                            or item.get("filename") == doc.get("title")
                            or item.get("filename") == (
                                doc.get("source_url") or "").split("/")[-1]):
                        content = item.get("content")
                        filename = item.get("filename")
                        break
            if content is None and loader is not None:
                loaded = loader(doc.get("title"))
                if loaded is not None:
                    content, filename = loaded
            if content is None:
                failures.append({
                    "title": doc.get("title"),
                    "reason": "source content unavailable for pending document",
                })
                continue
            if isinstance(content, str):
                content = content.encode("utf-8")
            filename = filename or doc.get("title") or "document"
            if "." not in filename:
                filename += ".txt"  # parser_for needs a readable extension
            report = await self.ingest_document(
                content,
                filename=filename,
                chunk_options=chunk_options,
                metadata={"title": doc.get("title") or "untitled",
                          "source_url": doc.get("source_url")},
            )
            if report.status in ("inserted", "unchanged"):
                if report.document_id is None:
                    failures.append({"title": doc.get("title"),
                                     "reason": "ingestion produced no "
                                               "document id"})
                    continue
                validated = await self.validate_ingested(report.document_id)
                processed.append({
                    "title": doc.get("title"),
                    "document_id": report.document_id,
                    "status": report.status,
                    "chunks_total": report.chunks_total,
                    "embedded": report.embedded,
                    "validation": validated,
                })
            else:
                failures.append({"title": doc.get("title"),
                                 "reason": report.error or report.status})

        remaining = await self.store.list_documents(status="pending")
        skipped = [{"title": d.get("title")} for d in remaining]
        return {
            "pending_before": len(pending),
            "processed": processed,
            "failures": failures,
            "pending_remaining": len(remaining),
            "pending_still_pending": skipped,
        }

    async def reembed_document(self, document_id: int) -> IngestionReport:
        """Re-embed only chunks whose content hash actually changed."""
        if not self.embedder.available:
            return IngestionReport(
                status="embedding_unavailable", filename="",
                document_id=document_id,
                note="no embedding provider configured; nothing re-embedded")

        document = await self.store.find_document_by_id(document_id)
        chunks = await self.store.list_chunks(document_id)
        changed = [c for c in chunks if _chunk_hash_mismatch(document, c)]
        hashes = {c["id"]: _chunk_hash(document["document_hash"], c["chunk_index"],
                                        c["content"], c.get("section"),
                                        c.get("page"))
                  for c in changed}
        embedded = await self._embed_chunks(
            changed, force=True,
            chunk_hash=lambda cid: hashes.get(cid))
        return IngestionReport(
            status="completed", filename="", document_id=document_id,
            chunks_total=len(chunks), embedded=embedded,
            skipped_embed=len(chunks) - len(changed),
            note=f"{len(chunks) - len(changed)} unchanged chunks skipped")


def _build_seed_loader(seed_dir: str):
    """Return ``title -> (bytes, filename)`` loader for the seed directory.

    Used by the PENDING driver to re-locate source bytes for documents that
    were registered but never completed.  Returns None when the directory does
    not exist so the caller can report honestly that content is unavailable.
    """
    import os

    if not seed_dir or not os.path.isdir(seed_dir):
        return None

    def load(title: str):
        if not title:
            return None
        for name in os.listdir(seed_dir):
            if name == title or os.path.splitext(name)[0] in (title,
                                                               os.path.splitext(title)[0]):
                try:
                    with open(os.path.join(seed_dir, name), "rb") as fh:
                        return (fh.read(), name)
                except OSError:
                    return None
        return None

    return load


def _chunk_hash_mismatch(document: Optional[Dict[str, Any]],
                         chunk: Dict[str, Any]) -> bool:
    if document is None:
        return True
    from app.ingestion.chunker import _chunk_hash

    expected = _chunk_hash(
        document["document_hash"], chunk["chunk_index"], chunk["content"],
        chunk.get("section"), chunk.get("page"))
    return expected != chunk.get("chunk_hash")


_knowledge_ingestion: Optional[KnowledgeIngestionService] = None


def get_knowledge_ingestion_service() -> KnowledgeIngestionService:
    global _knowledge_ingestion
    if _knowledge_ingestion is None:
        _knowledge_ingestion = KnowledgeIngestionService()
    return _knowledge_ingestion