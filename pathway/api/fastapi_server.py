"""
FastAPI server exposing cached AI reports stored in Redis.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from event_publisher import publish_agent_status  # Ensure import after edits

# Add parent directory to path to import redis_cache
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import (
    get_redis_client,
    get_reports_for_symbol,
    list_symbols as redis_list_symbols,
)
from .historical_analysis_api import router as historical_router
from .rag_api import router as rag_router
from .bullbear_api import router as bullbear_router
from .report_fetch_api import router as report_router, REPORT_TYPES
from .sentiment_cluster_api import router as cluster_router

from .backtesting_api import router as backtesting_router
from .workflow_api import router as workflow_router
from .strategist_api import router as strategist_router


app = FastAPI(
    title="Pathway Unified API",
    version="8.0.0",
    description="Unified API for Reports, RAG, Backtesting, Bull-Bear Debate, and Strategist Agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(historical_router, tags=["Historical Analysis"])
app.include_router(rag_router, tags=["RAG"])
app.include_router(bullbear_router, tags=["Bull-Bear Debate"])
app.include_router(report_router, tags=["Reports"])
app.include_router(cluster_router, tags=["Clusters"])
app.include_router(backtesting_router, tags=["Backtesting"])
app.include_router(workflow_router, tags=["Workflow"])
app.include_router(strategist_router, tags=["Strategist Agent"])

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    cached_symbols: list[str]
    report_counts: Dict[str, int]


def _compute_report_counts() -> Dict[str, int]:
    client = get_redis_client()
    counts: Dict[str, int] = {report_type: 0 for report_type in REPORT_TYPES}
    
    # Add cluster count
    clusters_key = "clusters:all"
    cluster_count = client.hlen(clusters_key) if client.exists(clusters_key) else 0
    counts["clusters"] = cluster_count

    symbols = redis_list_symbols(client)
    for symbol in symbols:
        reports = get_reports_for_symbol(symbol, client)
        for report_type in REPORT_TYPES:
            if reports.get(report_type) and reports[report_type].get("content"):
                counts[report_type] += 1

    return counts


@app.get("/", response_model=dict)
async def root() -> dict:
    return {
        "message": "Pathway Unified API",
        "version": "8.0.0",
        "architecture": "Unified Server for Reports, RAG, Backtesting, Bull-Bear Debate, and Strategist Agent",
        "endpoints": {
            "GET /reports/{symbol}": "Get all cached reports (includes facilitator)",
            "GET /reports/{symbol}/{report_type}": "Get specific report",
            "GET /clusters": "Get cluster visualization data",
            "GET /clusters/{symbol}": "Get symbol clusters",
            "GET /symbols": "List symbols with cached reports",
            "GET /health": "Health check",
            "POST /analyze": "Historical Analysis",
            "POST /query": "RAG Query",
            "GET /backtesting/": "Backtesting service status",
            "GET /backtesting/metrics": "Get all strategy metrics (from Redis cache)",
            "GET /backtesting/metrics/{strategy}": "Get metrics for specific strategy",
            "GET /backtesting/strategies": "List all strategies",
            "GET /backtesting/strategies/{name}": "Get strategy code and metrics",
            "POST /backtesting/strategies": "Create strategy from natural language (LLM)",
            "DELETE /backtesting/strategies/{name}": "Delete a strategy",
            "POST /backtesting/strategies/search": "Semantic search strategies",
            "POST /debate/{symbol}": "Run bull-bear debate",
            "GET /debate/{symbol}/status": "Check facilitator report exists",
            "# Strategist Agent (LangGraph + Mem0)": "---",
            "GET /strategist/status": "Check if Strategist agent is ready",
            "POST /strategist/chat": "Send message and get response",
            "POST /strategist/chat/stream": "SSE streaming chat response",
            "POST /strategist/new": "Start new conversation (preserves memories)",
            "GET /strategist/memory/{user_id}": "Get user's stored memories",
            "DELETE /strategist/memory/{user_id}": "Clear user memories",
            "GET /strategist/threads/{user_id}": "Get current thread info"
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    client = get_redis_client()
    symbols = redis_list_symbols(client)
    report_counts = _compute_report_counts()

    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
        cached_symbols=symbols,
        report_counts=report_counts,
    )


@app.get("/symbols")
async def list_symbols() -> dict:
    client = get_redis_client()
    symbols = redis_list_symbols(client)

    return {
        "symbols": symbols,
        "count": len(symbols),
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    import json  # Add json import

    print("🚀 Starting FastAPI server (Redis Cache)")
    print("📡 Serving AI reports directly from Redis")
    uvicorn.run(app, host="0.0.0.0", port=8000)