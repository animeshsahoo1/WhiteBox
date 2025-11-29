"""
Bull-Bear Debate API Router
Provides POST /debate/{symbol} endpoint for running debates.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bullbear.debate_runner import run_debate_and_generate_report

router = APIRouter(prefix="/debate", tags=["Bull-Bear Debate"])


class DebateRequest(BaseModel):
    """Request body for starting a debate."""
    max_rounds: Optional[int] = 2


class DebateResponse(BaseModel):
    """Response from debate endpoint."""
    status: str
    symbol: str
    rounds_completed: int
    total_exchanges: int
    recommendation: str
    facilitator_report: str
    timestamp: str


@router.post("/{symbol}", response_model=DebateResponse)
async def run_debate(symbol: str, request: DebateRequest = DebateRequest()):
    """
    Run bull-bear debate and generate facilitator report.
    
    This endpoint:
    1. Fetches the 4 reports (market, sentiment, news, fundamental) from Redis
    2. Runs a LangGraph debate between Bull and Bear analysts
    3. Generates a facilitator report with BUY/HOLD/SELL recommendation
    4. Saves the report to Redis and file system
    5. Returns the complete result
    
    The facilitator report is then available via:
    - GET /reports/{symbol} (includes facilitator_report field)
    - GET /reports/{symbol}/facilitator
    
    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
        request: Optional body with max_rounds (default 2)
        
    Returns:
        DebateResponse with facilitator report and recommendation
    """
    symbol = symbol.upper()
    
    # Validate max_rounds
    max_rounds = request.max_rounds
    if max_rounds < 1:
        max_rounds = 1
    elif max_rounds > 5:
        max_rounds = 5  # Cap at 5 to prevent very long debates
    
    try:
        result = run_debate_and_generate_report(
            symbol=symbol,
            max_rounds=max_rounds
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
    Check if a facilitator report exists for a symbol.
    
    This is a lightweight endpoint to check if a debate has been run
    without fetching the full report.
    """
    symbol = symbol.upper()
    
    try:
        from redis_cache import get_redis_client, _build_symbol_key
        import json
        
        client = get_redis_client()
        symbol_key = _build_symbol_key(symbol)
        
        facilitator_data = client.hget(symbol_key, "facilitator")
        
        if facilitator_data:
            entry = json.loads(facilitator_data)
            return {
                "symbol": symbol,
                "has_facilitator_report": True,
                "last_updated": entry.get("last_updated"),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "symbol": symbol,
                "has_facilitator_report": False,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking status: {str(e)}"
        )
