"""
Pathway Streaming Backtesting Pipeline

Consumes candles from Kafka via CandleConsumer, runs backtesting for all strategies,
and pushes real-time metrics to Redis cache.

Usage:
    python main_backtesting.py

Environment Variables:
    CANDLE_KAFKA_TOPIC: Topic for candle data (default: candles)
    STRATEGIES_DIR: Path to strategies folder (default: ./strategies)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

import pathway as pw

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
# PATHWAY UDFs
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
    1. CandleConsumer reads candles from Kafka (like other consumers)
    2. Strategies loaded from folder (streaming - new files picked up)
    3. Cross-join: each candle × each strategy
    4. Group by (strategy, symbol), reduce with trading_reducer (O(1) per candle)
    5. Extract metrics per strategy per symbol and push to Redis cache
    """
    
    # ===== INPUT: Candles from Kafka via CandleConsumer =====
    candle_consumer = CandleConsumer(topic_name=topic)
    candles = candle_consumer.consume()
    
    # ===== INPUT: Strategies from folder =====
    print(f"📁 Strategies: {strategies_folder}")
    
    strategy_files = pw.io.fs.read(
        path=strategies_folder,
        format="plaintext_by_file",
        mode="streaming",
        with_metadata=True
    )
    
    strategies = strategy_files.select(
        strategy_name=extract_strategy_name(pw.this._metadata),
        strategy_code=pw.this.data
    )
    
    # ===== CROSS JOIN =====
    candles_with_strategies = candles.join(strategies).select(
        symbol=candles.symbol,
        interval=candles.interval,
        timestamp=candles.timestamp,
        open=candles.open,
        high=candles.high,
        low=candles.low,
        close=candles.close,
        volume=candles.volume,
        strategy_name=strategies.strategy_name,
        strategy_code=strategies.strategy_code
    )
    
    # ===== GROUP BY (strategy, symbol, interval) & REDUCE (O(1) incremental) =====
    results = candles_with_strategies.groupby(
        pw.this.strategy_name, pw.this.symbol, pw.this.interval
    ).reduce(
        strategy_name=pw.this.strategy_name,
        symbol=pw.this.symbol,
        interval=pw.this.interval,
        state=trading_reducer(
            pw.this.timestamp,
            pw.this.open,
            pw.this.high,
            pw.this.low,
            pw.this.close,
            pw.this.volume,
            pw.this.strategy_code
        )
    )
    
    # ===== EXTRACT METRICS =====
    metrics = results.select(
        strategy=pw.this.strategy_name,
        symbol=pw.this.symbol,
        interval=pw.this.interval,
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
            position: str, candles_processed: int
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
                "candles_processed": candles_processed
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
                pw.this.position, pw.this.candles_processed
            ),
            last_updated=pw.this.candles_processed
        ).groupby(pw.this.strategy, pw.this.symbol, pw.this.interval).reduce(
            strategy=pw.this.strategy,
            symbol=pw.this.symbol,
            interval=pw.this.interval,
            metrics=pw.reducers.latest(pw.this.metrics),
            last_updated=pw.reducers.latest(pw.this.last_updated)
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
    print("🚀 PATHWAY STREAMING BACKTESTER")
    print("=" * 70)
    print(f"  Topic: {topic}")
    print(f"  Strategies: {strategies_folder}")
    print(f"  Redis: {'Available' if REDIS_AVAILABLE else 'Not available'}")
    print("=" * 70)
    
    # Create pipeline using CandleConsumer (like other pipelines)
    create_backtesting_pipeline(
        topic=topic,
        strategies_folder=strategies_folder
    )
    
    print("\n✅ Backtesting Pipeline initialized (Multi-Symbol, Multi-Interval)")
    print("   - CandleConsumer reads from Kafka (extracts symbol + interval)")
    print("   - Groups by (strategy, symbol, interval) for per-config metrics")
    print("   - Runs all strategies with O(1) incremental processing")
    print("   - Metrics cached in Redis (key: backtesting:{strategy}:{symbol}:{interval})")
    print("   - Keeps metrics for all configs ever tested!")
    print("\n🚀 Starting stream processing...")
    
    pw.run()


if __name__ == "__main__":
    main()
