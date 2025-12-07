"""
Pathway Reducers - Incremental Version with Lookback Filtering

Uses stateful_many reducer with incremental state updates.
All operations are O(1) per candle.

Lookback Filtering:
- Each strategy specifies a lookback period (e.g., "1y", "6mo", "1mo")
- On batch arrival, candles outside lookback window are filtered out
- For live streaming (1 candle at a time), this is a no-op
"""

import pathway as pw
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, List, Tuple

from trading_state import TradingState, process_single_candle


# ============================================================================
# LOOKBACK PERIOD PARSING
# ============================================================================

def parse_lookback_to_timedelta(lookback: str) -> timedelta:
    """
    Parse lookback string to timedelta.
    
    Supported formats:
    - "7d", "30d" -> days
    - "1mo", "3mo", "6mo" -> months
    - "1y", "2y" -> years
    - "max" -> very large (10 years)
    
    Returns timedelta for filtering.
    """
    lookback = lookback.lower().strip()
    
    if lookback == "max":
        return timedelta(days=3650)  # 10 years
    
    # Try parsing days: 7d, 30d, 60d
    if lookback.endswith('d'):
        try:
            days = int(lookback[:-1])
            return timedelta(days=days)
        except ValueError:
            pass
    
    # Try parsing months: 1mo, 3mo, 6mo
    if lookback.endswith('mo'):
        try:
            months = int(lookback[:-2])
            return timedelta(days=months * 30)  # Approximate
        except ValueError:
            pass
    
    # Try parsing years: 1y, 2y
    if lookback.endswith('y'):
        try:
            years = int(lookback[:-1])
            return timedelta(days=years * 365)  # Approximate
        except ValueError:
            pass
    
    # Default: 1 year
    return timedelta(days=365)


def filter_candles_by_lookback(candles: List[dict], lookback: str) -> List[dict]:
    """
    Filter candles to only include those within lookback period from latest candle.
    
    Args:
        candles: List of candle dicts with 'timestamp' key
        lookback: Lookback period string (e.g., "1y", "6mo")
    
    Returns:
        Filtered list of candles within lookback window
    """
    if not candles:
        return candles
    
    # Find the latest timestamp
    def parse_ts(ts_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        try:
            # Try ISO format first
            return datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
        except:
            try:
                # Try common formats
                return datetime.strptime(str(ts_str)[:19], '%Y-%m-%d %H:%M:%S')
            except:
                # Fallback: use string comparison (works for ISO-ish formats)
                return datetime.min
    
    # Sort and find latest
    sorted_candles = sorted(candles, key=lambda c: str(c['timestamp']))
    latest_ts = parse_ts(sorted_candles[-1]['timestamp'])

    # Calculate cutoff
    lookback_delta = parse_lookback_to_timedelta(lookback)
    cutoff_ts = latest_ts - lookback_delta

    # Filter candles
    filtered = [c for c in sorted_candles if parse_ts(c['timestamp']) >= cutoff_ts]
    
    return filtered


# ============================================================================
# STATEFUL REDUCER
# ============================================================================

@pw.reducers.stateful_many
def trading_reducer(
    state_json: Optional[str],
    rows: List[Tuple[List, int]]
) -> Optional[str]:
    """
    Stateful reducer for incremental backtesting with lookback filtering.
    
    Args:
        state_json: Previous state as JSON string (None if first call)
        rows: List of (row_values, count) tuples
              - row_values = [timestamp, open, high, low, close, volume, strategy_code, lookback, interval]
              - count > 0 for insertions, count < 0 for deletions
    
    Processes candles one at a time, updating state incrementally.
    Lookback filtering is applied to batch processing.
    All indicator and metric calculations are O(1).
    """
    # Extract interval from first row (same for all rows in group)
    interval = '1d'  # Default
    for row, count in rows:
        if len(row) > 8 and row[8] is not None:
            interval = str(row[8])
            break
    
    # Initialize or restore state
    if state_json is None:
        trading_state = TradingState.initial(interval=interval)
    else:
        trading_state = TradingState.from_json(state_json)
    
    # Collect all candles from rows
    candles_to_process = []
    strategy_code = None
    lookback = "1y"  # Default
    
    for row, count in rows:
        # row = [timestamp, open, high, low, close, volume, strategy_code, lookback]
        
        # Skip deletions from forget() - we can't reverse executed trades
        if count <= 0:
            continue
        
        # Validate row structure
        if not isinstance(row, (list, tuple)) or len(row) < 7:
            print(f"⚠️ Skipping malformed row (expected 7+ elements): {row}")
            continue
        
        timestamp = row[0]
        
        # Skip rows with None/invalid OHLCV values
        if row[1] is None or row[4] is None:
            continue
        
        # Validate and parse OHLCV values
        try:
            open_price = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            volume = float(row[5])
            
            # Validate OHLCV constraints
            if any(v <= 0 or not np.isfinite(v) for v in [open_price, high, low, close]):
                print(f"⚠️ Skipping candle with invalid OHLCV values: {row[:6]}")
                continue
            
            if volume < 0 or not np.isfinite(volume):
                volume = 0.0  # Allow zero volume, just fix negative
                
        except (ValueError, TypeError) as e:
            print(f"⚠️ Skipping candle with unparseable values: {row[:6]} - {e}")
            continue
        
        strategy_code = row[6]  # Same for all rows in a group
        
        # Extract lookback (may be at index 7)
        if len(row) > 7 and row[7] is not None:
            lookback = str(row[7])
        
        is_insertion = count > 0
        
        for _ in range(abs(count)):
            candles_to_process.append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
                'is_insertion': is_insertion
            })
    
    # Sort by timestamp for proper ordering
    candles_to_process.sort(key=lambda x: str(x['timestamp']))
    
    # Apply lookback filtering (only relevant for batch processing)
    # For live streaming with 1 candle, this is a no-op
    if len(candles_to_process) > 1:
        candles_to_process = filter_candles_by_lookback(candles_to_process, lookback)
    
    # Process each candle incrementally
    for candle in candles_to_process:
        trading_state = process_single_candle(
            trading_state,
            str(candle['timestamp']),
            candle['open'],
            candle['high'],
            candle['low'],
            candle['close'],
            candle['volume'],
            strategy_code,
            candle['is_insertion']
        )
    
    return trading_state.to_json()


