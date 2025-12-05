"""
Pathway Unified API Server
==========================
Serves AI-generated reports and real-time sentiment from Redis cache.

Architecture:
- Phase 1 (Fast): Real-time sentiment scores from sentiment_clustering.py
- Phase 2 (Slow): LLM-generated reports from sentiment_reports.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from event_publisher import publish_agent_status  # Ensure import after edits

sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client, list_symbols as redis_list_symbols

# Try relative imports first (when run as module), fall back to absolute imports
try:
    from .historical_analysis_api import router as historical_router
    from .rag_api import router as rag_router
    from .bullbear_api import router as bullbear_router
    from .report_fetch_api import router as report_router
    from .sentiment_api import router as sentiment_router
    from .news_api import router as news_router
    from .drift_api import router as drift_router
    from .backtesting_api import router as backtesting_router, initialize_embeddings
    from .workflow_api import router as workflow_router
    from .strategist_api import router as strategist_router
except ImportError:
    from api.historical_analysis_api import router as historical_router
    from api.rag_api import router as rag_router
    from api.bullbear_api import router as bullbear_router
    from api.report_fetch_api import router as report_router
    from api.sentiment_api import router as sentiment_router
    from api.news_api import router as news_router
    from api.drift_api import router as drift_router
    from api.backtesting_api import router as backtesting_router, initialize_embeddings
    from api.workflow_api import router as workflow_router
    from api.strategist_api import router as strategist_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await initialize_embeddings()
    yield
    # Shutdown (nothing to do)

app = FastAPI(
    title="Pathway Unified API",
    version="8.0.0",
    description="Unified API for Reports, RAG, Backtesting, Bull-Bear Debate, and Strategist Agent",
    lifespan=lifespan,
)

# Ensure required directories exist at startup
REQUIRED_DIRS = [
    "/app/reports/fundamental",
    "/app/reports/market", 
    "/app/reports/news",
    "/app/reports/sentiment",
    "/app/reports/sentiment/clusters",
    "/app/reports/facilitator",
    "/app/reports/debate",
    "/app/pathway_state",
    "/app/knowledge_base",
]
for dir_path in REQUIRED_DIRS:
    os.makedirs(dir_path, exist_ok=True)
print(f"📁 Ensured {len(REQUIRED_DIRS)} required directories exist")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(historical_router, tags=["Historical Analysis"])
app.include_router(rag_router, tags=["RAG"])
app.include_router(bullbear_router, tags=["Bull-Bear Debate"])
app.include_router(report_router, tags=["Reports"])
app.include_router(sentiment_router, tags=["Sentiment"])
app.include_router(news_router, tags=["News"])
app.include_router(drift_router, tags=["Drift Detection"])
app.include_router(backtesting_router, tags=["Backtesting"])
app.include_router(workflow_router, tags=["Workflow"])
app.include_router(strategist_router)  # Tags defined in router


# =============================================================================
# CORE ENDPOINTS
# =============================================================================
@app.get("/")
async def root():
    return {
        "message": "Pathway Unified API",
        "version": "8.0.0",
        "architecture": "Unified Server for Reports, RAG, Backtesting, Bull-Bear Debate, Drift Detection, and Strategist Agent",
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
            "# Drift Detection": "---",
            "GET /drift/health": "Drift detector health check",
            "GET /drift/status": "Drift detector status",
            "GET /drift/alerts": "Get all drift alerts",
            "GET /drift/alerts/latest": "Get latest N drift alerts",
            "GET /drift/alerts/{symbol}": "Get drift alerts for symbol",
            "GET /drift/report": "Get drift detection report",
            "GET /drift/symbols": "List symbols with drift alerts",
            "GET /drift/stats": "Get drift detection statistics",
            "POST /drift/analyze": "Analyze historical data for drift",
            "POST /drift/reset": "Reset drift detection state",
            "# Strategist Agent (LangGraph + Mem0)": "---",
            "GET /strategist/status": "Check if Strategist agent is ready",
            "POST /strategist/chat": "Send message and get response",
            "POST /strategist/chat/stream": "SSE streaming chat response",
            "POST /strategist/new": "Start new conversation (preserves memories)",
            "GET /strategist/memory/{user_id}": "Get user's stored memories",
            "DELETE /strategist/memory/{user_id}": "Clear user memories",
            "GET /strategist/threads/{user_id}": "Get current thread info",
            "Clusters": {
                "/sentiment/clusters/{symbol}": "Sentiment clusters with overall score",
                "/news/clusters/{symbol}": "News story clusters",
            },
        }
    }


@app.get("/health")
async def health():
    client = get_redis_client()
    symbols = redis_list_symbols(client)
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "cached_symbols": symbols,
        "symbol_count": len(symbols)
    }


@app.get("/symbols")
async def list_symbols():
    client = get_redis_client()
    symbols = redis_list_symbols(client)
    return {"symbols": symbols, "count": len(symbols)}


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Pathway API Server")
    print("⚡ Phase 1: /sentiment/score, /sentiment/clusters (fast)")
    print("📝 Phase 2: /reports (LLM-generated)")
    uvicorn.run(app, host="0.0.0.0", port=8000)