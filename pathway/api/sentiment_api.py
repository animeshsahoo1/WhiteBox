"""Sentiment API Router
Handles sentiment clusters with overall scores from Redis.
Includes in-memory caching for high-frequency requests.
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Any

from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client

# In-memory cache for cluster data (TTL: 5 seconds)
_cluster_cache: Dict[str, Tuple[float, Any]] = {}
CACHE_TTL = 5.0  # seconds


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


router = APIRouter(prefix="/sentiment")


# =============================================================================
# CLUSTER VISUALIZATION ENDPOINTS (from sentiment_cluster_api)
# =============================================================================
# Cache for all-clusters endpoint (heavier query)
_all_clusters_cache: Tuple[float, Any] = (0.0, None)
ALL_CLUSTERS_TTL = 3.0  # seconds


@router.get("/clusters")
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
    global _all_clusters_cache
    now = time.time()
    
    # Check cache first
    cached_time, cached_data = _all_clusters_cache
    if cached_data is not None and now - cached_time < ALL_CLUSTERS_TTL:
        return cached_data
    
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
        except Exception:
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
    
    result = {
        "clusters": clusters,
        "market_sentiment_score": market_sentiment_score,
        "total_posts": total_posts,
        "total_clusters": len(clusters),
        "by_symbol": by_symbol,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Update cache
    _all_clusters_cache = (now, result)
    
    return result


# =============================================================================
# SENTIMENT SCORE ENDPOINTS
# =============================================================================
def _get_sentiment_data(symbol: str) -> dict:
    """Get sentiment cluster data from Redis with in-memory caching."""
    cache_key = f"sentiment:{symbol}"
    now = time.time()
    
    # Check cache first
    if cache_key in _cluster_cache:
        cached_time, cached_data = _cluster_cache[cache_key]
        if now - cached_time < CACHE_TTL:
            return cached_data
    
    # Fetch from Redis
    client = get_redis_client()
    data = client.get(f"sentiment_clusters:{symbol}")
    
    result = {}
    if data:
        parsed = json.loads(data)
        if 'clusters_json' in parsed:
            result = json.loads(parsed['clusters_json'])
        else:
            result = parsed
    
    # Update cache
    _cluster_cache[cache_key] = (now, result)
    
    # Prune old cache entries (keep last 100)
    if len(_cluster_cache) > 100:
        oldest_keys = sorted(_cluster_cache.keys(), key=lambda k: _cluster_cache[k][0])[:50]
        for k in oldest_keys:
            del _cluster_cache[k]
    
    return result


@router.get("/clusters/{symbol}", response_model=SentimentClustersResponse)
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
