"""News API Router
Handles news story clusters from Redis.
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

# In-memory cache for news data (TTL: 10 seconds - news updates less frequently)
_news_cache: Dict[str, Tuple[float, Any]] = {}
NEWS_CACHE_TTL = 10.0  # seconds


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


router = APIRouter(prefix="/news")


def _get_news_clusters(symbol: str) -> list:
    """Get news clusters from Redis with in-memory caching."""
    cache_key = f"news:{symbol}"
    now = time.time()
    
    # Check cache first
    if cache_key in _news_cache:
        cached_time, cached_data = _news_cache[cache_key]
        if now - cached_time < NEWS_CACHE_TTL:
            return cached_data
    
    # Fetch from Redis
    client = get_redis_client()
    result = []
    data = client.get(f"news_clusters:{symbol}")
    if data:
        try:
            result = json.loads(data)
        except:
            pass
    
    # Update cache
    _news_cache[cache_key] = (now, result)
    
    # Prune old cache entries (keep last 50)
    if len(_news_cache) > 50:
        oldest_keys = sorted(_news_cache.keys(), key=lambda k: _news_cache[k][0])[:25]
        for k in oldest_keys:
            del _news_cache[k]
    
    return result


@router.get("/clusters/{symbol}", response_model=NewsResponse)
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
