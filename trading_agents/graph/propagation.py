# TradingAgents/graph/propagation.py

from typing import Dict, Any


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(self, company_name: str, trade_date: str) -> Dict[str, Any]:
        return {
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),

            "investment_debate_state": {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
                "count": 0,
            },

            "risk_debate_state": {
                "risky_response": "",
                "safe_response": "",
                "neutral_response": "",
            },

            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",

            "investment_plan": "",
            "trader_investment_plan": "",
            "final_trade_decision": "",
            "symbol": "",
            "trade_signal": {},
            "trade_signal_args": {},
            "final_report": "",
        }


    def get_graph_args(self) -> Dict[str, Any]:
        """Get arguments for the graph invocation."""
        return {
            "stream_mode": "values",
            "config": {"recursion_limit": self.max_recur_limit},
        }
