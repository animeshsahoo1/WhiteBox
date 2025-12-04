"""
Bull-Bear Debate Runner (New Implementation)
=============================================

This module wraps the new BullBearDebate LangGraph implementation
to provide backward compatibility with the existing API.

Uses:
- LangGraph for debate orchestration
- mem0 for memory persistence
- Pathway APIs for reports and RAG
- Redis for storing facilitator reports
"""
import os
import sys
import json
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client, _build_symbol_key

load_dotenv()

# Import our new implementation
from .graph import BullBearDebate, DebateState
from .config import get_config, BullBearConfig

# Track current debate (only one at a time - global lock)
_current_debate: Optional[Dict[str, Any]] = None
_debate_lock = threading.Lock()


def save_debate_progress(symbol: str, progress: Dict[str, Any]):
    """Save debate progress to file for live tracking."""
    reports_dir = Path(__file__).parent.parent / "reports" / "debate"
    symbol_dir = reports_dir / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    progress_path = symbol_dir / "debate_latest.json"
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    
    # Update in-memory tracker
    global _current_debate
    _current_debate = progress


def get_debate_progress(symbol: str) -> Optional[Dict[str, Any]]:
    """Get current debate progress."""
    global _current_debate
    
    # Check in-memory first
    if _current_debate and _current_debate.get("symbol") == symbol:
        return _current_debate
    
    # Check file
    reports_dir = Path(__file__).parent.parent / "reports" / "debate"
    progress_path = reports_dir / symbol / "debate_latest.json"
    
    if progress_path.exists():
        with open(progress_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_facilitator_report(symbol: str, report: str, reports_dir: str = None):
    """Save facilitator report to Redis and file."""
    # Save to Redis
    try:
        client = get_redis_client()
        symbol_key = _build_symbol_key(symbol)
        
        entry = {
            "symbol": symbol,
            "report_type": "facilitator",
            "content": report,
            "last_updated": datetime.utcnow().isoformat(),
            "received_at": datetime.utcnow().isoformat(),
        }
        
        client.hset(symbol_key, "facilitator", json.dumps(entry))
        client.sadd("reports:symbols", symbol)
        print(f"✅ Saved facilitator report to Redis for {symbol}")
    except Exception as e:
        print(f"⚠️  Failed to save to Redis: {e}")
    
    # Save to file
    if reports_dir is None:
        reports_dir = Path(__file__).parent.parent / "reports" / "facilitator"
    else:
        reports_dir = Path(reports_dir)
    
    symbol_dir = reports_dir / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = symbol_dir / "facilitator_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✅ Saved facilitator report to {report_path}")
    return str(report_path)


def save_debate_points_to_redis(symbol: str, debate_points: list):
    """Save debate points to Redis."""
    try:
        client = get_redis_client()
        symbol_key = _build_symbol_key(symbol)
        
        entry = {
            "symbol": symbol,
            "debate_points": debate_points,
            "last_updated": datetime.utcnow().isoformat(),
        }
        
        client.hset(symbol_key, "debate_points", json.dumps(entry))
        print(f"✅ Saved {len(debate_points)} debate points to Redis for {symbol}")
    except Exception as e:
        print(f"⚠️  Failed to save debate points to Redis: {e}")


def run_debate_and_generate_report(
    symbol: str,
    max_rounds: int = 5,
    background: bool = False,
    room_id: str = None,
    use_dummy: bool = False,
) -> Dict[str, Any]:
    """
    Run bull-bear debate and generate facilitator report.
    
    This is the main entry point that maintains backward compatibility
    with the existing API while using the new LangGraph implementation.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        max_rounds: Number of debate rounds (default 5)
        background: If True, run in background thread (returns immediately)
        room_id: Room ID for pub/sub events (defaults to symbol)
        use_dummy: If True, use dummy data instead of real APIs
        
    Returns:
        Dict with status, facilitator_report, recommendation, etc.
        If background=True, returns immediately with status="started"
    """
    global _current_debate, _debate_lock
    
    symbol = symbol.upper()
    if room_id is None:
        room_id = symbol
    
    # Check if debate is already running
    with _debate_lock:
        if _current_debate and _current_debate.get("status") == "in_progress":
            return {
                "status": "busy",
                "error": f"A debate is already in progress for {_current_debate.get('symbol')}",
                "current_symbol": _current_debate.get("symbol"),
            }
    
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
            args=(symbol, max_rounds, room_id, use_dummy),
            daemon=True
        )
        thread.start()
        
        return {"status": "started", "symbol": symbol, "max_rounds": max_rounds}
    
    return _run_debate_sync(symbol, max_rounds, room_id, use_dummy)


