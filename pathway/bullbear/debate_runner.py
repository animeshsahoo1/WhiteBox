"""
Bull-Bear Debate Runner
Orchestrates the debate and generates facilitator report.
Supports background execution with live progress tracking.
"""
import os
import sys
import json
import threading
from typing import Dict, Any, TypedDict, Annotated, Optional, Callable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic_memory.memory_system import AgenticMemorySystem
from bullbear.researchers.bull_researcher import create_bull_researcher
from bullbear.researchers.bear_researcher import create_bear_researcher
from bullbear.researchers.facilitator import (
    generate_facilitator_report,
    extract_recommendation,
    start_facilitator_stream,
    stop_facilitator_stream,
    get_facilitator_status,
)
from redis_cache import get_redis_client, get_reports_for_symbol, _build_symbol_key

load_dotenv()

# Reports directory for debate files
REPORTS_DIR = os.environ.get("REPORTS_DIR", "./reports/bullbear")


def clear_debate_files(symbol: str):
    """Clear/reset all debate files for a new debate session.
    
    Clears bull_debate.md, bear_debate.md, and facilitator_report.md
    so each debate starts fresh.
    """
    symbol = symbol.upper()
    symbol_dir = os.path.join(REPORTS_DIR, symbol)
    os.makedirs(symbol_dir, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Reset bull_debate.md
    bull_path = os.path.join(symbol_dir, "bull_debate.md")
    bull_template = f"""# Bull Analyst Debate History - {symbol}

## Debate Rounds
*No rounds yet...*

---
*Last Updated: {timestamp} UTC*
"""
    with open(bull_path, "w", encoding="utf-8") as f:
        f.write(bull_template)
    
    # Reset bear_debate.md  
    bear_path = os.path.join(symbol_dir, "bear_debate.md")
    bear_template = f"""# Bear Analyst Debate History - {symbol}

## Debate Rounds
*No rounds yet...*

---
*Last Updated: {timestamp} UTC*
"""
    with open(bear_path, "w", encoding="utf-8") as f:
        f.write(bear_template)
    
    # Reset facilitator_report.md
    facilitator_path = os.path.join(symbol_dir, "facilitator_report.md")
    with open(facilitator_path, "w", encoding="utf-8") as f:
        f.write(f"<!-- Round: 0 -->\n\n# Facilitator Report - {symbol}\n\n*Waiting for debate to start...*\n")
    
    print(f"🗑️  [DEBATE] Cleared all debate files for {symbol}")


# Track active debates
_active_debates: Dict[str, Dict] = {}


# ============================================================
# STATE DEFINITIONS
# ============================================================
class InvestDebateState(TypedDict):
    bull_history: Annotated[str, "Bullish conversation history"]
    bear_history: Annotated[str, "Bearish conversation history"]
    history: Annotated[str, "Full conversation history"]
    current_response: Annotated[str, "Latest response"]
    count: Annotated[int, "Number of exchanges"]
    last_speaker: Annotated[str, "Last agent who spoke"]


class BullBearState(TypedDict):
    company_of_interest: Annotated[str, "Company/Symbol being analyzed"]
    market_report: Annotated[str, "Market analysis report"]
    sentiment_report: Annotated[str, "Sentiment analysis report"]
    news_report: Annotated[str, "News analysis report"]
    fundamentals_report: Annotated[str, "Fundamental analysis report"]
    investment_debate_state: Annotated[InvestDebateState, "Debate state"]
    sender: Annotated[str, "Current sender"]
    max_rounds: Annotated[int, "Maximum debate rounds"]
    room_id: Annotated[str, "Room ID for pub/sub events"]


# ============================================================
# CONDITIONAL LOGIC
# ============================================================
def should_continue_debate(state: BullBearState) -> str:
    """Determine if debate should continue or end."""
    debate_state = state["investment_debate_state"]
    max_rounds = state.get("max_rounds", 2)
    
    if debate_state["count"] >= 2 * max_rounds:
        return "end"
    
    last_speaker = debate_state.get("last_speaker", "")
    
    if last_speaker == "bull_researcher":
        return "bear_researcher"
    elif last_speaker == "bear_researcher":
        return "bull_researcher"
    else:
        return "bull_researcher"


# ============================================================
# GRAPH SETUP
# ============================================================
def create_bull_bear_graph(llm, max_rounds: int = 2, on_turn: Callable = None):
    """Create the LangGraph workflow for bull-bear debate.
    
    Args:
        llm: Language model instance
        max_rounds: Number of debate rounds
        on_turn: Optional callback(state) called after each turn
    """
    session_id = str(uuid4())[:8]
    
    bear_memory = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model="openai/gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        collection_name=f"bear_memories_{session_id}",
    )

    bull_memory = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model="openai/gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        collection_name=f"bull_memories_{session_id}",
    )

    _bull_node = create_bull_researcher(llm, bull_memory)
    _bear_node = create_bear_researcher(llm, bear_memory)
    
    # Wrap nodes to call callback after each turn
    def bull_node(state):
        result = _bull_node(state)
        if on_turn:
            on_turn(result)
        return result
    
    def bear_node(state):
        result = _bear_node(state)
        if on_turn:
            on_turn(result)
        return result
    
    workflow = StateGraph(BullBearState)
    workflow.add_node("bull_researcher", bull_node)
    workflow.add_node("bear_researcher", bear_node)
    workflow.add_edge(START, "bull_researcher")
    
    workflow.add_conditional_edges(
        "bull_researcher",
        should_continue_debate,
        {"bear_researcher": "bear_researcher", "end": END},
    )
    
    workflow.add_conditional_edges(
        "bear_researcher",
        should_continue_debate,
        {"bull_researcher": "bull_researcher", "end": END},
    )
    
    return workflow.compile()


