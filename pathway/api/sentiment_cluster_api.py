"""
Sentiment Cluster API Router
Handles cluster visualization data and sentiment metrics from Redis.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client

router = APIRouter(prefix="/clusters")


@router.get("")
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


@router.get("/{symbol}")
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
