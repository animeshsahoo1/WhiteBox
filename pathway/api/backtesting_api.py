"""
Backtesting API Router - Strategy metrics and management endpoints.

Endpoints:
- GET /backtesting/metrics - Get all strategy metrics (from Redis cache)
- GET /backtesting/metrics/{strategy} - Get metrics for specific strategy
- GET /backtesting/strategies - List all strategies
- GET /backtesting/strategies/{name} - Get strategy code and metrics
- POST /backtesting/strategies - Create strategy from natural language (LLM)
- DELETE /backtesting/strategies/{name} - Delete a strategy
- POST /backtesting/strategies/search - Semantic search strategies (embeddings)
"""

import os
import re
import ast
import json
import math
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
STRATEGIES_FOLDER = Path(__file__).parent.parent / "strategies"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")

# Ensure strategies folder exists
STRATEGIES_FOLDER.mkdir(exist_ok=True)

# Create router
router = APIRouter(prefix="/backtesting", tags=["Backtesting"])


# ============================================================================
# REDIS METRICS STORE
# ============================================================================

class BacktestingMetricsStore:
    """
    Redis-backed store for backtesting strategy metrics.
    Reads from keys populated by the Pathway backtesting pipeline.
    
    Keys are structured as backtesting:{strategy}:{symbol}:{interval} to support
    multi-symbol, multi-interval backtesting. This allows comparing strategy
    performance across different configs.
    """
    
    _redis_client = None
    _fallback_store: Dict[str, Dict[str, Any]] = {}
    _use_fallback = False
    
    @classmethod
    def _get_redis(cls):
        """Get or create Redis connection."""
        if cls._use_fallback:
            return None
        if cls._redis_client is None:
            try:
                import redis
                redis_host = os.getenv("REDIS_HOST", "redis")
                redis_port = int(os.getenv("REDIS_PORT", 6379))
                redis_db = int(os.getenv("REDIS_DB", 0))
                cls._redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2
                )
                cls._redis_client.ping()
                print(f"✅ Backtesting API connected to Redis: {redis_host}:{redis_port}")
            except Exception as e:
                print(f"⚠️ Redis unavailable ({e}), using in-memory fallback")
                cls._use_fallback = True
                cls._redis_client = None
        return cls._redis_client
    
    @classmethod
    def _parse_entry(cls, data: str) -> Optional[Dict[str, Any]]:
        """Parse a Redis entry and extract metrics."""
        if not data:
            return None
        parsed = json.loads(data)
        if "metrics" in parsed:
            metrics = json.loads(parsed["metrics"]) if isinstance(parsed["metrics"], str) else parsed["metrics"]
            metrics["strategy"] = parsed.get("strategy")
            metrics["symbol"] = parsed.get("symbol")
            metrics["interval"] = parsed.get("interval")
            metrics["last_updated"] = parsed.get("last_updated")
            metrics["received_at"] = parsed.get("received_at")
            return metrics
        return parsed
    
    @classmethod
    def get(cls, strategy: str, symbol: Optional[str] = None, interval: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a strategy from Redis cache.
        
        Args:
            strategy: Strategy name
            symbol: Optional symbol filter
            interval: Optional interval filter (e.g., "1m", "1h", "1d")
        
        Returns:
            If both symbol and interval provided: single metrics dict
            Otherwise: dict of {key: metrics} for matching entries
        """
        redis_client = cls._get_redis()
        if redis_client:
            try:
                strategy_upper = strategy.upper()
                
                if symbol and interval:
                    # Exact match: strategy:symbol:interval
                    key = f"backtesting:{strategy_upper}:{symbol.upper()}:{interval.lower()}"
                    data = redis_client.get(key)
                    return cls._parse_entry(data)
                
                elif symbol:
                    # Match strategy:symbol:* (all intervals for this symbol)
                    pattern = f"backtesting:{strategy_upper}:{symbol.upper()}:*"
                elif interval:
                    # Match strategy:*:interval (all symbols for this interval)
                    pattern = f"backtesting:{strategy_upper}:*:{interval.lower()}"
                else:
                    # Match strategy:*:* (all symbols and intervals)
                    pattern = f"backtesting:{strategy_upper}:*:*"
                
                results = {}
                for key in redis_client.scan_iter(match=pattern, count=100):
                    data = redis_client.get(key)
                    parsed = cls._parse_entry(data)
                    if parsed:
                        sym = parsed.get("symbol", "UNKNOWN")
                        intv = parsed.get("interval", "unknown")
                        combo_key = f"{sym}:{intv}"
                        results[combo_key] = parsed
                
                return results if results else None
            except Exception as e:
                print(f"Redis read error: {e}")
        return cls._fallback_store.get(strategy)
    
    @classmethod
    def get_all(cls, symbol: Optional[str] = None, interval: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get all strategy metrics from Redis cache.
        
        Args:
            symbol: Optional filter by symbol
            interval: Optional filter by interval
        
        Returns:
            Dict of {strategy:symbol:interval: metrics}
        """
        redis_client = cls._get_redis()
        result = {}
        if redis_client:
            try:
                # Build pattern based on filters
                if symbol and interval:
                    pattern = f"backtesting:*:{symbol.upper()}:{interval.lower()}"
                elif symbol:
                    pattern = f"backtesting:*:{symbol.upper()}:*"
                elif interval:
                    pattern = f"backtesting:*:*:{interval.lower()}"
                else:
                    pattern = "backtesting:*:*:*"
                
                for key in redis_client.scan_iter(match=pattern, count=100):
                    # Skip the set keys
                    if key in ("backtesting:strategies", "backtesting:symbols", "backtesting:intervals"):
                        continue
                    data = redis_client.get(key)
                    parsed = cls._parse_entry(data)
                    if parsed:
                        strategy = parsed.get("strategy", "UNKNOWN")
                        sym = parsed.get("symbol", "UNKNOWN")
                        intv = parsed.get("interval", "unknown")
                        combo_key = f"{strategy}:{sym}:{intv}"
                        result[combo_key] = parsed
            except Exception as e:
                print(f"Redis read error: {e}")
        return result if result else cls._fallback_store.copy()
    
    @classmethod
    def list_strategies(cls) -> List[str]:
        """List unique strategies with metrics in Redis."""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                return list(redis_client.smembers("backtesting:strategies"))
            except Exception as e:
                print(f"Redis read error: {e}")
        return list(cls._fallback_store.keys())
    
    @classmethod
    def list_symbols(cls) -> List[str]:
        """List unique symbols with metrics in Redis."""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                return list(redis_client.smembers("backtesting:symbols"))
            except Exception as e:
                print(f"Redis read error: {e}")
        return []
    
    @classmethod
    def list_intervals(cls) -> List[str]:
        """List unique intervals with metrics in Redis."""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                return list(redis_client.smembers("backtesting:intervals"))
            except Exception as e:
                print(f"Redis read error: {e}")
        return []
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if Redis is connected."""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                return redis_client.ping()
            except:
                pass
        return False
    
    @classmethod
    def delete_strategy_metrics(cls, strategy: str) -> int:
        """
        Delete all cached metrics for a strategy.
        
        Args:
            strategy: Strategy name to delete metrics for
        
        Returns:
            Number of keys deleted
        """
        redis_client = cls._get_redis()
        deleted_count = 0
        
        if redis_client:
            try:
                strategy_upper = strategy.upper()
                pattern = f"backtesting:{strategy_upper}:*:*"
                
                # Find and delete all matching keys
                keys_to_delete = list(redis_client.scan_iter(match=pattern, count=100))
                if keys_to_delete:
                    deleted_count = redis_client.delete(*keys_to_delete)
                    print(f"🗑️ Deleted {deleted_count} Redis metrics keys for strategy: {strategy}")
                
                # Also remove from strategies set
                redis_client.srem("backtesting:strategies", strategy_upper)
                
            except Exception as e:
                print(f"Redis delete error: {e}")
        
        # Also clean from fallback store
        if strategy in cls._fallback_store:
            del cls._fallback_store[strategy]
            deleted_count = max(deleted_count, 1)
        
        return deleted_count
    
    @classmethod
    def get_redis_client(cls):
        """Get the Redis client for external use."""
        return cls._get_redis()


MetricsStore = BacktestingMetricsStore


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class StrategyMetrics(BaseModel):
    strategy: str
    symbol: Optional[str] = None
    interval: Optional[str] = None
    lookback: Optional[str] = None
    total_pnl: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    return_pct: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    last_signal: str = "HOLD"
    position: str = "NONE"
    candles_processed: int = 0


# Valid intervals and lookback periods
VALID_INTERVALS = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo"]
VALID_LOOKBACKS = ["7d", "14d", "30d", "1mo", "2mo", "3mo", "6mo", "1y", "2y", "5y", "max"]


class StrategyCreateRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=500, description="Strategy description in natural language")
    name: Optional[str] = Field(default=None, max_length=50, pattern=r'^[a-zA-Z0-9_-]*$')
    interval: str = Field(default="1h", description="Candle interval (1m, 5m, 15m, 30m, 1h, 1d)")
    lookback: str = Field(default="6mo", description="Backtest lookback period (7d, 1mo, 3mo, 6mo, 1y, 2y)")
    
    @classmethod
    def validate_interval(cls, v):
        if v not in VALID_INTERVALS:
            raise ValueError(f"Invalid interval '{v}'. Valid: {VALID_INTERVALS}")
        return v
    
    @classmethod
    def validate_lookback(cls, v):
        if v not in VALID_LOOKBACKS:
            raise ValueError(f"Invalid lookback '{v}'. Valid: {VALID_LOOKBACKS}")
        return v
    
    def __init__(self, **data):
        super().__init__(**data)
        # Validate after init
        if self.interval not in VALID_INTERVALS:
            raise ValueError(f"Invalid interval '{self.interval}'. Valid: {VALID_INTERVALS}")
        if self.lookback not in VALID_LOOKBACKS:
            raise ValueError(f"Invalid lookback '{self.lookback}'. Valid: {VALID_LOOKBACKS}")


class StrategyResponse(BaseModel):
    name: str
    code: str
    description: str
    interval: str
    lookback: str
    message: str


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    metric_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional weights for metrics to influence ranking. E.g., {'sharpe_ratio': 0.5, 'win_rate': 0.3}"
    )


# ============================================================================
# EMBEDDINGS HELPERS
# ============================================================================

EMBEDDINGS_KEY = "backtesting:embeddings"


def load_embeddings() -> Dict:
    """Load all embeddings from Redis."""
    try:
        client = MetricsStore.get_redis_client()
        if client:
            data = client.get(EMBEDDINGS_KEY)
            if data:
                return json.loads(data)
    except Exception as e:
        print(f"⚠️ Redis embeddings load error: {e}")
    return {}


def save_embeddings(embeddings: Dict):
    """Save all embeddings to Redis."""
    try:
        client = MetricsStore.get_redis_client()
        if client:
            client.set(EMBEDDINGS_KEY, json.dumps(embeddings))
    except Exception as e:
        print(f"⚠️ Redis embeddings save error: {e}")


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(x * x for x in b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding from OpenRouter using their embeddings API."""
    if not OPENROUTER_API_KEY:
        print("⚠️ No API key configured for embeddings")
        return None
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://pathway-backtesting.local",
                    "X-Title": "Pathway Backtesting"
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    return data["data"][0]["embedding"]
            else:
                print(f"⚠️ Embedding API error {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"⚠️ Embedding request failed: {e}")
    
    return None


# ============================================================================
# STATUS ENDPOINT
# ============================================================================

@router.get("/")
async def backtesting_status():
    """Get backtesting service status."""
    return {
        "status": "healthy",
        "service": "backtesting-api",
        "version": "3.0.0",  # Updated for multi-symbol support
        "strategies_count": len(list(STRATEGIES_FOLDER.glob("*.txt"))),
        "metrics_strategies": len(MetricsStore.list_strategies()),
        "metrics_symbols": len(MetricsStore.list_symbols()),
        "metrics_intervals": len(MetricsStore.list_intervals()),
        "redis_connected": MetricsStore.is_connected(),
        "llm_configured": bool(OPENROUTER_API_KEY),
        "embedding_model": EMBEDDING_MODEL,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# METRICS ENDPOINTS (Redis-cached from Pathway pipeline)
# ============================================================================

@router.get("/metrics")
async def get_all_metrics(symbol: Optional[str] = None, interval: Optional[str] = None):
    """
    Get all strategy metrics from Redis cache (populated by Pathway pipeline).
    
    Args:
        symbol: Optional filter by symbol (e.g., AAPL, GOOGL)
        interval: Optional filter by interval (e.g., 1m, 1h, 1d)
    
    Returns metrics grouped by strategy:symbol:interval combinations.
    """
    metrics = MetricsStore.get_all(symbol=symbol, interval=interval)
    return {
        "strategies": metrics,
        "count": len(metrics),
        "filter_symbol": symbol,
        "filter_interval": interval,
        "available_symbols": MetricsStore.list_symbols(),
        "available_intervals": MetricsStore.list_intervals(),
        "redis_connected": MetricsStore.is_connected(),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/metrics/{strategy}")
async def get_strategy_metrics(strategy: str, symbol: Optional[str] = None, interval: Optional[str] = None):
    """
    Get metrics for a specific strategy.
    
    Args:
        strategy: Strategy name (e.g., macd_rsi_confluence)
        symbol: Optional filter by symbol
        interval: Optional filter by interval (e.g., 1m, 1h, 1d)
    
    Returns:
        If symbol and interval provided: metrics for that exact combination
        Otherwise: dict of matching entries
    """
    # Try exact match first, then uppercase
    metrics = MetricsStore.get(strategy, symbol=symbol, interval=interval)
    if not metrics:
        metrics = MetricsStore.get(
            strategy.upper(), 
            symbol=symbol.upper() if symbol else None,
            interval=interval.lower() if interval else None
        )
    
    if not metrics:
        detail = f"No metrics found for strategy: {strategy}"
        if symbol:
            detail += f" with symbol: {symbol}"
        if interval:
            detail += f" with interval: {interval}"
        raise HTTPException(404, detail)
    
    return {
        "strategy": strategy,
        "symbol": symbol,
        "interval": interval,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/symbols")
async def list_symbols():
    """List all symbols with backtesting metrics."""
    symbols = MetricsStore.list_symbols()
    return {
        "symbols": sorted(symbols),
        "count": len(symbols),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/intervals")
async def list_intervals():
    """List all intervals with backtesting metrics."""
    intervals = MetricsStore.list_intervals()
    return {
        "intervals": sorted(intervals),
        "count": len(intervals),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# STRATEGY MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/strategies")
async def list_strategies(symbol: Optional[str] = None, interval: Optional[str] = None):
    """
    List all strategies with their metrics status.
    
    Args:
        symbol: Optional filter to show metrics for a specific symbol only
        interval: Optional filter to show metrics for a specific interval only
    """
    strategies = [f.stem for f in STRATEGIES_FOLDER.glob("*.txt")]
    embeddings = load_embeddings()
    result = []
    
    for name in strategies:
        # Read strategy file to extract interval and lookback
        filepath = STRATEGIES_FOLDER / f"{name}.txt"
        code = filepath.read_text() if filepath.exists() else ""
        
        # Extract interval and lookback from header
        strategy_interval = "1h"  # default
        strategy_lookback = "6mo"  # default
        
        interval_match = re.search(r'^#\s*interval:\s*(\S+)', code, re.MULTILINE)
        if interval_match:
            strategy_interval = interval_match.group(1)
        
        lookback_match = re.search(r'^#\s*lookback:\s*(\S+)', code, re.MULTILINE)
        if lookback_match:
            strategy_lookback = lookback_match.group(1)
        
        # Try to get metrics (strategy names are uppercase in Redis)
        metrics = MetricsStore.get(name, symbol=symbol, interval=interval) or \
                  MetricsStore.get(name.upper(), 
                                   symbol=symbol.upper() if symbol else None,
                                   interval=interval.lower() if interval else None)
        description = embeddings.get(name, {}).get("description", "")
        
        # If no symbol/interval filter, metrics will be a dict of {symbol:interval: metrics}
        # If filters provided, metrics will be the filtered results
        if isinstance(metrics, dict) and not (symbol and interval):
            # Aggregate across all configs or show summary
            config_keys = list(metrics.keys()) if metrics else []
            total_pnl = sum(m.get("total_pnl", 0) for m in metrics.values()) if metrics else None
            total_trades = sum(m.get("total_trades", 0) for m in metrics.values()) if metrics else None
            
            result.append({
                "name": name,
                "description": description,
                "interval": strategy_interval,
                "lookback": strategy_lookback,
                "has_metrics": bool(metrics),
                "configs": config_keys,  # List of symbol:interval combos
                "total_pnl_all_configs": total_pnl,
                "total_trades_all_configs": total_trades,
            })
        else:
            result.append({
                "name": name,
                "description": description,
                "interval": strategy_interval,
                "lookback": strategy_lookback,
                "filter_symbol": symbol,
                "filter_interval": interval,
                "has_metrics": metrics is not None,
                "total_pnl": metrics.get("total_pnl") if metrics else None,
                "total_trades": metrics.get("total_trades") if metrics else None,
                "win_rate": metrics.get("win_rate") if metrics else None,
                "candles_processed": metrics.get("candles_processed") if metrics else None,
            })
    
    return {
        "strategies": result, 
        "count": len(result),
        "filter_symbol": symbol,
        "filter_interval": interval,
        "available_symbols": MetricsStore.list_symbols(),
        "available_intervals": MetricsStore.list_intervals()
    }


@router.get("/strategies/{name}")
async def get_strategy(name: str, symbol: Optional[str] = None, interval: Optional[str] = None):
    """
    Get strategy code and metrics.
    
    Args:
        name: Strategy name
        symbol: Optional filter for specific symbol metrics
        interval: Optional filter for specific interval metrics
    """
    filepath = STRATEGIES_FOLDER / f"{name}.txt"
    
    # Try lowercase version
    if not filepath.exists():
        filepath = STRATEGIES_FOLDER / f"{name.lower()}.txt"
    
    if not filepath.exists():
        raise HTTPException(404, f"Strategy not found: {name}")
    
    code = filepath.read_text()
    
    # Extract interval and lookback from strategy file header
    strategy_interval = "1h"  # default
    strategy_lookback = "6mo"  # default
    
    interval_match = re.search(r'^#\s*interval:\s*(\S+)', code, re.MULTILINE)
    if interval_match:
        strategy_interval = interval_match.group(1)
    
    lookback_match = re.search(r'^#\s*lookback:\s*(\S+)', code, re.MULTILINE)
    if lookback_match:
        strategy_lookback = lookback_match.group(1)
    
    metrics = MetricsStore.get(name, symbol=symbol, interval=interval) or \
              MetricsStore.get(name.upper(), 
                               symbol=symbol.upper() if symbol else None,
                               interval=interval.lower() if interval else None)
    embeddings = load_embeddings()
    description = embeddings.get(filepath.stem, {}).get("description", "")
    
    return {
        "name": filepath.stem,
        "description": description,
        "code": code,
        "interval": strategy_interval,
        "lookback": strategy_lookback,
        "filter_symbol": symbol,
        "filter_interval": interval,
        "metrics": metrics,
        "available_symbols": MetricsStore.list_symbols(),
        "available_intervals": MetricsStore.list_intervals(),
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/strategies/{name}")
async def delete_strategy(name: str):
    """Delete a strategy file and its cached metrics."""
    filepath = STRATEGIES_FOLDER / f"{name}.txt"
    
    if not filepath.exists():
        filepath = STRATEGIES_FOLDER / f"{name.lower()}.txt"
    
    if not filepath.exists():
        raise HTTPException(404, f"Strategy not found: {name}")
    
    filepath.unlink()
    
    # Remove embedding
    embeddings = load_embeddings()
    if name in embeddings:
        del embeddings[name]
        save_embeddings(embeddings)
    
    # Remove cached metrics from Redis
    deleted_metrics = MetricsStore.delete_strategy_metrics(name)
    
    return {
        "message": f"Strategy '{name}' deleted", 
        "name": name,
        "metrics_deleted": deleted_metrics
    }


@router.post("/strategies", response_model=StrategyResponse)
async def create_strategy(request: StrategyCreateRequest):
    """
    Create a new strategy from natural language description using LLM.
    
    The strategy will be created with the specified interval and lookback period
    in the file header. These are used by the backtesting pipeline to:
    - interval: Only process candles matching this interval
    - lookback: Only backtest using data from this period
    """
    if not OPENROUTER_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY or OPENROUTER_API_KEY not configured")
    
    prompt = f"""You are a trading strategy developer. Create a concise Python trading strategy function.

User request: "{request.description}"
Target interval: {request.interval}
Backtest period: {request.lookback}

IMPORTANT - Follow this exact style (short docstring, minimal code, return None for no action):

```python
def strategy(indicators):
    \"\"\"
    Strategy Name
    
    Entry: condition
    Exit: condition
    SL: X%
    TP: Y%
    
    Best for: {request.interval} charts
    \"\"\"
    import numpy as np
    
    # Get only the indicators you need
    rsi = indicators.get('rsi_14')
    close = indicators.get('close')
    
    # Guard against None/NaN
    if rsi is None or np.isnan(rsi) or close is None:
        return None
    
    # Entry signal
    if rsi < 30:
        return {{
            'action': 'BUY',
            'stop_loss': close * 0.98,
            'take_profit': close * 1.05,
            'size': 0.5
        }}
    
    # Exit signal
    if rsi > 70:
        return {{'action': 'SELL'}}
    
    return None
```

Available indicators: sma_5, sma_10, sma_20, sma_50, sma_200, ema_9, ema_12, ema_26, rsi_14, bb_upper, bb_middle, bb_lower, atr_14, close, open, high, low, volume, position, entry_price, adx, plus_di, minus_di, macd_line, macd_signal, macd_histogram, stoch_k, stoch_d, williams_r, cci_20

Rules:
1. Keep docstring SHORT (5-7 lines max) - just strategy name and key parameters
2. Only import numpy if needed for np.isnan()
3. Return None for no action (NOT {{'action': None}})
4. Return dict with 'action' and optionally: stop_loss, take_profit, trailing_stop, size
5. Keep code under 40 lines total
6. NO verbose parameter documentation
7. DO NOT include the # interval: or # lookback: headers - those will be added automatically

Return ONLY the Python code (the def strategy function), no markdown or explanation."""

    # LLM call with retry logic (exponential backoff)
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://pathway-backtesting.local",
                        "X-Title": "Pathway Backtesting"
                    },
                    json={
                        "model": "openai/gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=60.0
                )
                
                if response.status_code == 429:
                    # Rate limited - retry with backoff
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Rate limited, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    raise HTTPException(429, "LLM rate limit exceeded. Please try again later.")
                
                if response.status_code != 200:
                    raise HTTPException(500, f"LLM error: {response.text}")
                
                code = response.json()["choices"][0]["message"]["content"]
                code = re.sub(r'^```python\s*', '', code, flags=re.MULTILINE)
                code = re.sub(r'^```\s*$', '', code, flags=re.MULTILINE)
                code = code.strip()
                break  # Success - exit retry loop
                
        except HTTPException:
            raise
        except httpx.TimeoutException:
            last_error = "Request timed out"
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ Timeout, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            raise HTTPException(504, f"LLM request timed out after {max_retries} attempts")
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⚠️ Error: {e}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            raise HTTPException(500, f"Strategy generation failed after {max_retries} attempts: {last_error}")
    
    # Validate generated code syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise HTTPException(
            400, 
            f"LLM generated invalid Python code. Syntax error at line {e.lineno}: {e.msg}. "
            f"Try rephrasing your strategy description."
        )
    
    # Generate name from description
    name = request.name or "_".join(request.description.lower().split()[:4])
    name = re.sub(r'[^\w]', '_', name)[:50]
    
    # Add interval and lookback header to the code
    full_code = f"# interval: {request.interval}\n# lookback: {request.lookback}\n\n{code}"
    
    # Save strategy file
    filepath = STRATEGIES_FOLDER / f"{name}.txt"
    filepath.write_text(full_code)
    
    # Generate and save embedding
    embedding = await get_embedding(request.description)
    if embedding:
        embeddings = load_embeddings()
        embeddings[name] = {
            "description": request.description, 
            "embedding": embedding,
            "interval": request.interval,
            "lookback": request.lookback
        }
        save_embeddings(embeddings)
        print(f"✅ Saved embedding for strategy: {name}")
    
    return StrategyResponse(
        name=name,
        code=full_code,
        description=request.description,
        interval=request.interval,
        lookback=request.lookback,
        message=f"Strategy '{name}' created with interval={request.interval}, lookback={request.lookback}. It will be picked up by the pipeline automatically."
    )


@router.post("/strategies/search")
async def search_strategies(request: SearchRequest):
    """Semantic search for strategies using embeddings."""
    query_embedding = await get_embedding(request.query)
    if not query_embedding:
        raise HTTPException(500, "Failed to generate query embedding. Check API key and embedding model.")
    
    embeddings = load_embeddings()
    if not embeddings:
        return {
            "query": request.query,
            "results": [],
            "count": 0,
            "message": "No strategies with embeddings found."
        }
    
    # Get list of existing strategy files
    existing_strategies = set()
    for f in STRATEGIES_FOLDER.glob("*.txt"):
        existing_strategies.add(f.stem)
    
    results = []
    for name, data in embeddings.items():
        # Only include strategies that still exist as files
        if name not in existing_strategies:
            continue
        if "embedding" in data:
            similarity = cosine_similarity(query_embedding, data["embedding"])
            metrics = MetricsStore.get(name) or MetricsStore.get(name.upper())
            results.append({
                "name": name,
                "description": data.get("description", ""),
                "similarity": round(similarity, 4),
                "metrics": metrics
            })
    
    # Apply weighted scoring if metric_weights provided
    if request.metric_weights:
        # Step 1: Collect all metric values for min-max normalization
        metric_values: Dict[str, List[float]] = {m: [] for m in request.metric_weights.keys()}
        
        for result in results:
            if result["metrics"]:
                for metric in request.metric_weights.keys():
                    value = result["metrics"].get(metric)
                    if value is not None and not (isinstance(value, float) and math.isnan(value)):
                        metric_values[metric].append(value)
        
        # Step 2: Calculate min/max for each metric
        metric_ranges: Dict[str, tuple] = {}
        for metric, values in metric_values.items():
            if values:
                min_val, max_val = min(values), max(values)
                metric_ranges[metric] = (min_val, max_val)
        
        # Step 3: Compute weighted score with proper min-max normalization
        for result in results:
            # Start with similarity as base score (already 0-1)
            weighted_score = result["similarity"]
            
            if result["metrics"]:
                for metric, weight in request.metric_weights.items():
                    value = result["metrics"].get(metric)
                    if value is not None and not (isinstance(value, float) and math.isnan(value)):
                        if metric in metric_ranges:
                            min_val, max_val = metric_ranges[metric]
                            
                            # Min-max normalization: (x - min) / (max - min)
                            if max_val != min_val:
                                normalized = (value - min_val) / (max_val - min_val)
                            else:
                                normalized = 0.5  # All values are the same
                            
                            # For max_drawdown, lower is better, so invert
                            if metric == "max_drawdown":
                                normalized = 1 - normalized
                            
                            weighted_score += normalized * weight
            
            result["weighted_score"] = round(weighted_score, 4)
        
        # Sort by weighted score (higher is better)
        results.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)
        sort_method = "weighted"
    else:
        # Default: sort by similarity only
        results.sort(key=lambda x: x["similarity"], reverse=True)
        sort_method = "similarity"
    
    return {
        "query": request.query,
        "sort_method": sort_method,
        "metric_weights": request.metric_weights,
        "results": results[:request.limit],
        "count": len(results[:request.limit]),
        "note": "Rankings update live as new candles arrive and metrics change in Redis."
    }


# ============================================================================
# STARTUP - Generate embeddings for existing strategies
# ============================================================================

async def initialize_embeddings():
    """
    Generate embeddings for existing strategies that don't have them.
    Called on startup by the main FastAPI app.
    """
    print("=" * 60)
    print("🚀 BACKTESTING API - Initializing")
    print("=" * 60)
    print(f"  Strategies folder: {STRATEGIES_FOLDER}")
    print(f"  Redis connected: {MetricsStore.is_connected()}")
    print(f"  LLM configured: {bool(OPENROUTER_API_KEY)}")
    print(f"  Embedding model: {EMBEDDING_MODEL}")
    
    strategies = list(STRATEGIES_FOLDER.glob('*.txt'))
    print(f"  Found {len(strategies)} strategy files")
    
    # Generate embeddings for existing strategies that don't have them
    if OPENROUTER_API_KEY:
        embeddings = load_embeddings()
        new_embeddings = 0
        
        for filepath in strategies:
            name = filepath.stem
            if name not in embeddings:
                code = filepath.read_text()
                # Extract description from docstring or comments
                description = _extract_description(name, code)
                
                print(f"  📊 Generating embedding for: {name}")
                print(f"     Description: {description[:60]}...")
                
                embedding = await get_embedding(f"{name}: {description}")
                if embedding:
                    embeddings[name] = {"description": description, "embedding": embedding}
                    new_embeddings += 1
                    print(f"  ✅ Embedded: {name}")
                else:
                    print(f"  ⚠️ Failed to embed: {name}")
        
        if new_embeddings > 0:
            save_embeddings(embeddings)
            print(f"  💾 Saved {new_embeddings} new embeddings to Redis")
        
        print(f"  📚 Total embeddings: {len(embeddings)}")
    else:
        print("  ⚠️ No API key - skipping embedding generation")
    
    print("=" * 60)


def _extract_description(name: str, code: str) -> str:
    """Extract description from strategy code (docstring or comments)."""
    description = f"Trading strategy: {name}"
    
    # Try to extract docstring (triple quotes)
    if '"""' in code:
        try:
            start = code.index('"""') + 3
            end = code.index('"""', start)
            docstring = code[start:end].strip()
            # Get first paragraph of docstring
            description = docstring.split('\n\n')[0].replace('\n', ' ').strip()
            if len(description) > 200:
                description = description[:200] + "..."
        except:
            pass
    elif "'''" in code:
        try:
            start = code.index("'''") + 3
            end = code.index("'''", start)
            docstring = code[start:end].strip()
            description = docstring.split('\n\n')[0].replace('\n', ' ').strip()
            if len(description) > 200:
                description = description[:200] + "..."
        except:
            pass
    else:
        # Fall back to first comment
        lines = code.strip().split('\n')
        for line in lines[:10]:
            if line.strip().startswith('#'):
                description = line.strip('# ').strip()
                break
    
    return description
