"""
News API Router
Handles news story clusters from Redis.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client


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
    """Get news clusters from Redis."""
    client = get_redis_client()
    
    data = client.get(f"news_clusters:{symbol}")
    if data:
        try:
            return json.loads(data)
        except:
            pass
    return []


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