def _run_debate_sync(
    symbol: str, 
    max_rounds: int, 
    room_id: str = None,
    use_dummy: bool = False
) -> Dict[str, Any]:
    """Internal sync debate execution using new LangGraph implementation."""
    global _current_debate
    
    symbol = symbol.upper()
    if room_id is None:
        room_id = symbol
    started_at = datetime.utcnow().isoformat()
    
    print(f"\n{'='*60}")
    print(f"🎭 Starting Bull-Bear Debate for {symbol}")
    print(f"   Max Rounds: {max_rounds}")
    print(f"   Using: New LangGraph Implementation")
    print(f"{'='*60}\n")
    
    # Update progress: in_progress
    progress = {
        "symbol": symbol,
        "status": "in_progress",
        "max_rounds": max_rounds,
        "current_round": 0,
        "started_at": started_at,
        "updated_at": datetime.utcnow().isoformat(),
    }
    save_debate_progress(symbol, progress)
    
    try:
        # Create config
        config = get_config()
        
        # Create debate instance with use_dummy parameter
        debate = BullBearDebate(config, use_dummy=use_dummy)
        
        # Run the debate with streaming to track progress
        final_state = None
        current_round = 0
        
        for event in debate.stream(symbol, max_rounds, room_id):
            node_name = list(event.keys())[0]
            state = event[node_name]
            
            # Update progress based on node
            if "current_round" in state:
                current_round = state["current_round"]
            
            # Count debate points from unified debate_points list
            debate_pts = state.get("debate_points", [])
            bull_points = len([p for p in debate_pts if p.get("party") == "bull"])
            bear_points = len([p for p in debate_pts if p.get("party") == "bear"])
            
            progress = {
                "symbol": symbol,
                "status": "in_progress",
                "max_rounds": max_rounds,
                "current_round": current_round,
                "total_points": bull_points + bear_points,
                "bull_points": bull_points,
                "bear_points": bear_points,
                "last_node": node_name,
                "started_at": started_at,
                "updated_at": datetime.utcnow().isoformat(),
            }
            save_debate_progress(symbol, progress)
            
            final_state = state
        
        if final_state is None:
            raise RuntimeError("Debate produced no final state")
        
        # Count points from unified debate_points list
        all_debate_points = final_state.get("debate_points", [])
        final_bull_count = len([p for p in all_debate_points if p.get("party") == "bull"])
        final_bear_count = len([p for p in all_debate_points if p.get("party") == "bear"])
        
        print(f"\n✅ Debate completed!")
        print(f"   Bull points: {final_bull_count}")
        print(f"   Bear points: {final_bear_count}")
        print(f"   Rounds: {final_state.get('round_number', 0)}")
        
        # Extract results
        facilitator_report = final_state.get("facilitator_report", "")
        recommendation = final_state.get("recommendation", "HOLD")
        conclusion_reason = final_state.get("conclusion_reason", "max_rounds")
        
        # Get debate points from unified list
        all_points = final_state.get("debate_points", [])
        bull_points_list = [p for p in all_points if p.get("party") == "bull"]
        bear_points_list = [p for p in all_points if p.get("party") == "bear"]
        
        # Format debate points as dicts for JSON
        debate_points = []
        for p in bull_points_list:
            if hasattr(p, "__dict__"):
                debate_points.append({
                    "party": "bull",
                    "claim": p.claim if hasattr(p, "claim") else str(p),
                    "evidence": p.evidence if hasattr(p, "evidence") else "",
                    "round": p.round_number if hasattr(p, "round_number") else 0,
                })
            else:
                debate_points.append({"party": "bull", "claim": str(p)})
        
        for p in bear_points_list:
            if hasattr(p, "__dict__"):
                debate_points.append({
                    "party": "bear",
                    "claim": p.claim if hasattr(p, "claim") else str(p),
                    "evidence": p.evidence if hasattr(p, "evidence") else "",
                    "round": p.round_number if hasattr(p, "round_number") else 0,
                })
            else:
                debate_points.append({"party": "bear", "claim": str(p)})
        
        # Save facilitator report to Redis
        report_path = None
        if facilitator_report:
            print(f"\n💾 Saving facilitator report...")
            report_path = save_facilitator_report(symbol, facilitator_report)
        
        # Save debate points to Redis
        if debate_points:
            save_debate_points_to_redis(symbol, debate_points)
        
        # Final completed status
        final_progress = {
            "symbol": symbol,
            "status": "completed",
            "max_rounds": max_rounds,
            "current_round": final_state.get("current_round", 0),
            "total_points": len(debate_points),
            "recommendation": recommendation,
            "conclusion_reason": conclusion_reason,
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
        }
        save_debate_progress(symbol, final_progress)
        
        # Clear current debate
        _current_debate = None
        
        print(f"\n{'='*60}")
        print(f"✅ Complete! Facilitator report ready for {symbol}")
        print(f"   Recommendation: {recommendation}")
        print(f"   Conclusion: {conclusion_reason}")
        print(f"{'='*60}\n")
        
        return {
            "status": "success",
            "symbol": symbol,
            "rounds_completed": final_state.get("current_round", 0),
            "max_rounds": max_rounds,
            "total_exchanges": len(debate_points),
            "recommendation": recommendation,
            "conclusion_reason": conclusion_reason,
            "facilitator_report": facilitator_report,
            "report_path": report_path,
            "debate_points": debate_points,
        }
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"\n❌ Debate failed: {error_msg}")
        traceback.print_exc()
        
        # Save error state
        error_progress = {
            "symbol": symbol,
            "status": "error",
            "error": error_msg,
            "started_at": started_at,
            "updated_at": datetime.utcnow().isoformat(),
        }
        save_debate_progress(symbol, error_progress)
        
        # Clear current debate
        _current_debate = None
        
        return {
            "status": "error",
            "symbol": symbol,
            "error": error_msg,
        }


