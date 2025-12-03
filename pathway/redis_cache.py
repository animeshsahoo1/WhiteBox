"""Utilities for sharing AI reports via Redis and PostgreSQL."""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional

import pathway as pw
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

REDIS_DEFAULT_HOST = "localhost"
REDIS_DEFAULT_PORT = 6379
REDIS_DEFAULT_DB = 0
REPORT_SYMBOL_SET_KEY = "reports:symbols"
REPORT_KEY_PREFIX = "reports"


def _build_symbol_key(symbol: str) -> str:
    return f"{REPORT_KEY_PREFIX}:{symbol}"


# =====================================================================
# POSTGRESQL CONNECTION
# =====================================================================

@lru_cache(maxsize=1)
def get_postgres_connection():
    """Return a PostgreSQL connection configured via DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("⚠️  DATABASE_URL not set - PostgreSQL saving disabled")
        return None
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        print("✅ PostgreSQL connection established")
        return conn
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return None


def save_report_to_postgres(symbol: str, report_type: str, entry: Dict[str, Any]) -> bool:
    """Save a report to the analyst_reports PostgreSQL table."""
    conn = get_postgres_connection()
    if not conn:
        return False
    
    try:
        # Generate unique ID: {symbol}_{report_type}_{timestamp}_{random}
        import uuid
        timestamp_str = entry.get("last_updated", datetime.utcnow().isoformat())
        # Clean timestamp for ID (remove special chars)
        timestamp_clean = timestamp_str.replace(":", "").replace("-", "").replace("T", "_").replace(".", "")[:15]
        # Add short UUID to ensure uniqueness even for same-second reports
        unique_suffix = str(uuid.uuid4())[:8]
        report_id = f"{symbol}_{report_type}_{timestamp_clean}_{unique_suffix}"
        
        # Parse timestamp for the timestamp column
        try:
            if isinstance(timestamp_str, str):
                report_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                report_timestamp = datetime.utcnow()
        except:
            report_timestamp = datetime.utcnow()
        
        # Prepare report body as JSON string
        report_body = json.dumps(entry)
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analyst_reports (id, symbol, report_type, timestamp, score, report_body, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (report_id, symbol, report_type, report_timestamp, None, report_body))
        
        print("=" * 60)
        print(f"✅ [POSTGRESQL] Report saved to analyst_reports table!")
        print(f"   📌 ID: {report_id}")
        print(f"   📈 Symbol: {symbol}")
        print(f"   📋 Report Type: {report_type}")
        print(f"   🕐 Timestamp: {report_timestamp}")
        print(f"   📦 Body Size: {len(report_body)} chars")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Failed to save to PostgreSQL: {e}")
        # Try to reconnect on next call
        get_postgres_connection.cache_clear()
        return False


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Return a cached Redis client configured via environment variables."""

    url = os.getenv("REDIS_URL")
    if url:
        print("############## Using REDIS_URL for Redis connection ################")
        return redis.Redis.from_url(url, decode_responses=True)
    
    host = os.getenv("REDIS_HOST", REDIS_DEFAULT_HOST)
    port = int(os.getenv("REDIS_PORT", str(REDIS_DEFAULT_PORT)))
    db = int(os.getenv("REDIS_DB", str(REDIS_DEFAULT_DB)))

    return redis.Redis(host=host, port=port, db=db, decode_responses=True)


def _to_serializable_timestamp(value: Any, fallback_time: int) -> str:
    if value is None:
        return str(fallback_time)

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive fallback
            return str(value)

    return str(value)


def _extract_report_content(row: Dict[str, Any]) -> Optional[str]:
    candidate = (
        row.get("report")
        or row.get("response")
        or row.get("llm_analysis")
        or row.get("content")
    )

    if candidate is None:
        return None

    if isinstance(candidate, str):
        return candidate

    if hasattr(candidate, "as_dict"):
        try:
            return json.dumps(candidate.as_dict(), indent=2)
        except Exception:
            return str(candidate)

    if hasattr(candidate, "as_list"):
        try:
            return json.dumps(candidate.as_list(), indent=2)
        except Exception:
            return str(candidate)

    return str(candidate)


