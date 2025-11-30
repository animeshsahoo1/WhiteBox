"""Orchestrator API Router."""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.orchestrator_agent import run_orchestrator
from guardrails import guard_input, guard_output

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
    Smart query agent with automatic context gathering + guardrails.
    
    Flow:
    1. INPUT GUARDRAILS: Check for jailbreaks, off-topic, PII
    2. Fetches reports from Redis
    3. Judges if RAG/fundamental context needed
    4. Judges if web search needed
    5. Generates comprehensive answer
    6. OUTPUT GUARDRAILS: Add disclaimer, mask PII
    """
    try:
        # INPUT GUARDRAILS
        input_check = guard_input(request.query)
        if not input_check.allowed:
            return QueryResponse(
                query=request.query,
                symbol=request.symbol.upper(),
                answer=input_check.message,
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Use guarded input (may have PII masked)
        answer = run_orchestrator(input_check.message, request.symbol)
        
        # OUTPUT GUARDRAILS
        output_check = guard_output(answer)
        
        return QueryResponse(
            query=request.query,
            symbol=request.symbol.upper(),
            answer=output_check.message,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
