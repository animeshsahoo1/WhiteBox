"""Utilities for sharing AI reports via Redis."""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional

import pathway as pw
import redis

REDIS_DEFAULT_HOST = "localhost"
REDIS_DEFAULT_PORT = 6379
REDIS_DEFAULT_DB = 0
REPORT_SYMBOL_SET_KEY = "reports:symbols"
REPORT_KEY_PREFIX = "reports"


def _build_symbol_key(symbol: str) -> str:
    return f"{REPORT_KEY_PREFIX}:{symbol}"


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


class RedisClusterObserver(pw.io.python.ConnectorObserver):
    """Pathway observer that writes cluster visualization data into Redis."""
    
    CLUSTERS_KEY_PREFIX = "clusters:"
    ALL_CLUSTERS_KEY = "clusters:all"
    
    def __init__(self):
        self.redis = get_redis_client()
    
    def on_change(self, key: Any, row: Dict[str, Any], time: int, is_addition: bool) -> None:
        symbol = row.get("symbol")
        if not symbol:
            return
        
        symbol = str(symbol).upper()
        cluster_id = row.get("cluster_id")
        
        if not is_addition:
            # Remove cluster from Redis
            cluster_key = f"{self.CLUSTERS_KEY_PREFIX}{symbol}:{cluster_id}"
            self.redis.delete(cluster_key)
            # Also remove from the all clusters list
            self.redis.hdel(self.ALL_CLUSTERS_KEY, cluster_key)
            return
        
        # Add or update cluster
        cluster_data = {
            "symbol": symbol,
            "cluster_id": cluster_id,
            "summary": row.get("summary", ""),
            "avg_sentiment": float(row.get("avg_sentiment", 0.0)),
            "count": int(row.get("count", 0)),
            "timestamp": row.get("timestamp", datetime.utcnow().isoformat()),
        }
        
        # Store individual cluster
        cluster_key = f"{self.CLUSTERS_KEY_PREFIX}{symbol}:{cluster_id}"
        self.redis.set(cluster_key, json.dumps(cluster_data), ex=3600)  # 1 hour TTL
        
        # Also add to aggregated list for easy querying
        self.redis.hset(self.ALL_CLUSTERS_KEY, cluster_key, json.dumps(cluster_data))
        self.redis.expire(self.ALL_CLUSTERS_KEY, 3600)
    
    def on_time_end(self, time: int) -> None:
        pass
    
    def on_end(self) -> None:
        pass


