"""
Pathway Unified API Server
==========================
Serves AI-generated reports and real-time sentiment from Redis cache.

Architecture:
- Phase 1 (Fast): Real-time sentiment scores from sentiment_clustering.py
- Phase 2 (Slow): LLM-generated reports from sentiment_reports.py
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client, get_reports_for_symbol, list_symbols as redis_list_symbols
from .historical_analysis_api import router as historical_router
from .rag_api import router as rag_router
from .bullbear_api import router as bullbear_router
from .orchestrator_api import router as orchestrator_router
from .workflow_api import router as workflow_router

# =============================================================================
# CONFIG
# =============================================================================
REPORT_TYPES = ["fundamental", "market", "news", "sentiment", "facilitator"]

app = FastAPI(title="Pathway Unified API", version="8.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Include routers
app.include_router(historical_router, tags=["Historical Analysis"])
app.include_router(rag_router, tags=["RAG"])
app.include_router(bullbear_router, tags=["Bull-Bear Debate"])
app.include_router(orchestrator_router, tags=["Orchestrator"])
app.include_router(workflow_router, tags=["Workflow"])


# =============================================================================
# MODELS
# =============================================================================
class ReportsResponse(BaseModel):
    symbol: str
    fundamental_report: Optional[str] = None
    market_report: Optional[str] = None
    news_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    facilitator_report: Optional[str] = None
    timestamp: str
    status: str


class SentimentClusterItem(BaseModel):
    cluster_id: int
    summary: str
    avg_sentiment: float
    count: int


class SentimentClustersResponse(BaseModel):
    symbol: str
    overall_sentiment: float
    cluster_count: int
    total_posts: int
    clusters: List[SentimentClusterItem]
    timestamp: str


class NewsArticle(BaseModel):
    title: str
    source: str


class NewsStory(BaseModel):
    headline: str
    articles: List[NewsArticle]
    links: List[str]


class NewsResponse(BaseModel):
    symbol: str
    stories: List[NewsStory]
    timestamp: str


# =============================================================================
# CORE ENDPOINTS
# =============================================================================
@app.get("/")
async def root():
    return {
        "message": "Pathway Unified API",
        "version": "8.0.0",
        "endpoints": {
            "📝 Reports": {
                "/reports/{symbol}": "All reports for symbol",
                "/reports/{symbol}/{type}": "Specific report type (fundamental, market, news, sentiment)",
            },
            "📊 Clusters": {
                "/sentiment/clusters/{symbol}": "Sentiment clusters with overall score",
                "/news/clusters/{symbol}": "News story clusters",
            },
            "🔧 Other": {
                "/symbols": "List tracked symbols",
                "/health": "Health check",
            }
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
# REPORTS API (Phase 2)
# =============================================================================
@app.get("/reports/{symbol}", response_model=ReportsResponse)
async def get_all_reports(symbol: str):
    """Get all cached reports for a symbol."""
    client = get_redis_client()
    symbol = symbol.upper()
    reports = get_reports_for_symbol(symbol, client)
    
    if not reports:
        raise HTTPException(status_code=404, detail=f"No reports found for {symbol}")
    
    return ReportsResponse(
        symbol=symbol,
        fundamental_report=reports.get("fundamental", {}).get("content"),
        market_report=reports.get("market", {}).get("content"),
        news_report=reports.get("news", {}).get("content"),
        sentiment_report=reports.get("sentiment", {}).get("content"),
        facilitator_report=reports.get("facilitator", {}).get("content"),
        timestamp=datetime.utcnow().isoformat(),
        status="success",
    )


@app.get("/reports/{symbol}/{report_type}")
async def get_specific_report(symbol: str, report_type: str):
    """Get a specific report type for a symbol."""
    symbol = symbol.upper()
    report_type = report_type.lower()
    
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of {REPORT_TYPES}")
    
    client = get_redis_client()
    reports = get_reports_for_symbol(symbol, client)
    
    if report_type not in reports:
        raise HTTPException(status_code=404, detail=f"No {report_type} report for {symbol}")
    
    entry = reports[report_type]
    return {
        "symbol": symbol,
        "report_type": report_type,
        "content": entry.get("content"),
        "last_updated": entry.get("last_updated"),
    }


# =============================================================================
# SENTIMENT CLUSTERS API
# =============================================================================
def _get_sentiment_data(symbol: str) -> dict:
    """Get sentiment cluster data from Redis."""
    client = get_redis_client()
    
    # Try sentiment_clusters key
    data = client.get(f"sentiment_clusters:{symbol}")
    if data:
        parsed = json.loads(data)
        if 'clusters_json' in parsed:
            return json.loads(parsed['clusters_json'])
        return parsed
    
    return {}


@app.get("/sentiment/clusters/{symbol}", response_model=SentimentClustersResponse)
async def get_sentiment_clusters(symbol: str):
    """Get sentiment clusters with overall score for a symbol."""
    symbol = symbol.upper()
    data = _get_sentiment_data(symbol)
    
    clusters = [
        SentimentClusterItem(
            cluster_id=c.get('cluster_id', 0),
            summary=c.get('summary', '')[:200],
            avg_sentiment=c.get('avg_sentiment', 0.0),
            count=c.get('count', 0)
        )
        for c in data.get('clusters', [])
    ]
    
    return SentimentClustersResponse(
        symbol=symbol,
        overall_sentiment=data.get('overall_sentiment', 0.0),
        cluster_count=data.get('cluster_count', 0),
        total_posts=data.get('total_posts', 0),
        clusters=clusters,
        timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat())
    )


# =============================================================================
# NEWS CLUSTERS API
# =============================================================================
def _get_news_clusters(symbol: str) -> list:
    """Get news clusters from Redis."""
    client = get_redis_client()
    
    data = client.get(f"news_clusters:{symbol}")
    if data:
        try:
            return json.loads(data)
        except:
            pass
    return []


@app.get("/news/clusters/{symbol}", response_model=NewsResponse)
async def get_news_clusters(symbol: str):
    """Get news story clusters for a symbol."""
    symbol = symbol.upper()
    clusters = _get_news_clusters(symbol)
    
    stories = [
        NewsStory(
            headline=c.get('headline', 'Story'),
            articles=[NewsArticle(title=a.get('title', ''), source=a.get('source', '')) for a in c.get('articles', [])[:10]],
            links=c.get('links', [])
        )
        for c in clusters
    ]
    
    return NewsResponse(
        symbol=symbol,
        stories=stories,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Pathway API Server")
    print("⚡ Phase 1: /sentiment/score, /sentiment/clusters (fast)")
    print("📝 Phase 2: /reports (LLM-generated)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
