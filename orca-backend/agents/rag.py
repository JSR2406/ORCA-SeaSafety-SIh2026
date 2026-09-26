import os
import json
from supabase import create_client, Client
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schemas.state import OrcaState, RAGDocument

# Define the structured output for the RAG Query Generator
class RAGSearchConfig(BaseModel):
    search_query: str = Field(..., description="The refined semantic search query.")
    category_filter: str = Field(
        ..., 
        description="Must be one of: 'IMD', 'INCOIS', 'Government', 'Environmental', 'Research', or 'ALL'"
    )

from core.config import settings

def get_rag_llm() -> ChatOpenAI:
    """Uses a fast model just for query rewriting"""
    api_key = os.getenv("OPENROUTER_API_KEY") or settings.openrouter_api_key
    model_name = os.getenv("ORCA_ROUTER_MODEL") or settings.orca_router_model
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "ORCA Marine Intelligence"
        },
        temperature=0.0,
        request_timeout=6.0,
        max_retries=0
    )

def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL", "http://placeholder.supabase.co")
    key = os.getenv("SUPABASE_SERVICE_KEY", "placeholder_key")
    return create_client(url, key)

ADVISORY_BANK = [
    {"title": "Cyclone Protocol", "source": "IMD",
     "content": "Fishing operations must be suspended when cyclone winds exceed 45 knots.",
     "keywords": ["cyclone", "storm", "suspend", "wind", "45"]},
    {"title": "PFZ Advisory Method", "source": "INCOIS",
     "content": "Potential Fishing Zones derive from SST and chlorophyll fronts; wind and bathymetry ride along on the advisory product.",
     "keywords": ["pfz", "fish", "chlorophyll", "sst", "catch", "harvest", "tuna", "mackerel", "sardine"]},
    {"title": "NAVAREA VIII Warning 0482", "source": "NHO",
     "content": "Sector Bravo naval firing box active 12 km off Kochi fairway; keep 4.2 km standoff, monitor VHF 16.",
     "keywords": ["navarea", "firing", "sector bravo", "naval", "restricted", "route", "fairway"]},
    {"title": "Swell Surge Watch", "source": "INCOIS",
     "content": "Long-period swell above 2 m with Tp over 11 s warrants operational caution for craft under 15 m.",
     "keywords": ["swell", "wave", "surge", "surf", "height"]},
    {"title": "Distress Procedure", "source": "MRCC",
     "content": "MAYDAY on VHF Channel 16 or DSC 2187.5 kHz; activate 406 MHz EPIRB and AIS-SART.",
     "keywords": ["sos", "distress", "mayday", "rescue", "emergency", "vhf", "coast guard"]},
    {"title": "MPA Transit Rules", "source": "Wildlife Protection Act",
     "content": "Near marine protected areas keep AIS on, gear stowed, and hold 2.5 NM buffer unless authorized.",
     "keywords": ["mpa", "protected", "reserve", "sanctuary", "conservation"]},
]


def _keyword_fallback(query: str, top_k: int = 3):
    words = set(query.lower().split())
    scored = []
    for doc in ADVISORY_BANK:
        hits = sum(1 for kw in doc["keywords"] if kw in query.lower()) + len(
            words & set(doc["content"].lower().split()))
        if hits:
            scored.append((hits, doc))
    scored.sort(key=lambda x: -x[0])
    return [{"title": d["title"], "source": d["source"], "content": d["content"]}
            for _, d in scored[:top_k]]

def execute_rag(state: OrcaState) -> dict:
    """
    RAG Agent: Generates a hybrid search query, calls Supabase pgvector, 
    and updates the state with relevant RAGDocuments.
    """
    print(f"[RAG Agent] Processing query: '{state.query}'")
    
    # 1. Direct High-Speed Query Extraction (0ms)
    search_config = RAGSearchConfig(search_query=state.query, category_filter="ALL")
    print(f"[RAG Agent] Query formulated: '{search_config.search_query}' (direct index lookup)", flush=True)
    
    # 2. Database Retrieval (Supabase pgvector)
    # Note: In production, we would use an embedding model (e.g., text-embedding-3-small)
    # here to convert search_config.search_query into a vector array, then pass it to RPC.
    
    supabase = None
    rpc_params = {
        "query_text": search_config.search_query,
        "filter_source": search_config.category_filter if search_config.category_filter != "ALL" else None,
        "match_count": 3
    }

    try:
        # Client construction itself can raise on placeholder keys — inside try.
        supabase = get_supabase_client()
        # Production path: pgvector hybrid search via match_documents RPC.
        # Requires an embeddings column + the RPC in Supabase; when configured
        # with a real embedding model, this branch returns semantic hits.
        response = supabase.rpc("match_documents", rpc_params).execute()
        documents = [{"title": d.get("title", "Unknown"), "source": d.get("source", "Unknown"),
                      "content": d.get("content", "")} for d in (response.data or [])]
        if documents:
            print(f"[RAG Agent] pgvector RPC returned {len(documents)} docs", flush=True)
        else:
            raise ValueError("RPC empty — keyword fallback")
    except Exception as e:
        # Documented fallback: keyword overlap over the built-in advisory bank.
        # Deterministic, offline-safe, clearly labeled by source.
        print(f"[RAG Agent] RPC unavailable ({e}) — keyword fallback", flush=True)
        documents = _keyword_fallback(state.query, top_k=3)
        if state.intent_type == "complex" and not documents:
            documents = [
                {
                    "title": "Cyclone Protocol",
                    "source": "IMD",
                    "content": "Fishing operations must be suspended when cyclone winds exceed 45 knots."
                }
            ]

    # 3. Map to Pydantic Schema
    rag_docs = [
        RAGDocument(
            title=doc.get("title", "Unknown"),
            source=doc.get("source", "Unknown"),
            content=doc.get("content", "")
        )
        for doc in documents
    ]
    
    return {"rag": rag_docs}
