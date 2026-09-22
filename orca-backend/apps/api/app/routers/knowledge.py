# Knowledge pipeline API (RAG).
#
# Read + operator endpoints for the end-to-end RAG pipeline:
#   * GET  /status        - KB health: documents by ingestion status, chunk /
#                           embedding counts, pgvector layer verification
#   * GET  /pending       - documents still stuck at ingestion_status=pending
#   * POST /process-pending - drive pending documents through the pipeline from
#                           their source bytes (seed dir or inline items)
#   * POST /query         - full RAG: retrieve context + grounded answer with
#                           [n] citations (LLM when configured, else verbatim
#                           extractive mode)
import structlog
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.knowledge_generation import get_knowledge_generation_service
from app.services.knowledge_rag import get_knowledge_rag_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class PendingSourceItem(BaseModel):
    title: str = Field(min_length=1, description="Document title (used to match)"
                       )
    content: str = Field(min_length=1, description="Document text content")
    filename: Optional[str] = Field(
        None, description="Source filename with a readable extension")


class ProcessPendingRequest(BaseModel):
    seed_dir: Optional[str] = Field(
        None, description="Directory with the source PDFs to re-ingest")
    items: Optional[List[PendingSourceItem]] = Field(
        None, description="Inline source items for pending documents")


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500,
                       description="Free-text knowledge question")
    top_k: int = Field(5, ge=1, le=10, description="Context chunks to retrieve")
    generate: Optional[bool] = Field(
        None, description="Default auto: LLM when configured. False forces "
                          "extractive mode.")
    ingestion_status: Optional[str] = Field(
        None, description="Restrict retrieval to this ingestion status")


@router.get("/status")
async def knowledge_status() -> Dict[str, Any]:
    """Pipeline health: documents by status, chunk counts, vector layer."""
    return await get_knowledge_rag_service().kb_overview()


@router.get("/pending")
async def pending_documents() -> Dict[str, Any]:
    from app.ingestion.knowledge_ingestion import get_knowledge_ingestion_service

    docs = await get_knowledge_ingestion_service().store.list_documents(
        status="pending", limit=50)
    return {"count": len(docs), "documents": docs}


@router.post("/process-pending")
async def process_pending(body: ProcessPendingRequest) -> Dict[str, Any]:
    from app.ingestion.knowledge_ingestion import get_knowledge_ingestion_service

    if not body.seed_dir and not body.items:
        raise HTTPException(
            status_code=422,
            detail="Provide seed_dir or items so pending documents can be "
                   "re-ingested from their source bytes.")
    items = ([
        {"title": item.title, "filename": item.filename or item.title,
         "content": item.content}
        for item in body.items
    ] if body.items else None)
    report = await get_knowledge_ingestion_service().process_pending(
        seed_dir=body.seed_dir, items=items)
    return report


@router.post("/query")
async def knowledge_query(body: KnowledgeQueryRequest) -> Dict[str, Any]:
    """End-to-end RAG: retrieve + grounded answer with citations."""
    answer = await get_knowledge_generation_service().answer(
        body.query, top_k=body.top_k, generate=body.generate,
        ingestion_status=body.ingestion_status)
    return answer.to_dict()