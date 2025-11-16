"""
FastAPI server exposing cached AI reports stored in Redis.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent directory to path to import redis_cache
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import (
    get_redis_client,
    get_reports_for_symbol,
    list_symbols as redis_list_symbols,
)

REPORT_TYPES = ["fundamental", "market", "news", "sentiment"]

app = FastAPI(
    title="Pathway Live Reports API (Redis Cache)",
    version="5.0.0",
    description="FastAPI serves AI reports directly from the Redis cache populated by Pathway",
)


class ReportsResponse(BaseModel):
    symbol: str
    fundamental_report: Optional[str] = None
    market_report: Optional[str] = None
    news_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    timestamp: str
    status: str


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
        "message": "Pathway Live Reports API (Redis Cache)",
        "version": "5.0.0",
        "architecture": "Pathway streams reports into Redis; FastAPI reads from Redis on demand",
        "endpoints": {
            "GET /reports/{symbol}": "Get all cached reports for a stock symbol",
            "GET /reports/{symbol}/{report_type}": "Get a specific report",
            "GET /clusters": "Get all cluster visualization data (for frontend graphs)",
            "GET /clusters/{symbol}": "Get cluster data for a specific symbol",
            "GET /symbols": "List all symbols with cached reports",
            "GET /health": "Health check endpoint",
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


@app.get("/reports/{symbol}", response_model=ReportsResponse)
async def get_all_reports(symbol: str) -> ReportsResponse:
    client = get_redis_client()
    normalized_symbol = symbol.upper()

    print(f"\n{'=' * 60}")
    print(f"📥 Request for all reports: {normalized_symbol}")
    print(f"{'=' * 60}")

    reports = get_reports_for_symbol(normalized_symbol, client)
    if not reports:
        print(f"❌ No reports found for {normalized_symbol}\n")
        raise HTTPException(
            status_code=404,
            detail=f"No cached reports found for symbol {normalized_symbol}",
        )

    fundamental_report = reports.get("fundamental", {}).get("content")
    market_report = reports.get("market", {}).get("content")
    news_report = reports.get("news", {}).get("content")
    sentiment_report = reports.get("sentiment", {}).get("content")

    print(f"\n📊 Cached results for {normalized_symbol}:")
    print(f"  Fundamental: {'✅' if fundamental_report else '❌'}")
    print(f"  Market: {'✅' if market_report else '❌'}")
    print(f"  News: {'✅' if news_report else '❌'}")
    print(f"  Sentiment: {'✅' if sentiment_report else '❌'}")
    print(f"✅ Returning cached response for {normalized_symbol}\n")

    return ReportsResponse(
        symbol=normalized_symbol,
        fundamental_report=fundamental_report,
        market_report=market_report,
        news_report=news_report,
        sentiment_report=sentiment_report,
        timestamp=datetime.utcnow().isoformat(),
        status="success",
    )


@app.get("/reports/{symbol}/{report_type}")
async def get_specific_report(symbol: str, report_type: str) -> dict:
    normalized_symbol = symbol.upper()
    normalized_report_type = report_type.lower()

    if normalized_report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type '{report_type}'. Must be one of {REPORT_TYPES}",
        )

    client = get_redis_client()
    reports = get_reports_for_symbol(normalized_symbol, client)

    if normalized_report_type not in reports:
        raise HTTPException(
            status_code=404,
            detail=f"No cached {normalized_report_type} report found for {normalized_symbol}",
        )

    entry = reports[normalized_report_type]

    return {
        "symbol": normalized_symbol,
        "report_type": normalized_report_type,
        "content": entry.get("content"),
        "last_updated": entry.get("last_updated"),
        "received_at": entry.get("received_at"),
        "processing_time": entry.get("processing_time"),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# CLUSTER VISUALIZATION ENDPOINTS (for frontend graph building)
# ============================================================================

@app.get("/clusters", response_model=None)
def get_all_clusters():
    """
    Get all cluster visualization data from Redis cache.
    Returns clusters grouped by symbol with aggregated sentiment metrics.
    
    This endpoint provides raw cluster data for frontend visualization.
    Frontend developers can use this to build their own graphs and dashboards.
    
    Returns:
        - clusters: List of all cluster objects
        - market_sentiment_score: Weighted average sentiment across all posts
        - total_posts: Total number of posts across all clusters
        - total_clusters: Total number of active clusters
        - by_symbol: Clusters grouped by stock symbol with aggregated metrics
    """
    client = get_redis_client()
    
    # Get all clusters from the aggregated hash
    all_clusters_key = "clusters:all"
    clusters_data = client.hgetall(all_clusters_key)
    
    if not clusters_data:
        return {
            "clusters": [],
            "market_sentiment_score": 0.0,
            "total_posts": 0,
            "total_clusters": 0,
            "by_symbol": {},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Parse cluster data
    clusters = []
    by_symbol = {}
    total_posts = 0
    all_sentiments = []
    all_counts = []
    
    for cluster_key, cluster_json in clusters_data.items():
        try:
            cluster = json.loads(cluster_json)
            clusters.append(cluster)
            
            symbol = cluster.get("symbol", "UNKNOWN")
            if symbol not in by_symbol:
                by_symbol[symbol] = {"clusters": [], "sentiment": 0.0, "posts": 0}
            
            by_symbol[symbol]["clusters"].append(cluster)
            by_symbol[symbol]["posts"] += cluster.get("count", 0)
            
            total_posts += cluster.get("count", 0)
            all_sentiments.append(cluster.get("avg_sentiment", 0.0))
            all_counts.append(cluster.get("count", 0))
        except:
            continue
    
    # Calculate market sentiment score (weighted average)
    market_sentiment_score = 0.0
    if all_counts and sum(all_counts) > 0:
        market_sentiment_score = sum(
            s * c for s, c in zip(all_sentiments, all_counts)
        ) / sum(all_counts)
    
    # Calculate per-symbol sentiment
    for symbol, data in by_symbol.items():
        if data["posts"] > 0:
            data["sentiment"] = sum(
                c["avg_sentiment"] * c["count"] for c in data["clusters"]
            ) / data["posts"]
    
    return {
        "clusters": clusters,
        "market_sentiment_score": market_sentiment_score,
        "total_posts": total_posts,
        "total_clusters": len(clusters),
        "by_symbol": by_symbol,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/clusters/{symbol}", response_model=None)
def get_symbol_clusters(symbol: str):
    """
    Get cluster data for a specific symbol from Redis cache.
    
    This endpoint provides cluster data for a single stock symbol,
    useful for building symbol-specific visualizations.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'TSLA')
    
    Returns:
        - symbol: The stock ticker
        - clusters: List of cluster objects for this symbol
        - sentiment: Weighted average sentiment for the symbol
        - posts: Total posts for this symbol
    """
    client = get_redis_client()
    symbol_upper = symbol.upper()
    
    # Get all clusters for this symbol
    pattern = f"clusters:{symbol_upper}:*"
    cluster_keys = client.keys(pattern)
    
    if not cluster_keys:
        return {
            "symbol": symbol_upper,
            "clusters": [],
            "sentiment": 0.0,
            "posts": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    clusters = []
    total_posts = 0
    weighted_sentiment_sum = 0.0
    
    for key in cluster_keys:
        cluster_json = client.get(key)
        if cluster_json:
            try:
                cluster = json.loads(cluster_json)
                clusters.append(cluster)
                count = cluster.get("count", 0)
                total_posts += count
                weighted_sentiment_sum += cluster.get("avg_sentiment", 0.0) * count
            except:
                continue
    
    symbol_sentiment = weighted_sentiment_sum / total_posts if total_posts > 0 else 0.0
    
    return {
        "symbol": symbol_upper,
        "clusters": clusters,
        "sentiment": symbol_sentiment,
        "posts": total_posts,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    import json  # Add json import

    print("🚀 Starting FastAPI server (Redis Cache)")
    print("📡 Serving AI reports directly from Redis")
    uvicorn.run(app, host="0.0.0.0", port=8000)