# ============================================================================
# METRIC EXTRACTION UDFs
# ============================================================================

@pw.udf
def extract_total_pnl(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('total_pnl', 0.0)


@pw.udf
def extract_total_trades(state_json: Optional[str]) -> int:
    if state_json is None:
        return 0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('total_trades', 0)


@pw.udf
def extract_win_rate(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('win_rate', 0.0)


@pw.udf
def extract_max_drawdown(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('max_drawdown', 0.0)


@pw.udf
def extract_volatility(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('volatility', 0.0)


@pw.udf
def extract_sharpe(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('sharpe_ratio', 0.0)


@pw.udf
def extract_profit_factor(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('profit_factor', 0.0)


@pw.udf
def extract_return_pct(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('return_pct', 0.0)


@pw.udf
def extract_last_signal(state_json: Optional[str]) -> str:
    if state_json is None:
        return "NONE"
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('last_signal', 'NONE')


@pw.udf
def extract_position(state_json: Optional[str]) -> str:
    if state_json is None:
        return "NONE"
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('position', 'NONE')


@pw.udf
def extract_candles_processed(state_json: Optional[str]) -> int:
    if state_json is None:
        return 0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('candles_processed', 0)


@pw.udf
def extract_expectancy(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('expectancy', 0.0)


@pw.udf
def extract_avg_win(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('avg_win', 0.0)


@pw.udf
def extract_avg_loss(state_json: Optional[str]) -> float:
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('avg_loss', 0.0)


@pw.udf
def extract_equity(state_json: Optional[str]) -> float:
    """Extract total portfolio value including unrealized P&L."""
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('equity', 0.0)


@pw.udf
def extract_equity_return_pct(state_json: Optional[str]) -> float:
    """Extract return % including unrealized P&L (matches backtesting.py)."""
    if state_json is None:
        return 0.0
    state = TradingState.from_json(state_json)
    return state.get_all_metrics().get('equity_return_pct', 0.0)

