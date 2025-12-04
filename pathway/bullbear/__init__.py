"""
Bull-Bear Debate Module for Pathway
====================================

This module provides a LangGraph-based bull-bear debate system
with mem0 memory persistence for financial analysis.

Main Entry Points:
- run_debate_and_generate_report: Run debate and get facilitator report
- BullBearDebate: Direct access to LangGraph workflow

Classes:
- DebateState: TypedDict for debate state
- DebatePoint: Dataclass for individual debate points
- BullBearConfig: Configuration class

Usage:
    from bullbear import run_debate_and_generate_report
    
    result = run_debate_and_generate_report("AAPL", max_rounds=5)
    print(result["recommendation"])
"""

# Core classes
from .state import DebateState, DebatePoint, DebateParty
from .config import get_config, BullBearConfig

# Main debate class
from .graph import BullBearDebate

# Runner functions (backward compatible API)
from .debate_runner import (
    run_debate_and_generate_report,
    get_debate_progress,
    save_facilitator_report,
    extract_recommendation,
)

__all__ = [
    # Core
    "DebateState",
    "DebatePoint",
    "DebateParty",
    # Config
    "get_config",
    "BullBearConfig",
    # Main class
    "BullBearDebate",
    # Runner functions
    "run_debate_and_generate_report",
    "get_debate_progress",
    "save_facilitator_report",
    "extract_recommendation",
]
