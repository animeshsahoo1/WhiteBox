"""State definition for orchestrator graph"""

from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """State maintained throughout the conversation"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    query_type: str  # "request_strategy" | "input_strategy" | "general" | "risk_based" | "hypothesis_based" | "performance"
    user_inputted_strategy: dict  # If user provides a strategy directly
    need_hypothesis: bool
    hypotheses: list
    search_params: dict
    strategies_found: list
    selected_strategy: dict  # Final strategy to analyze
    backtest_results: dict
    web_search_results: list
    risk_analyses: dict
    final_response: str
    conversation_history: list
