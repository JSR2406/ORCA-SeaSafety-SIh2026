"""Decision entry point re-exported for API/agents."""
from ml.risk_engine.rules import RiskDecision, decide, to_dict

__all__ = ["RiskDecision", "decide", "to_dict"]
