"""
Bull-Bear Debate API Router
Provides POST /debate/{symbol} endpoint for running debates with live status.

Uses the new LangGraph-based implementation with mem0 memory persistence.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bullbear.debate_runner import run_debate_and_generate_report, get_debate_progress
from redis_cache import get_redis_client, _build_symbol_key


# ============================================================
# FACILITATOR STATUS FUNCTIONS (Minimal Implementation)
# ============================================================

# Track active streams per symbol
_active_streams: Dict[str, bool] = {}


def get_facilitator_status(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get facilitator status from Redis or file.
    Returns None if no facilitator report exists.
    """
    symbol = symbol.upper()
    
    # Try Redis first
    try:
        client = get_redis_client()
        symbol_key = _build_symbol_key(symbol)
        facilitator_data = client.hget(symbol_key, "facilitator")
        
        if facilitator_data:
            entry = json.loads(facilitator_data)
            return {
                "status": "completed",
                "round": entry.get("round", 0),
                "report": entry.get("content", ""),
                "recommendation": _extract_recommendation(entry.get("content", "")),
                "updated_at": entry.get("last_updated"),
                "source": "redis",
            }
    except Exception:
        pass
    
    # Try file fallback
    reports_dir = Path(__file__).parent.parent / "reports" / "facilitator" / symbol
    report_path = reports_dir / "facilitator_report.md"
    
    if report_path.exists():
        try:
            content = report_path.read_text(encoding="utf-8")
            return {
                "status": "completed",
                "round": 0,
                "report": content,
                "recommendation": _extract_recommendation(content),
                "updated_at": datetime.fromtimestamp(report_path.stat().st_mtime).isoformat(),
                "source": "file",
            }
        except Exception:
            pass
    
    return None


def is_stream_active(symbol: str) -> bool:
    """Check if facilitator stream is active for a symbol."""
    return _active_streams.get(symbol.upper(), False)


def _extract_recommendation(report: str) -> Optional[str]:
    """Extract BUY/HOLD/SELL recommendation from facilitator report."""
    if not report:
        return None
    
    report_upper = report.upper()
    if "STRONG BUY" in report_upper or "RECOMMENDATION: BUY" in report_upper:
        return "BUY"
    elif "STRONG SELL" in report_upper or "RECOMMENDATION: SELL" in report_upper:
        return "SELL"
    elif "BUY" in report_upper and "SELL" not in report_upper:
        return "BUY"
    elif "SELL" in report_upper and "BUY" not in report_upper:
        return "SELL"
    return "HOLD"


router = APIRouter(prefix="/debate", tags=["Bull-Bear Debate"])


class DebateRequest(BaseModel):
    """Request body for starting a debate."""
    max_rounds: Optional[int] = 5  # Default to 5 rounds (new implementation)
    background: Optional[bool] = True  # Run in background by default
    use_dummy: Optional[bool] = False  # Use dummy data for testing


class DebateResponse(BaseModel):
    """Response from debate endpoint."""
    status: str
    symbol: str
    rounds_completed: int
    total_exchanges: int
    recommendation: str
    conclusion_reason: str
    facilitator_report: str
    timestamp: str


class DebateStartResponse(BaseModel):
    """Response when debate starts in background."""
    status: str
    symbol: str
    max_rounds: int
    message: str


@router.post("/{symbol}")
async def run_debate(symbol: str, request: DebateRequest = DebateRequest()):
    """
    Start bull-bear debate.
    
    If background=True (default): Returns immediately, poll /debate/{symbol}/status for progress.
    If background=False: Blocks until complete, returns full result.
    """
    symbol = symbol.upper()
    
    # Limit rounds to 1-10 (new implementation supports more)
    max_rounds = max(1, min(request.max_rounds or 5, 10))
    
    try:
        result = run_debate_and_generate_report(
            symbol=symbol,
            max_rounds=max_rounds,
            background=request.background,
            use_dummy=request.use_dummy,
        )
        
        # Check if busy
        if result.get("status") == "busy":
            raise HTTPException(
                status_code=409,  # Conflict
                detail=result.get("error", "A debate is already in progress")
            )
        
        if request.background:
            return DebateStartResponse(
                status="started",
                symbol=symbol,
                max_rounds=max_rounds,
                message=f"Debate started. Poll GET /debate/{symbol}/status for live progress."
            )
        
        return DebateResponse(
            status=result["status"],
            symbol=result["symbol"],
            rounds_completed=result.get("rounds_completed", 0),
            total_exchanges=result.get("total_exchanges", 0),
            recommendation=result.get("recommendation", "HOLD"),
            conclusion_reason=result.get("conclusion_reason", "unknown"),
            facilitator_report=result.get("facilitator_report", ""),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except ValueError as e:
        # Missing reports or invalid symbol
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except RuntimeError as e:
        # Debate execution failed
        raise HTTPException(
            status_code=500,
            detail=f"Debate execution failed: {str(e)}"
        )
    except Exception as e:
        # Unexpected error
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/{symbol}/status")
async def get_debate_status(symbol: str):
    """
    Get live debate progress.
    
    Returns the current state including:
    - status: "started", "in_progress", "completed", "error", or "not_found"
    - current_round: Which round we're on
    - total_points: Total debate points (bull + bear)
    - recommendation: Final recommendation (when completed)
    - conclusion_reason: Why debate ended (consensus/exhaustion/max_rounds/early_end)
    """
    symbol = symbol.upper()
    
    try:
        progress = get_debate_progress(symbol)
        
        if progress:
            return {
                "symbol": symbol,
                "status": progress.get("status", "unknown"),
                "max_rounds": progress.get("max_rounds"),
                "current_round": progress.get("current_round"),
                "total_points": progress.get("total_points", 0),
                "bull_points": progress.get("bull_points", 0),
                "bear_points": progress.get("bear_points", 0),
                "last_node": progress.get("last_node"),
                "recommendation": progress.get("recommendation"),
                "conclusion_reason": progress.get("conclusion_reason"),
                "error": progress.get("error"),
                "started_at": progress.get("started_at"),
                "updated_at": progress.get("updated_at"),
                "completed_at": progress.get("completed_at"),
            }
        else:
            return {
                "symbol": symbol,
                "status": "not_found",
                "message": "No debate found. Start one with POST /debate/{symbol}"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking status: {str(e)}"
        )


# ============================================================
# FACILITATOR API
# ============================================================

@router.get("/facilitator/{symbol}/status")
async def get_facilitator_report_status(symbol: str):
    """
    Get current facilitator report status for a symbol.
    
    The facilitator auto-generates reports when bear_debate.md changes.
    This endpoint returns the latest facilitator report.
    
    Returns:
    - status: "watching", "processing", "completed", "error", "stopped", or "not_found"
    - report: The latest facilitator report (markdown)
    - recommendation: BUY/HOLD/SELL extracted from report
    - stream_active: Whether facilitator is still watching for changes
    """
    symbol = symbol.upper()
    
    try:
        status = get_facilitator_status(symbol)
        stream_active = is_stream_active(symbol)
        
        if status:
            return {
                "symbol": symbol,
                "status": status.get("status", "unknown"),
                "round": status.get("round", 0),
                "report": status.get("report", ""),
                "recommendation": status.get("recommendation"),
                "stream_active": stream_active,
                "updated_at": status.get("updated_at"),
                "source": status.get("source", "memory"),
            }
        else:
            return {
                "symbol": symbol,
                "status": "not_found",
                "round": 0,
                "report": "",
                "recommendation": None,
                "stream_active": stream_active,
                "message": "No facilitator report found. Start a debate with POST /debate/{symbol}"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking facilitator status: {str(e)}"
        )