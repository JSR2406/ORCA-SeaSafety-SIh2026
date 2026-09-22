# KnowledgeGenerationService - grounded answer generation for the RAG pipeline.
#
# Two honest modes:
#   * llm_generated - an LLM is configured (LLM_API_KEY), the answer is produced
#     from the retrieved context only, with per-chunk [n] citations.
#   * extractive     - no LLM configured: the "answer" is a verbatim, labelled
#     excerpt of the top retrieved chunk(s).  Never fabricated prose.
# plus an explicit no_documents mode when retrieval returns nothing (the system
# says so rather than hallucinating).
#
# Grounding: every generated answer is checked - citation markers must reference
# real context indices and the answer must share tokens with the context.
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.services.knowledge_rag import (
    KnowledgeRagService,
    RetrievalResult,
    get_knowledge_rag_service,
)

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[(\d+)\]")
_WORD_RE = re.compile(r"[a-z0-9]{3,}")


def _tokens(text: str) -> set:
    return set(_WORD_RE.findall((text or "").lower()))


@dataclass
class RagAnswer:
    query: str
    answer: str
    mode: str  # llm_generated | extractive | no_documents
    citation_count: List[int] = field(default_factory=list)
    grounded: bool = False
    grounding_ratio: float = 0.0
    note: str = ""
    retrieval: Optional[Dict[str, Any]] = None
    latency_ms: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "mode": self.mode,
            "citation_count": self.citation_count,
            "grounded": self.grounded,
            "grounding_ratio": self.grounding_ratio,
            "note": self.note,
            "retrieval": self.retrieval,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class KnowledgeGenerationService:
    """Composes retrieval + (optional) LLM generation with grounding checks."""

    def __init__(self, retriever: Optional[KnowledgeRagService] = None,
                 llm_factory: Optional[Callable[[], AsyncOpenAI]] = None):
        self.retriever = retriever or get_knowledge_rag_service()
        self._llm_factory = llm_factory

    # ------------------------------------------------------------------ config
    @property
    def llm_available(self) -> bool:
        return bool(settings.rag_generation_enabled and settings.llm_api_key)

    def _client(self) -> AsyncOpenAI:
        if self._llm_factory is not None:
            return self._llm_factory()
        kwargs: Dict[str, Any] = {"api_key": settings.llm_api_key}
        if settings.llm_provider == "openrouter":
            kwargs["base_url"] = "https://openrouter.ai/api/v1"
        return AsyncOpenAI(**kwargs)

    # ------------------------------------------------------------- main entry
    async def answer(self, query: str, top_k: Optional[int] = None,
                     validity_only: bool = True,
                     ingestion_status: Optional[str] = None,
                     generate: Optional[bool] = None,
                     now: Optional[datetime] = None,
                     ) -> RagAnswer:
        """Retrieve context for ``query`` and answer it honestly.

        ``generate=False`` forces extractive mode even when an LLM is
        configured; ``generate=None`` auto-decides from configuration.
        """
        if top_k is None:
            top_k = settings.rag_max_citations
        timing: Dict[str, float] = {}
        t0 = time.perf_counter()
        retrieval = await self.retriever.retrieve(
            query, limit=top_k, validity_only=validity_only, now=now,
            ingestion_status=ingestion_status)
        timing["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        result = retrieval.to_dict()
        if not retrieval.chunks:
            return RagAnswer(
                query=query,
                answer=("No relevant documents were found in the knowledge "
                        "base for this query. No answer is fabricated."),
                mode="no_documents",
                grounded=False,
                note="retrieval returned zero chunks",
                retrieval=result,
                latency_ms=timing,
            )

        coverage = self._top_coverage(query, retrieval)
        if coverage < settings.rag_min_top_coverage:
            return RagAnswer(
                query=query,
                answer=("No relevant documents were found in the knowledge "
                        "base for this query. The top retrieved chunk shares "
                        f"only {coverage:.0%} of the query terms, which is "
                        "below the relevance threshold. No answer is "
                        "fabricated."),
                mode="no_documents",
                grounded=False,
                note=(f"top-chunk query-token coverage {coverage:.0%} below "
                      f"rag_min_top_coverage "
                      f"({settings.rag_min_top_coverage:.0%})"),
                retrieval=result,
                latency_ms=timing,
            )

        context_text = self._build_context(retrieval)
        want_llm = self.llm_available if generate is None else (
            generate and self.llm_available)

        if not want_llm:
            answer_text, mode = self._extractive(retrieval)
            timing["generation_ms"] = 0.0
        else:
            t1 = time.perf_counter()
            try:
                answer_text = await self._llm_answer(query, context_text, top_k)
                mode = "llm_generated"
                timing["generation_ms"] = round(
                    (time.perf_counter() - t1) * 1000, 2)
            except Exception as exc:  # noqa: BLE001 - degrade honestly
                logger.warning("LLM generation failed (%s); extractive fallback",
                               exc)
                answer_text, mode = self._extractive(retrieval)
                timing["generation_ms"] = round(
                    (time.perf_counter() - t1) * 1000, 2)

        citations, grounded, ratio = self._grounding_check(
            answer_text, context_text, len(retrieval.chunks))
        return RagAnswer(
            query=query,
            answer=answer_text,
            mode=mode,
            citation_count=citations,
            grounded=grounded,
            grounding_ratio=ratio,
            note=self._note(mode, retrieval),
            retrieval=result,
            latency_ms=timing,
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _top_coverage(query: str, retrieval: RetrievalResult) -> float:
        """Fraction of query tokens present in the top retrieved chunk.

        0.0 means the best match is essentially unrelated - the signal the
        relevance gate uses to answer "no relevant documents" honestly.
        """
        query_tokens = _tokens(query)
        if not query_tokens:
            return 0.0
        top_tokens = _tokens(retrieval.chunks[0].get("content") or "")
        overlap = len(query_tokens & top_tokens)
        return overlap / len(query_tokens)

    def _build_context(self, retrieval: RetrievalResult) -> str:
        budget = max(settings.rag_max_context_chars, 500)
        blocks = []
        used = 0
        for i, chunk in enumerate(retrieval.chunks, start=1):
            header = f"[{i}] {chunk['title']}"
            if chunk.get("section"):
                header += f" / {chunk['section']}"
            if chunk.get("page") is not None:
                header += f" (p.{chunk['page']})"
            if chunk.get("source_url"):
                header += f" <{chunk['source_url']}>"
            if chunk.get("document_validity"):
                header += f" validity={chunk['document_validity']}"
            block = f"{header}\n{chunk['content']}"
            if used + len(block) > budget:
                block = block[: budget - used]
            blocks.append(block)
            used += len(block)
            if used >= budget:
                break
        return "\n\n".join(blocks)

    def _extractive(self, retrieval: RetrievalResult):
        snippet = retrieval.chunks[0]["content"]
        note_fragments = [f"from {retrieval.chunks[0]['title']}"]
        if retrieval.chunks[0].get("section"):
            note_fragments.append(retrieval.chunks[0]["section"])
        answer = (
            f"Excerpt ({', '.join(note_fragments)}):\n\n{snippet}\n\n"
            "[1]"
        )
        return answer, "extractive"

    @staticmethod
    def _note(mode: str, retrieval: RetrievalResult) -> str:
        if mode == "llm_generated":
            note = f"LLM answer grounded in {len(retrieval.chunks)} retrieved chunk(s); context: {retrieval.note}"
        else:
            note = ("no LLM configured; verbatim excerpt of top chunk shown "
                    "(never fabricated). " + retrieval.note)
        return note

    # ---------------------------------------------------------------- the LLM
    PROMPT = """You are a marine-legal knowledge assistant.  Answer ONLY from the
retrieved context below.  If the context does not contain the answer, say so
explicitly and do not invent facts, rules, citations, or documents.

Rules:
- Cite your sources inline as [n] using the numbered blocks below.  You may cite
  several blocks at once, e.g. [1][3].
- Never invent authorities, URLs, dates, or statute numbers.
- Keep the answer concise and factual; quote exact numbers where the context
  states them.
- If a document is a draft or its validity is 'not_yet_effective'/'expired',
  say so when it matters.

Retrieved context:
{context}

Question: {query}
"""

    async def _llm_answer(self, query: str, context_text: str,
                          top_k: int) -> str:
        client = self._client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            timeout=settings.rag_generation_timeout_seconds,
            messages=[
                {"role": "system", "content":
                 self.PROMPT.format(context=context_text, query=query)},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=600,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\s*", "", content, flags=re.M)
            content = re.sub(r"\s*```$", "", content)
        return content

    # ------------------------------------------------------------ grounding
    def _grounding_check(self, answer_text: str, context_text: str,
                         n_chunks: int):
        """Verify every [n] citation points at a real context block and that
        the answer shares vocabulary with the retrieved context."""
        citations = sorted({
            int(m) for m in _CITATION_RE.findall(answer_text)
            if int(m) > 0 and int(m) <= n_chunks})
        answer_words = _tokens(answer_text)
        context_words = _tokens(context_text)
        if context_words and answer_words:
            ratio = len(answer_words & context_words) / len(answer_words)
        else:
            ratio = 0.0

        if answer_text.startswith("Excerpt ("):
            grounded = True  # verbatim excerpt is definitionally grounded
        else:
            # A generated answer must both cite real blocks AND share
            # vocabulary with the context it was told to use.
            grounded = bool(citations) and ratio >= 0.15
        if grounded and len(answer_words) < settings.rag_grounding_min_tokens:
            grounded = False  # too short to judge
        return citations, grounded, round(ratio, 4)


_knowledge_generation: Optional[KnowledgeGenerationService] = None


def get_knowledge_generation_service() -> KnowledgeGenerationService:
    global _knowledge_generation
    if _knowledge_generation is None:
        _knowledge_generation = KnowledgeGenerationService()
    return _knowledge_generation