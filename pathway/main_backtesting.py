"""
Pathway Streaming Backtesting Pipeline

Consumes candles from Kafka via CandleConsumer, runs backtesting for all strategies,
and pushes real-time metrics to Redis cache.

Architecture:
- Each strategy specifies its preferred interval and lookback period
- Natural join on interval: strategy only sees candles matching its interval
- Groupby (strategy, symbol): separate metrics per strategy per symbol
- Lookback filtering: only process candles within strategy's lookback window

Usage:
    python main_backtesting.py

Environment Variables:
    CANDLE_KAFKA_TOPIC: Topic for candle data (default: candles)
    STRATEGIES_DIR: Path to strategies folder (default: ./strategies)
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

import pathway as pw


# ============================================================================
# INTERVAL-BASED FORGET THRESHOLDS (matches producer's yfinance constraints)
# ============================================================================
# These thresholds define how long to keep candles in memory per interval.
# Based on the max historical data the producer sends for each interval.

INTERVAL_FORGET_THRESHOLDS = {
    "1m": timedelta(days=7),       # 7 days (yfinance limit)
    "2m": timedelta(days=60),      # 60 days
    "5m": timedelta(days=60),      # 60 days
    "15m": timedelta(days=60),     # 60 days
    "30m": timedelta(days=60),     # 60 days
    "60m": timedelta(days=730),    # 2 years
    "90m": timedelta(days=60),     # 60 days
    "1h": timedelta(days=730),     # 2 years
    "4h": timedelta(days=730),     # 2 years
    "1d": timedelta(days=730),     # 2 years (cap for "max")
    "5d": timedelta(days=730),     # 2 years
    "1wk": timedelta(days=730),    # 2 years
    "1mo": timedelta(days=730),    # 2 years
}

# Default forget threshold for unknown intervals
DEFAULT_FORGET_THRESHOLD = timedelta(days=365)

# Add backtesting_lib to path
sys.path.insert(0, str(Path(__file__).parent / 'backtesting_lib'))

from consumers.candle_consumer import CandleConsumer
from reducers import (
    trading_reducer,
    extract_total_pnl,
    extract_total_trades,
    extract_win_rate,
    extract_max_drawdown,
    extract_volatility,
    extract_sharpe,
    extract_profit_factor,
    extract_return_pct,
    extract_last_signal,
    extract_position,
    extract_candles_processed,
    extract_expectancy,
    extract_avg_win,
    extract_avg_loss,
)

# Import Redis cache for metrics storage
try:
    from redis_cache import get_report_observer
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis cache not available - metrics will only be logged")


# ============================================================================
# PATHWAY UDFs FOR STRATEGY METADATA EXTRACTION
# ============================================================================

@pw.udf
def extract_strategy_name(metadata: pw.Json) -> str:
    """Extract strategy name from file metadata."""
    try:
        path = metadata['path'].as_str()
        filename = Path(path).name
        return Path(filename).stem
    except Exception:
        return "unknown"


@pw.udf
def extract_strategy_interval(strategy_code: str) -> str:
    """
    Extract interval from strategy file header.
    Format: # interval: 1h
    Default: 1h
    """
    try:
        match = re.search(r'^#\s*interval:\s*(\S+)', strategy_code, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).lower()
    except Exception:
        pass
    return "1h"  # Default interval


@pw.udf
def extract_strategy_lookback(strategy_code: str) -> str:
    """
    Extract lookback period from strategy file header.
    Format: # lookback: 6mo
    Default: 1y
    """
    try:
        match = re.search(r'^#\s*lookback:\s*(\S+)', strategy_code, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).lower()
    except Exception:
        pass
    return "1y"  # Default lookback


# ============================================================================
# PIPELINE
# ============================================================================

def create_backtesting_pipeline(
    topic: str = "candles",
    strategies_folder: str = "./strategies/"
):
    """
    Create the streaming backtesting pipeline.
    
    Architecture:
    1. CandleConsumer reads candles from Kafka (multi-symbol, multi-interval)
    2. Strategies loaded from folder with interval/lookback metadata
    3. Natural join on interval: each strategy only sees matching candles
    4. Group by (strategy, symbol), reduce with trading_reducer
    5. Lookback filtering inside reducer
    6. Extract metrics per strategy per symbol and push to Redis cache
    """
    
    # ===== INPUT: Candles from Kafka via CandleConsumer =====
    candle_consumer = CandleConsumer(topic_name=topic)
    candles = candle_consumer.consume()
    # candles_raw = candle_consumer.consume()
    
    # # ===== MEMORY MANAGEMENT: Apply forget() with per-interval thresholds =====
    # # Each interval has different forget threshold based on producer's yfinance limits
    # # Using internal _forget with threshold_column for per-row thresholds
    
    # # UDF to parse timestamp string to datetime
    # @pw.udf
    # def parse_timestamp(ts_str: str) -> pw.DateTimeUtc:
    #     """Parse timestamp string to datetime for forget()."""
    #     from dateutil import parser
    #     try:
    #         dt = parser.parse(ts_str)
    #         # Convert to UTC if timezone-aware
    #         if dt.tzinfo is not None:
    #             import pytz
    #             dt = dt.astimezone(pytz.UTC)
    #         return dt
    #     except Exception:
    #         return datetime.now()
    
    # # UDF to get forget threshold based on interval
    # @pw.udf
    # def get_forget_threshold(interval: str) -> pw.DateTimeNaive:
    #     """Get forget threshold timedelta based on interval."""
    #     threshold = INTERVAL_FORGET_THRESHOLDS.get(
    #         interval.lower(), 
    #         DEFAULT_FORGET_THRESHOLD
    #     )
    #     # Return as timedelta (will be added to timestamp)
    #     return threshold
    
    # # Add parsed timestamp and compute per-interval threshold column
    # candles = candles_raw.with_columns(
    #     _timestamp_dt=parse_timestamp(pw.this.timestamp),
    #     _forget_threshold=get_forget_threshold(pw.this.interval)
    # )
    
    # # Compute threshold column: timestamp + threshold (when to forget this candle)
    # # A candle is forgotten when: max(timestamp) > _timestamp_dt + _forget_threshold
    # candles = candles.with_columns(
    #     _forget_at=pw.this._timestamp_dt + pw.this._forget_threshold
    # )
    
    # # Apply _forget with per-row threshold column
    # # Internal API: _forget(threshold_column, time_column, mark_forgetting_records)
    # candles = candles._forget(
    #     threshold_column=pw.this._forget_at,
    #     time_column=pw.this._timestamp_dt,
    #     mark_forgetting_records=False
    # )
    # print(f"🧹 Memory bounded: per-interval forget thresholds (1m→7d, 5m→60d, 1h→2y, 1d→2y)")
    
    # ===== INPUT: Strategies from folder =====
    print(f"📁 Strategies: {strategies_folder}")
    
    strategy_files = pw.io.fs.read(
        path=strategies_folder,
        format="plaintext_by_file",
        mode="streaming",
        with_metadata=True
    )
    
    # Extract strategy metadata (name, interval, lookback)
    strategies = strategy_files.select(
        strategy_name=extract_strategy_name(pw.this._metadata),
        strategy_code=pw.this.data,
        interval=extract_strategy_interval(pw.this.data),
        lookback=extract_strategy_lookback(pw.this.data)
    )
    
    # ===== NATURAL JOIN ON INTERVAL =====
    # Each strategy only receives candles matching its preferred interval
    candles_with_strategies = candles.join(
        strategies,
        pw.left.interval == pw.right.interval
    ).select(
        symbol=candles.symbol,
        interval=candles.interval,
        timestamp=candles.timestamp,
        open=candles.open,
        high=candles.high,
        low=candles.low,
        close=candles.close,
        volume=candles.volume,
        strategy_name=strategies.strategy_name,
        strategy_code=strategies.strategy_code,
        lookback=strategies.lookback
    )
    
    # ===== GROUP BY (strategy, symbol) & REDUCE =====
    # Interval is implicit (already filtered by join)
    # Lookback passed to reducer for time-based filtering
    # Note: Use pw.reducers.any() instead of latest() to handle deletions gracefully
    results = candles_with_strategies.groupby(
        pw.this.strategy_name, pw.this.symbol
    ).reduce(
        strategy_name=pw.this.strategy_name,
        symbol=pw.this.symbol,
        interval=pw.reducers.any(pw.this.interval),
        lookback=pw.reducers.any(pw.this.lookback),
        state=trading_reducer(
            pw.this.timestamp,
            pw.this.open,
            pw.this.high,
            pw.this.low,
            pw.this.close,
            pw.this.volume,
            pw.this.strategy_code,
            pw.this.lookback
        )
    )
    
    # ===== EXTRACT METRICS =====
    metrics = results.select(
        strategy=pw.this.strategy_name,
        symbol=pw.this.symbol,
        interval=pw.this.interval,
        lookback=pw.this.lookback,
        total_pnl=extract_total_pnl(pw.this.state),
        total_trades=extract_total_trades(pw.this.state),
        win_rate=extract_win_rate(pw.this.state),
        max_drawdown=extract_max_drawdown(pw.this.state),
        volatility=extract_volatility(pw.this.state),
        sharpe_ratio=extract_sharpe(pw.this.state),
        profit_factor=extract_profit_factor(pw.this.state),
        return_pct=extract_return_pct(pw.this.state),
        expectancy=extract_expectancy(pw.this.state),
        avg_win=extract_avg_win(pw.this.state),
        avg_loss=extract_avg_loss(pw.this.state),
        last_signal=extract_last_signal(pw.this.state),
        position=extract_position(pw.this.state),
        candles_processed=extract_candles_processed(pw.this.state)
    )
    
    # ===== OUTPUT: Stream to Redis cache (if available) =====
    if REDIS_AVAILABLE:
        # Format metrics for Redis (using dedicated RedisBacktestingObserver)
        import json
        
        @pw.udf
        def format_metrics(
            total_pnl: float, total_trades: int, win_rate: float,
            max_drawdown: float, volatility: float, sharpe_ratio: float,
            profit_factor: float, return_pct: float, expectancy: float,
            avg_win: float, avg_loss: float, last_signal: str, 
            position: str, candles_processed: int, lookback: str
        ) -> str:
            """Format all metrics as JSON."""
            return json.dumps({
                "total_pnl": round(total_pnl, 2),
                "total_trades": total_trades,
                "win_rate": round(win_rate, 4),
                "max_drawdown": round(max_drawdown, 4),
                "volatility": round(volatility, 4),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "profit_factor": round(profit_factor, 4),
                "return_pct": round(return_pct, 4),
                "expectancy": round(expectancy, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "last_signal": last_signal,
                "position": position,
                "candles_processed": candles_processed,
                "lookback": lookback
            })
        
        backtesting_metrics = metrics.select(
            strategy=pw.this.strategy,
            symbol=pw.this.symbol,
            interval=pw.this.interval,
            metrics=format_metrics(
                pw.this.total_pnl, pw.this.total_trades, pw.this.win_rate,
                pw.this.max_drawdown, pw.this.volatility, pw.this.sharpe_ratio,
                pw.this.profit_factor, pw.this.return_pct, pw.this.expectancy,
                pw.this.avg_win, pw.this.avg_loss, pw.this.last_signal,
                pw.this.position, pw.this.candles_processed, pw.this.lookback
            ),
            last_updated=pw.this.candles_processed
        ).groupby(pw.this.strategy, pw.this.symbol).reduce(
            strategy=pw.this.strategy,
            symbol=pw.this.symbol,
            interval=pw.reducers.any(pw.this.interval),
            metrics=pw.reducers.any(pw.this.metrics),
            last_updated=pw.reducers.max(pw.this.last_updated)
        )
        
        backtesting_observer = get_report_observer("backtesting")
        pw.io.python.write(
            backtesting_metrics,
            backtesting_observer,
            name="backtesting_metrics_stream",
        )
        print("📤 Streaming backtesting metrics to Redis cache")
    
    return metrics


def main():
    """Main entry point for backtesting pipeline."""
    load_dotenv()
    
    # Configuration from environment
    topic = os.getenv("CANDLE_KAFKA_TOPIC", "candles")
    strategies_folder = os.getenv("STRATEGIES_DIR", "./strategies/")
    
    print("=" * 70)
    print("🚀 PATHWAY STREAMING BACKTESTER (v2.0)")
    print("=" * 70)
    print(f"  Topic: {topic}")
    print(f"  Strategies: {strategies_folder}")
    print(f"  Redis: {'Available' if REDIS_AVAILABLE else 'Not available'}")
    print("=" * 70)
    
    # Create pipeline
    create_backtesting_pipeline(
        topic=topic,
        strategies_folder=strategies_folder
    )
    
    print("\n✅ Backtesting Pipeline initialized")
    print("   - Strategies specify interval + lookback in file header")
    print("   - Natural join on interval (no cartesian explosion)")
    print("   - Group by (strategy, symbol) for per-stock metrics")
    print("   - Lookback filtering for historical window")
    print("   - Metrics cached in Redis (key: backtesting:{strategy}:{symbol}:{interval})")
    print("\n🚀 Starting stream processing...")
    
    persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")

    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=60000  # Snapshot every 60 seconds
        )
    )


if __name__ == "__main__":
    main()