class RedisReportObserver(pw.io.python.ConnectorObserver):
    """Pathway observer that writes report updates into Redis."""

    def __init__(self, report_type: str, ttl_seconds: Optional[int] = None):
        self.report_type = report_type
        self.ttl_seconds = ttl_seconds
        self.redis = get_redis_client()

    def on_change(self, key: Any, row: Dict[str, Any], time: int, is_addition: bool) -> None:
        symbol_raw = row.get("symbol")
        if not symbol_raw:
            return

        symbol = str(symbol_raw).upper()
        symbol_key = _build_symbol_key(symbol)

        if not is_addition:
            self.redis.hdel(symbol_key, self.report_type)
            if self.redis.hlen(symbol_key) == 0:
                self.redis.delete(symbol_key)
                self.redis.srem(REPORT_SYMBOL_SET_KEY, symbol)
            return

        content = _extract_report_content(row)
        if content is None:
            return

        last_updated = (
            row.get("last_updated")
            or row.get("window_end")
            or row.get("timestamp")
            or row.get("time")
            or time
        )

        entry = {
            "symbol": symbol,
            "report_type": self.report_type,
            "content": content,
            "last_updated": _to_serializable_timestamp(last_updated, time),
            "received_at": datetime.utcnow().isoformat(),
            "processing_time": int(time),
        }

        self.redis.hset(symbol_key, self.report_type, json.dumps(entry))
        self.redis.sadd(REPORT_SYMBOL_SET_KEY, symbol)

        if self.ttl_seconds:
            self.redis.expire(symbol_key, self.ttl_seconds)

    def on_time_end(self, time: int) -> None:  # pragma: no cover - optional hook
        pass

    def on_end(self) -> None:  # pragma: no cover - optional hook
        pass


_observer_cache: Dict[str, RedisReportObserver] = {}


