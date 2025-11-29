"""
Bull-Bear Debate API Router
Provides POST /debate/{symbol} endpoint for running debates with live status.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bullbear.debate_runner import run_debate_and_generate_report, get_debate_progress

router = APIRouter(prefix="/debate", tags=["Bull-Bear Debate"])


class DebateRequest(BaseModel):
    """Request body for starting a debate."""
    max_rounds: Optional[int] = 2
    background: Optional[bool] = True  # Run in background by default


class DebateResponse(BaseModel):
    """Response from debate endpoint."""
    status: str
    symbol: str
    rounds_completed: int
    total_exchanges: int
    recommendation: str
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
    
    max_rounds = max(1, min(request.max_rounds or 2, 5))
    
    try:
        result = run_debate_and_generate_report(
            symbol=symbol,
            max_rounds=max_rounds,
            background=request.background
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
            rounds_completed=result["rounds_completed"],
            total_exchanges=result["total_exchanges"],
            recommendation=result["recommendation"],
            facilitator_report=result["facilitator_report"],
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
    Get live debate progress with Bull/Bear conversation.
    
    Returns the current state including:
    - status: "started", "in_progress", "completed", "error", or "not_found"
    - bull_history: All Bull arguments so far
    - bear_history: All Bear arguments so far
    - current_round: Which round we're on
    - last_speaker: Who spoke last ("bull_researcher" or "bear_researcher")
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
                "total_exchanges": progress.get("total_exchanges", 0),
                "last_speaker": progress.get("last_speaker"),
                "bull_history": progress.get("bull_history", ""),
                "bear_history": progress.get("bear_history", ""),
                "current_response": progress.get("current_response", ""),
                "recommendation": progress.get("recommendation"),
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