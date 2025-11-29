"""Orchestrator API Router."""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.orchestrator_agent import run_orchestrator

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


class QueryRequest(BaseModel):
    query: str
    symbol: Optional[str] = "AAPL"


class QueryResponse(BaseModel):
    query: str
    symbol: str
    answer: str
    timestamp: str


@router.post("/query", response_model=QueryResponse)
async def orchestrator_query(request: QueryRequest):
    """
    Smart query agent with automatic context gathering.
    
    Flow:
    1. Fetches reports from Redis
    2. Judges if RAG/fundamental context needed
    3. Judges if web search needed
    4. Generates comprehensive answer
    """
    try:
        answer = run_orchestrator(request.query, request.symbol)
        return QueryResponse(
            query=request.query,
            symbol=request.symbol.upper(),
            answer=answer,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
