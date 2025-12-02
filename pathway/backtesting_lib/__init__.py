"""
Backtesting Library for Pathway Streaming Pipeline

Contains:
- indicators.py: O(1) incremental technical indicators
- trading_state.py: Trading state machine with SL/TP/trailing stops
- reducers.py: Pathway stateful reducers for incremental backtesting
- metrics.py: Performance metrics calculations
"""

from .indicators import IncrementalIndicators
from .trading_state import TradingState, process_single_candle
from .reducers import (
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

__all__ = [
    "IncrementalIndicators",
    "TradingState",
    "process_single_candle",
    "trading_reducer",
    "extract_total_pnl",
    "extract_total_trades",
    "extract_win_rate",
    "extract_max_drawdown",
    "extract_volatility",
    "extract_sharpe",
    "extract_profit_factor",
    "extract_return_pct",
    "extract_last_signal",
    "extract_position",
    "extract_candles_processed",
    "extract_expectancy",
    "extract_avg_win",
    "extract_avg_loss",
]
