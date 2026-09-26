import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schemas.state import OrcaState

# Define the strict output schema for the router
class IntentResponse(BaseModel):
    intent_type: str = Field(
        ..., 
        description="Must be exactly 'simple' or 'complex'."
    )

from core.config import settings

def get_router_llm() -> ChatOpenAI:
    """
    Initializes the OpenRouter LLM client for Nemotron.
    Expects OPENROUTER_API_KEY in the environment or settings.
    """
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
        temperature=0.0, # Must be deterministic for routing
        max_tokens=300,
        request_timeout=float(os.getenv("ORCA_LLM_TIMEOUT_S", "6.0")),
        max_retries=0
    )

def execute_router(state: OrcaState) -> dict:
    """
    Analyzes the incoming user query and updates the intent_type.
    Uses fast deterministic classification for instant (<1ms) response,
    falling back to structured LLM classification when necessary.
    Also detects query language (explicit state.language wins).
    """
    from core.sessions import detect_language
    lang = detect_language(state.query, override=getattr(state, "language", None))
    q_lower = state.query.lower().strip()
    
    # 1. Instant heuristic detection
    simple_indicators = [
        "what is", "what are", "explain", "who are", "define", "meaning of", 
        "tell me about", "describe", "why is", "how does", "what does",
        "hello", "hi", "hey", "help", "who created", "thank"
    ]
    complex_indicators = [
        "tomorrow", "today", "now", "tonight", "forecast", "safe to", "can i fish", 
        "should i go", "wave height", "wind speed", "swell", "cyclone", "storm",
        "route to", "fairway", "pfz", "coordinates", "navarea", "firing", "port of"
    ]
    
    # Fast path: definitions and general explanations
    if any(q_lower.startswith(ind) for ind in simple_indicators) and not any(ind in q_lower for ind in complex_indicators):
        print(f"[Router Instant Decision] SIMPLE ('{state.query}')", flush=True)
        return {"language": lang, "intent_type": "simple"}
        
    # Fast path: operational and navigational conditions
    if any(ind in q_lower for ind in complex_indicators):
        print(f"[Router Instant Decision] COMPLEX ('{state.query}')", flush=True)
        return {"language": lang, "intent_type": "complex"}

    # 2. Ambiguous query: query LLM with short timeout
    print(f"[Router] Analyzing ambiguous query with LLM: '{state.query}'", flush=True)
    try:
        llm = get_router_llm()
        structured_llm = llm.with_structured_output(IntentResponse)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Classify query as 'simple' (definitions/explanations) or 'complex' (live weather/ocean/fishing/routes). Output JSON."),
            ("human", "Query: {query}")
        ])
        chain = prompt | structured_llm
        result: IntentResponse = chain.invoke({"query": state.query})
        intent = result.intent_type.lower()
        if intent not in ["simple", "complex"]:
            intent = "simple"
        print(f"[Router Decision] {intent.upper()}", flush=True)
        return {"language": lang, "intent_type": intent}
    except Exception as e:
        print(f"[Router Fallback] {e} -> defaulting to simple", flush=True)
        return {"language": lang, "intent_type": "simple"}