class RedisImageObserver(pw.io.python.ConnectorObserver):
    """Pathway observer that writes indicator chart images into Redis."""
    
    IMAGES_KEY_PREFIX = "images:"
    IMAGES_INDEX_KEY = "images:index"
    
    def __init__(self, ttl_seconds: int = 3600):
        self.redis = get_redis_client()
        self.ttl_seconds = ttl_seconds
    
    def on_change(self, key: Any, row: Dict[str, Any], time: int, is_addition: bool) -> None:
        symbol = row.get("symbol")
        if not symbol:
            return
        
        symbol = str(symbol).upper()
        
        # Extract timestamp (use window_end or current time)
        timestamp_raw = row.get("window_end") or row.get("timestamp") or datetime.utcnow()
        if isinstance(timestamp_raw, datetime):
            timestamp = timestamp_raw.strftime("%Y%m%d_%H%M%S")
        else:
            timestamp = str(timestamp_raw).replace(" ", "_").replace(":", "").replace("-", "")
        
        # Build unique key for this image set
        image_set_key = f"{self.IMAGES_KEY_PREFIX}{symbol}:{timestamp}"
        
        if not is_addition:
            # Remove images
            self.redis.delete(image_set_key)
            self.redis.hdel(self.IMAGES_INDEX_KEY, f"{symbol}:{timestamp}")
            return
        
        # Extract images from row (assuming images are in a Json field)
        images_data = row.get("images")
        if not images_data:
            return
        
        # Convert to dict if it's a Json object
        if hasattr(images_data, "as_dict"):
            images_dict = images_data.as_dict()
        elif isinstance(images_data, dict):
            images_dict = images_data
        else:
            return
        
        # Store all images in a single hash
        image_payload = {
            "symbol": symbol,
            "timestamp": timestamp,
            "window_start": str(row.get("window_start", "")),
            "window_end": str(row.get("window_end", "")),
            "pattern_image": images_dict.get("pattern_image", ""),
            "trend_image": images_dict.get("trend_image", ""),
            "rsi_plot": images_dict.get("rsi_plot", ""),
            "macd_plot": images_dict.get("macd_plot", ""),
            "stochastic_plot": images_dict.get("stochastic_plot", ""),
            "roc_plot": images_dict.get("roc_plot", ""),
            "willr_plot": images_dict.get("willr_plot", ""),
            "price_plot": images_dict.get("price_plot", ""),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store as JSON in Redis
        self.redis.set(image_set_key, json.dumps(image_payload), ex=self.ttl_seconds)
        
        # Add to index for easy lookup
        index_entry = {
            "symbol": symbol,
            "timestamp": timestamp,
            "key": image_set_key,
            "created_at": datetime.utcnow().isoformat()
        }
        self.redis.hset(self.IMAGES_INDEX_KEY, f"{symbol}:{timestamp}", json.dumps(index_entry))
        self.redis.expire(self.IMAGES_INDEX_KEY, self.ttl_seconds)
        
        print(f"✅ Cached images for {symbol} at {timestamp} in Redis: {image_set_key}")
    
    def on_time_end(self, time: int) -> None:
        pass
    
    def on_end(self) -> None:
        pass


def get_report_observer(report_type: str) -> RedisReportObserver:
    """Return a singleton observer for the given report type."""
    
    # Special case for clusters
    if report_type == "clusters":
        if "clusters" not in _observer_cache:
            _observer_cache["clusters"] = RedisClusterObserver()
        return _observer_cache["clusters"]
    
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


def get_images_for_symbol(symbol: str, timestamp: Optional[str] = None, redis_client: Optional[redis.Redis] = None) -> Dict[str, Any]:
    """
    Retrieve indicator chart images for a symbol from Redis.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        timestamp: Optional specific timestamp (format: YYYYMMDD_HHMMSS). If None, returns latest.
        redis_client: Optional Redis client instance
    
    Returns:
        Dictionary with image data or empty dict if not found
    """
    client = redis_client or get_redis_client()
    symbol = symbol.upper()
    
    if timestamp:
        # Get specific timestamp
        image_key = f"images:{symbol}:{timestamp}"
        data = client.get(image_key)
        if data:
            try:
                return json.loads(data)
            except (TypeError, json.JSONDecodeError):
                return {}
        return {}
    else:
        # Get latest - scan all keys for this symbol
        index_data = client.hgetall("images:index")
        symbol_images = []
        
        for key, value in index_data.items():
            try:
                entry = json.loads(value)
                if entry.get("symbol") == symbol:
                    symbol_images.append(entry)
            except (TypeError, json.JSONDecodeError):
                continue
        
        if not symbol_images:
            return {}
        
        # Sort by timestamp and get latest
        symbol_images.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        latest = symbol_images[0]
        
        # Fetch the actual image data
        image_key = latest.get("key")
        if image_key:
            data = client.get(image_key)
            if data:
                try:
                    return json.loads(data)
                except (TypeError, json.JSONDecodeError):
                    return {}
        
        return {}


def list_images_for_symbol(symbol: str, redis_client: Optional[redis.Redis] = None) -> list[Dict[str, Any]]:
    """
    List all available image timestamps for a symbol.
    
    Args:
        symbol: Stock symbol
        redis_client: Optional Redis client instance
    
    Returns:
        List of image metadata dictionaries
    """
    client = redis_client or get_redis_client()
    symbol = symbol.upper()
    
    index_data = client.hgetall("images:index")
    symbol_images = []
    
    for key, value in index_data.items():
        try:
            entry = json.loads(value)
            if entry.get("symbol") == symbol:
                symbol_images.append(entry)
        except (TypeError, json.JSONDecodeError):
            continue
    
    # Sort by timestamp descending (newest first)
    symbol_images.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return symbol_images
