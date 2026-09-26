from typing import List, Literal
from langgraph.graph import StateGraph, START, END
from schemas.state import OrcaState
from .nodes import (
    router_node,
    live_data_node,
    rag_node,
    geospatial_node,
    ml_node,
    generation_node
)

def route_intent(state: OrcaState) -> List[str]:
    """
    Conditional routing logic based on the intent decided by the router_node.
    """
    if state.intent_type == "simple":
        # Skip heavy processing, go straight to answering
        return ["generation_node"]
    else:
        # Trigger the parallel subagents
        return ["live_data_node", "rag_node", "geospatial_node"]

# 1. Initialize the Graph with our strict Pydantic State
workflow = StateGraph(OrcaState)

# 2. Add all nodes to the graph
workflow.add_node("router_node", router_node)
workflow.add_node("live_data_node", live_data_node)
workflow.add_node("rag_node", rag_node)
workflow.add_node("geospatial_node", geospatial_node)
workflow.add_node("ml_node", ml_node)
workflow.add_node("generation_node", generation_node)

# 3. Define the Edges (The Flow)

# Start by sending the user query to the router
workflow.add_edge(START, "router_node")

# Conditional Edge: Router decides if we go to Generation (Simple) OR Parallel Agents (Complex)
workflow.add_conditional_edges(
    "router_node",
    route_intent,
    {
        "generation_node": "generation_node",
        "live_data_node": "live_data_node",
        "rag_node": "rag_node",
        "geospatial_node": "geospatial_node"
    }
)

# Parallel Synchronization: All three agents must finish before the ML Node can run
workflow.add_edge("live_data_node", "ml_node")
workflow.add_edge("rag_node", "ml_node")
workflow.add_edge("geospatial_node", "ml_node")

# After ML scores are generated, send the fully enriched state to the Generation Node
workflow.add_edge("ml_node", "generation_node")

# After generation, the workflow ends
workflow.add_edge("generation_node", END)

# 4. Compile the graph
# This creates the executable application
app = workflow.compile()