class RedisImageObserver(pw.io.python.ConnectorObserver):
    """Pathway observer that writes indicator chart images into Redis."""
    
    IMAGES_KEY_PREFIX = "images:"
    IMAGES_INDEX_KEY = "images:index"
    
    def __init__(self, ttl_seconds: int = 3600):
        self.redis = get_redis_client()
        self.ttl_seconds = ttl_seconds
    
    def on_change(self, key: Any, row: Dict[str, Any], time: int, is_addition: bool) -> None:
        """Handle image data changes from Pathway stream."""
        symbol = row.get("symbol")
        if not symbol:
            return
        
        symbol = str(symbol).upper()
        timestamp = row.get("timestamp", datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
        
        image_key = f"{self.IMAGES_KEY_PREFIX}{symbol}:{timestamp}"
        
        if not is_addition:
            # Remove image from Redis
            self.redis.delete(image_key)
            self.redis.hdel(self.IMAGES_INDEX_KEY, image_key)
            return
        
        # Store image data
        image_data = {
            "symbol": symbol,
            "timestamp": timestamp,
            "key": image_key,
            "pattern_image": row.get("pattern_image", ""),
            "trend_image": row.get("trend_image", ""),
            "rsi_plot": row.get("rsi_plot", ""),
            "macd_plot": row.get("macd_plot", ""),
            "stochastic_plot": row.get("stochastic_plot", ""),
            "roc_plot": row.get("roc_plot", ""),
            "willr_plot": row.get("willr_plot", ""),
            "price_plot": row.get("price_plot", ""),
        }
        
        # Store the full image data
        self.redis.set(image_key, json.dumps(image_data), ex=self.ttl_seconds)
        
        # Update index for quick lookups
        index_entry = {
            "symbol": symbol,
            "timestamp": timestamp,
            "key": image_key,
        }
        self.redis.hset(self.IMAGES_INDEX_KEY, image_key, json.dumps(index_entry))
        self.redis.expire(self.IMAGES_INDEX_KEY, self.ttl_seconds)
    
    def on_time_end(self, time: int) -> None:
        pass
    
    def on_end(self) -> None:
        pass


class RedisNewsClusterObserver(pw.io.python.ConnectorObserver):
    """Pathway observer that writes news cluster data into Redis for API access."""
    
    NEWS_CLUSTERS_KEY_PREFIX = "news_clusters:"
    
    def __init__(self, ttl_seconds: int = 3600):
        self.redis = get_redis_client()
        self.ttl_seconds = ttl_seconds
        self._cluster_cache: Dict[str, Dict] = {}  # symbol -> {cluster_id -> cluster_data}
    
    def on_change(self, key: Any, row: Dict[str, Any], time: int, is_addition: bool) -> None:
        symbol = row.get("symbol")
        if not symbol:
            return
        
        symbol = str(symbol).upper()
        cluster_id = str(row.get("cluster_id", ""))
        
        if symbol not in self._cluster_cache:
            self._cluster_cache[symbol] = {}
        
        if not is_addition:
            # Remove cluster
            if cluster_id in self._cluster_cache[symbol]:
                del self._cluster_cache[symbol][cluster_id]
        else:
            # Add/update cluster with full article data
            articles_json = row.get("articles_json", "[]")
            try:
                articles = json.loads(articles_json) if isinstance(articles_json, str) else articles_json
            except:
                articles = []
            
            # Parse links
            links_json = row.get("links_json", "[]")
            try:
                links = json.loads(links_json) if isinstance(links_json, str) else links_json
            except:
                links = []
            
            self._cluster_cache[symbol][cluster_id] = {
                "cluster_id": cluster_id,
                "headline": row.get("headline", ""),
                "articles": articles,
                "links": links,
                "article_count": row.get("article_count", len(articles)),
                "first_seen": row.get("first_seen", ""),
                "last_updated": row.get("last_updated", ""),
            }
        
        # Save full cluster list for the symbol
        clusters_list = list(self._cluster_cache[symbol].values())
        cluster_key = f"{self.NEWS_CLUSTERS_KEY_PREFIX}{symbol}"
        self.redis.set(cluster_key, json.dumps(clusters_list), ex=self.ttl_seconds)
    
    def on_time_end(self, time: int) -> None:
        pass
    
    def on_end(self) -> None:
        pass


class RedisSentimentObserver(pw.io.python.ConnectorObserver):
    """Pathway observer that writes sentiment cluster data to standalone Redis keys."""
    
    def __init__(self, key_prefix: str = "sentiment_clusters:", ttl_seconds: int = 3600):
        self.redis = get_redis_client()
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
    
    def on_change(self, key: Any, row: Dict[str, Any], time: int, is_addition: bool) -> None:
        symbol = row.get("symbol")
        if not symbol:
            return
        
        symbol = str(symbol).upper()
        redis_key = f"{self.key_prefix}{symbol}"
        
        if not is_addition:
            self.redis.delete(redis_key)
            return
        
        # Store the full row data
        self.redis.set(redis_key, json.dumps(row), ex=self.ttl_seconds)
    
    def on_time_end(self, time: int) -> None:
        pass
    
    def on_end(self) -> None:
        pass


def get_report_observer(report_type: str) -> RedisReportObserver:
    """Return a singleton observer for the given report type."""
    
    # Special case for sentiment_clusters
    if report_type == "sentiment_clusters":
        if "sentiment_clusters" not in _observer_cache:
            ttl_env = os.getenv("REDIS_SENTIMENT_TTL")
            ttl_value = int(ttl_env) if ttl_env else 3600
            _observer_cache["sentiment_clusters"] = RedisSentimentObserver("sentiment_clusters:", ttl_value)
        return _observer_cache["sentiment_clusters"]
    
    # Special case for news_clusters
    if report_type == "news_clusters":
        if "news_clusters" not in _observer_cache:
            ttl_env = os.getenv("REDIS_NEWS_CLUSTER_TTL")
            ttl_value = int(ttl_env) if ttl_env else 3600
            _observer_cache["news_clusters"] = RedisNewsClusterObserver(ttl_value)
        return _observer_cache["news_clusters"]
    
    # Special case for images
    if report_type == "images":
        if "images" not in _observer_cache:
            ttl_env = os.getenv("REDIS_IMAGE_TTL")
            ttl_value = int(ttl_env) if ttl_env else 3600  # Default 1 hour
            _observer_cache["images"] = RedisImageObserver(ttl_value)
        return _observer_cache["images"]

    if report_type not in _observer_cache:
        ttl_env = os.getenv("REDIS_REPORT_TTL")
        ttl_value = int(ttl_env) if ttl_env else None
        _observer_cache[report_type] = RedisReportObserver(report_type, ttl_value)
    return _observer_cache[report_type]


def list_symbols(redis_client: Optional[redis.Redis] = None) -> list[str]:
    client = redis_client or get_redis_client()
    raw_symbols = client.smembers(REPORT_SYMBOL_SET_KEY)
    if not raw_symbols:
        return []

    valid_symbols: list[str] = []
    for symbol in raw_symbols:
        key = _build_symbol_key(symbol)
        if client.hlen(key) > 0:
            valid_symbols.append(symbol)
        else:
            client.srem(REPORT_SYMBOL_SET_KEY, symbol)

    return sorted(valid_symbols)


def get_reports_for_symbol(symbol: str, redis_client: Optional[redis.Redis] = None) -> Dict[str, Dict[str, Any]]:
    client = redis_client or get_redis_client()
    key = _build_symbol_key(symbol.upper())
    raw_entries = client.hgetall(key)

    reports: Dict[str, Dict[str, Any]] = {}
    for report_type, payload in raw_entries.items():
        try:
            entry = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            entry = {
                "symbol": symbol.upper(),
                "report_type": report_type,
                "content": payload,
            }
        reports[report_type] = entry

    return reports


def delete_symbol(symbol: str, redis_client: Optional[redis.Redis] = None) -> None:
    client = redis_client or get_redis_client()
    key = _build_symbol_key(symbol.upper())
    client.delete(key)
    client.srem(REPORT_SYMBOL_SET_KEY, symbol.upper())