# Backward compatibility exports
def extract_recommendation(report: str) -> str:
    """Extract BUY/HOLD/SELL recommendation from report."""
    report_upper = report.upper()
    
    if "STRONG BUY" in report_upper:
        return "STRONG BUY"
    elif "STRONG SELL" in report_upper:
        return "STRONG SELL"
    elif "BUY" in report_upper and "SELL" not in report_upper:
        return "BUY"
    elif "SELL" in report_upper and "BUY" not in report_upper:
        return "SELL"
    elif "HOLD" in report_upper:
        return "HOLD"
    else:
        return "HOLD"


if __name__ == "__main__":
    # Test run
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Bull-Bear Debate")
    parser.add_argument("symbol", type=str, help="Stock symbol (e.g., AAPL)")
    parser.add_argument("--rounds", type=int, default=5, help="Max rounds (default: 5)")
    parser.add_argument("--dummy", action="store_true", help="Use dummy data")
    
    args = parser.parse_args()
    
    result = run_debate_and_generate_report(
        args.symbol,
        max_rounds=args.rounds,
        use_dummy=args.dummy,
    )
    
    print(f"\nResult: {result['status']}")
    if result["status"] == "success":
        print(f"Recommendation: {result['recommendation']}")
        print(f"Conclusion: {result['conclusion_reason']}")