# ============================================================
# PROGRESS TRACKING
# ============================================================


def _save_error(symbol: str, error: str, started_at: str):
    """Save error state to progress file."""
    progress = {
        "symbol": symbol,
        "status": "error",
        "error": error,
        "started_at": started_at,
        "updated_at": datetime.utcnow().isoformat(),
    }
    save_debate_progress(symbol, progress)


def save_debate_progress(symbol: str, progress: Dict[str, Any]):
    """Save debate progress to file for live tracking."""
    reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports", "debate")
    symbol_dir = os.path.join(reports_dir, symbol)
    os.makedirs(symbol_dir, exist_ok=True)
    
    progress_path = os.path.join(symbol_dir, "debate_latest.json")
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    
    # Also update in-memory tracker
    _active_debates[symbol] = progress


def get_debate_progress(symbol: str) -> Optional[Dict[str, Any]]:
    """Get current debate progress."""
    # Check in-memory first
    if symbol in _active_debates:
        return _active_debates[symbol]
    
    # Check file
    reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports", "debate")
    progress_path = os.path.join(reports_dir, symbol, "debate_latest.json")
    
    if os.path.exists(progress_path):
        with open(progress_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def run_debate_and_generate_report(
    symbol: str,
    max_rounds: int = 2,
    background: bool = False,
    room_id: str = None
) -> Dict[str, Any]:
    """
    Run bull-bear debate and generate facilitator report.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        max_rounds: Number of debate rounds (default 2)
        background: If True, run in background thread (returns immediately)
        room_id: Room ID for pub/sub events (defaults to symbol)
        
    Returns:
        Dict with status, facilitator_report, recommendation, etc.
        If background=True, returns immediately with status="started"
    """
    symbol = symbol.upper()
    if room_id is None:
        room_id = symbol
        print(f"Room id is None so making room_id = {symbol}")
    
    if background:
        # Initialize progress and start background thread
        progress = {
            "symbol": symbol,
            "status": "started",
            "max_rounds": max_rounds,
            "current_round": 0,
            "rounds": [],
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        save_debate_progress(symbol, progress)
        
        thread = threading.Thread(
            target=_run_debate_sync,
            args=(symbol, max_rounds, room_id),
            daemon=True
        )
        thread.start()
        
        return {"status": "started", "symbol": symbol, "max_rounds": max_rounds}
    
    return _run_debate_sync(symbol, max_rounds, room_id)


def _run_debate_sync(symbol: str, max_rounds: int, room_id: str = None) -> Dict[str, Any]:
    """Internal sync debate execution with progress tracking."""
    symbol = symbol.upper()
    if room_id is None:
        room_id = symbol
    started_at = datetime.utcnow().isoformat()
    
    # Progress tracking callback
    def on_turn(state):
        debate_state = state.get("investment_debate_state", {})
        count = debate_state.get("count", 0)
        last_speaker = debate_state.get("last_speaker", "")
        # Round number: (count // 2) + 1
        # count=0 -> round 1, count=1 -> round 1, count=2 -> round 2, count=3 -> round 2
        current_round = (count // 2) + 1
        
        progress = {
            "symbol": symbol,
            "status": "in_progress",
            "max_rounds": max_rounds,
            "current_round": current_round,
            "total_exchanges": count,
            "last_speaker": last_speaker,
            "bull_history": debate_state.get("bull_history", ""),
            "bear_history": debate_state.get("bear_history", ""),
            "current_response": debate_state.get("current_response", ""),
            "started_at": started_at,
            "updated_at": datetime.utcnow().isoformat(),
        }
        save_debate_progress(symbol, progress)
    
    print(f"\n{'='*60}")
    print(f"🎭 Starting Bull-Bear Debate for {symbol}")
    print(f"   Max Rounds: {max_rounds}")
    print(f"{'='*60}\n")
    
    # Step 1: Fetch reports from Redis
    print("📡 Fetching reports from Redis...")
    
    try:
        reports = get_reports_for_symbol(symbol)
    except Exception as e:
        _save_error(symbol, str(e), started_at)
        raise ValueError(f"Failed to fetch reports from Redis: {e}")
    
    if not reports:
        _save_error(symbol, f"No reports found for {symbol}", started_at)
        raise ValueError(f"No reports found for {symbol}")
    
    market_report = reports.get("market", {}).get("content", "")
    sentiment_report = reports.get("sentiment", {}).get("content", "")
    news_report = reports.get("news", {}).get("content", "")
    fundamental_report = reports.get("fundamental", {}).get("content", "")
    
    missing = []
    if not market_report:
        missing.append("market")
    if not sentiment_report:
        missing.append("sentiment")
    if not news_report:
        missing.append("news")
    if not fundamental_report:
        missing.append("fundamental")
    
    if missing:
        print(f"⚠️  Missing reports: {', '.join(missing)}")
        # Continue anyway with available reports
    
    print(f"✅ Reports loaded:")
    print(f"   Market: {len(market_report)} chars")
    print(f"   Sentiment: {len(sentiment_report)} chars")
    print(f"   News: {len(news_report)} chars")
    print(f"   Fundamental: {len(fundamental_report)} chars")
    
    # Step 2: Run LangGraph debate
    print(f"\n🎭 Running debate ({max_rounds} rounds)...")
    
    # Clear old debate files before starting new debate
    clear_debate_files(symbol)
    
    # Start facilitator stream BEFORE debate begins
    # It will watch bear_debate.md and auto-generate facilitator reports after each round
    print(f"🎬 Starting facilitator stream for {symbol}...")
    start_facilitator_stream(symbol, room_id)
    
    # Note: llm param is kept for API compatibility but bull/bear use litellm directly
    graph = create_bull_bear_graph(llm=None, max_rounds=max_rounds, on_turn=on_turn)
    
    initial_state: BullBearState = {
        "company_of_interest": symbol,
        "market_report": market_report or "No market data available.",
        "sentiment_report": sentiment_report or "No sentiment data available.",
        "news_report": news_report or "No news data available.",
        "fundamentals_report": fundamental_report or "No fundamental data available.",
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "history": "",
            "current_response": "",
            "count": 0,
            "last_speaker": "",
        },
        "sender": "",
        "max_rounds": max_rounds,
        "room_id": room_id,  # Use room_id for pub/sub events
    }
    
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        _save_error(symbol, str(e), started_at)
        raise RuntimeError(f"Debate execution failed: {e}")
    
    debate_state = final_state["investment_debate_state"]
    
    print(f"\n✅ Debate completed!")
    print(f"   Total exchanges: {debate_state['count']}")
    
    # Facilitator report is auto-generated by streaming watcher
    # Just wait a moment for it to process
    import time
    time.sleep(3)  # Give facilitator stream time to generate
    
    # Get facilitator status (report generated by stream)
    facilitator_status = get_facilitator_status(symbol)
    facilitator_report = facilitator_status.get("report", "") if facilitator_status else ""
    recommendation = facilitator_status.get("recommendation", "PENDING") if facilitator_status else "PENDING"
    
    print(f"   Recommendation: {recommendation}")
    
    # Stop the facilitator stream now that debate is done
    stop_facilitator_stream(symbol)
    
    # Save final completed status
    final_progress = {
        "symbol": symbol,
        "status": "completed",
        "max_rounds": max_rounds,
        "total_exchanges": debate_state["count"],
        "recommendation": recommendation,
        "bull_history": debate_state["bull_history"],
        "bear_history": debate_state["bear_history"],
        "started_at": started_at,
        "completed_at": datetime.utcnow().isoformat(),
    }
    save_debate_progress(symbol, final_progress)
    
    # Clean up in-memory tracker
    _active_debates.pop(symbol, None)
    
    print(f"\n{'='*60}")
    print(f"✅ Complete! Facilitator report ready for {symbol}")
    print(f"{'='*60}\n")
    
    return {
        "status": "success",
        "symbol": symbol,
        "rounds_completed": max_rounds,
        "total_exchanges": debate_state["count"],
        "recommendation": recommendation,
        "facilitator_report": facilitator_report,
    }


if __name__ == "__main__":
    # Test run
    result = run_debate_and_generate_report("AAPL", max_rounds=2)
    print(f"\nResult: {result['status']}")
    print(f"Recommendation: {result['recommendation']}")