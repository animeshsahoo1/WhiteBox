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


def get_report_observer(report_type: str) -> RedisReportObserver:
    """Return a singleton observer for the given report type."""
    
    # Special case for clusters
    if report_type == "clusters":
        if "clusters" not in _observer_cache:
            _observer_cache["clusters"] = RedisClusterObserver()
        return _observer_cache["clusters"]

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
