"""
Pathway Reducers - Incremental Version

Uses stateful_many reducer with incremental state updates.
All operations are O(1) per candle.
"""

import pathway as pw
import numpy as np
from typing import Optional, List, Tuple

from trading_state import TradingState, process_single_candle


# ============================================================================
# STATEFUL REDUCER
# ============================================================================

@pw.reducers.stateful_many
def trading_reducer(
    state_json: Optional[str],
    rows: List[Tuple[List, int]]
) -> Optional[str]:
    """
    Stateful reducer for incremental backtesting.
    
    Args:
        state_json: Previous state as JSON string (None if first call)
        rows: List of (row_values, count) tuples
              - row_values = [timestamp, open, high, low, close, volume, strategy_code]
              - count > 0 for insertions, count < 0 for deletions
    
    Processes candles one at a time, updating state incrementally.
    All indicator and metric calculations are O(1).
    """
    # Initialize or restore state
    if state_json is None:
        trading_state = TradingState.initial()
    else:
        trading_state = TradingState.from_json(state_json)
    
    # Collect all candles from rows
    candles_to_process = []
    strategy_code = None
    
    for row, count in rows:
        # row = [timestamp, open, high, low, close, volume, strategy_code]
        timestamp = row[0]
        
        # Skip rows with None values (can happen during cross-join initialization)
        if row[1] is None or row[4] is None:
            continue
            
        open_price = float(row[1])
        high = float(row[2])
        low = float(row[3])
        close = float(row[4])
        volume = float(row[5])
        strategy_code = row[6]  # Same for all rows in a group
        
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
    candles_to_process.sort(key=lambda x: x['timestamp'])
    
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
