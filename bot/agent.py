# bot/agent.py - Friction Aware Reasoning
import os

MIN_EDGE = float(os.getenv("MIN_EDGE_THRESHOLD", 0.01))

def evaluate_opportunity(ticker, predicted_gain):
    """
    Surgical check: Is the gain worth the brokerage and mortgage hurdle?
    """
    if predicted_gain < MIN_EDGE:
        return {
            "action": "HOLD",
            "reason": f"Insufficient edge ({predicted_gain*100}% < {MIN_EDGE*100}% threshold)"
        }
    
    return {"action": "EXECUTE", "reason": "Edge exceeds friction threshold"}

