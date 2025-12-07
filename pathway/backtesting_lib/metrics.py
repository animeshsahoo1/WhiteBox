"""
Incremental Metrics Calculation

All metrics are O(1) per update using:
- Running sums for totals
- Welford's algorithm for variance/std dev
- Simple counters for trade statistics
"""

import json
import math
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class MetricsState:
    """
    Holds all running state for incremental metrics calculation.
    Every metric is O(1) per trade/candle update.
    
    Enhanced with:
    - Stop-loss and take-profit tracking
    - Trailing stop support
    - Position sizing
    - Short selling
    - Exit reason tracking
    """
    
    # === Trade Counts ===
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # === Exit Reason Counts ===
    exits_by_signal: int = 0
    exits_by_stop_loss: int = 0
    exits_by_take_profit: int = 0
    exits_by_trailing_stop: int = 0
    
    # === PnL Tracking ===
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    
    # === Capital Tracking ===
    initial_capital: float = 10000.0
    current_capital: float = 10000.0
    
    # === Welford's Algorithm for Variance (Sharpe/Volatility) ===
    # Online algorithm: M2 = sum of squared differences from mean
    welford_count: int = 0
    welford_mean: float = 0.0
    welford_m2: float = 0.0
    
    # === Drawdown Tracking ===
    peak_equity: float = 10000.0
    max_drawdown: float = 0.0
    
    # === Consecutive Win/Loss Streaks ===
    current_streak: int = 0
    current_streak_type: str = 'NONE'  # 'WIN', 'LOSS', 'NONE'
    max_win_streak: int = 0
    max_loss_streak: int = 0
    
    # === Position State ===
    position_type: str = 'NONE'  # 'NONE', 'LONG', 'SHORT'
    entry_price: float = 0.0
    entry_time: str = ''
    position_size: float = 1.0  # Fraction of capital (0-1)
    position_units: float = 0.0  # Actual units held
    
    # === Stop-Loss / Take-Profit ===
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    trailing_stop_pct: float = 0.0  # 0 = disabled, e.g. 0.02 = 2%
    trailing_stop_price: float = 0.0  # Current trailing stop level
    highest_since_entry: float = 0.0  # For trailing stop (long)
    lowest_since_entry: float = 0.0  # For trailing stop (short)
    
    # === Signal State ===
    last_signal: str = 'NONE'
    pending_signal: dict = field(default_factory=dict)  # Full signal dict
    last_price: float = 0.0
    last_exit_reason: str = 'NONE'  # 'signal', 'stop_loss', 'take_profit', 'trailing_stop'
    
    # === Configuration ===
    commission: float = 0.001
    default_position_size: float = 1.0  # Default fraction of capital to use
    
    # === Candle Count ===
    candles_processed: int = 0
    
    # === Equity-Curve Welford's Algorithm (for industry-standard Sharpe) ===
    # Tracks per-bar equity returns rather than per-trade - more accurate measure
    equity_welford_count: int = 0
    equity_welford_mean: float = 0.0
    equity_welford_m2: float = 0.0
    previous_equity: float = 10000.0
    interval: str = '1d'  # For correct annualization factor
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MetricsState':
        data = json.loads(json_str)
        return cls(**data)
    
    @classmethod
    def initial(cls, initial_capital: float = 10000.0, commission: float = 0.001, interval: str = '1d') -> 'MetricsState':
        return cls(
            initial_capital=initial_capital,
            current_capital=initial_capital,
            peak_equity=initial_capital,
            previous_equity=initial_capital,
            commission=commission,
            interval=interval
        )


def record_trade(state: MetricsState, pnl: float, exit_reason: str = 'signal') -> MetricsState:
    """
    Record a completed trade - O(1).
    Updates all trade-related metrics incrementally.
    
    Args:
        state: Current metrics state
        pnl: Profit/loss from the trade
        exit_reason: One of 'signal', 'stop_loss', 'take_profit', 'trailing_stop'
    """
    state.total_trades += 1
    state.total_pnl += pnl
    state.current_capital += pnl
    state.last_exit_reason = exit_reason
    
    # Track exit reasons
    if exit_reason == 'signal':
        state.exits_by_signal += 1
    elif exit_reason == 'stop_loss':
        state.exits_by_stop_loss += 1
    elif exit_reason == 'take_profit':
        state.exits_by_take_profit += 1
    elif exit_reason == 'trailing_stop':
        state.exits_by_trailing_stop += 1
    
    # Win/Loss tracking
    if pnl > 0:
        state.winning_trades += 1
        state.gross_profit += pnl
        
        # Streak tracking
        if state.current_streak_type == 'WIN':
            state.current_streak += 1
        else:
            state.current_streak = 1
            state.current_streak_type = 'WIN'
        state.max_win_streak = max(state.max_win_streak, state.current_streak)
    else:
        state.losing_trades += 1
        state.gross_loss += abs(pnl)
        
        # Streak tracking
        if state.current_streak_type == 'LOSS':
            state.current_streak += 1
        else:
            state.current_streak = 1
            state.current_streak_type = 'LOSS'
        state.max_loss_streak = max(state.max_loss_streak, state.current_streak)
    
    # Welford's algorithm for online variance
    state.welford_count += 1
    delta = pnl - state.welford_mean
    state.welford_mean += delta / state.welford_count
    delta2 = pnl - state.welford_mean
    state.welford_m2 += delta * delta2
    
    return state


def update_equity(state: MetricsState, current_price: float, high: float = None, low: float = None) -> MetricsState:
    """
    Update equity and drawdown tracking - O(1).
    Called on each candle to track mark-to-market equity.
    Also updates trailing stop levels if position is open.
    
    Args:
        state: Current metrics state
        current_price: Current close price
        high: High of current candle (for trailing stop updates)
        low: Low of current candle (for trailing stop updates)
    """
    if high is None:
        high = current_price
    if low is None:
        low = current_price
    
    # Calculate current equity (mark-to-market)
    equity = state.current_capital
    if state.position_type == 'LONG':
        unrealized_pnl = (current_price - state.entry_price) * state.position_units
        equity += unrealized_pnl
        
        # Update highest price since entry (for trailing stop)
        state.highest_since_entry = max(state.highest_since_entry, high)
        
        # Update trailing stop if enabled
        if state.trailing_stop_pct > 0:
            new_trailing_stop = state.highest_since_entry * (1 - state.trailing_stop_pct)
            state.trailing_stop_price = max(state.trailing_stop_price, new_trailing_stop)
            
    elif state.position_type == 'SHORT':
        unrealized_pnl = (state.entry_price - current_price) * state.position_units
        equity += unrealized_pnl
        
        # Update lowest price since entry (for trailing stop)
        state.lowest_since_entry = min(state.lowest_since_entry, low) if state.lowest_since_entry > 0 else low
        
        # Update trailing stop if enabled
        if state.trailing_stop_pct > 0:
            new_trailing_stop = state.lowest_since_entry * (1 + state.trailing_stop_pct)
            if state.trailing_stop_price == 0:
                state.trailing_stop_price = new_trailing_stop
            else:
                state.trailing_stop_price = min(state.trailing_stop_price, new_trailing_stop)
    
    # Update peak and drawdown
    if equity > state.peak_equity:
        state.peak_equity = equity
    
    if state.peak_equity > 0:
        drawdown = (state.peak_equity - equity) / state.peak_equity
        state.max_drawdown = max(state.max_drawdown, drawdown)
    
    state.last_price = current_price
    state.candles_processed += 1
    
    # Update equity-curve return tracking (Welford's algorithm for per-bar returns)
    if state.previous_equity > 0:
        equity_return = (equity - state.previous_equity) / state.previous_equity
        
        # Welford's online algorithm for mean and variance
        state.equity_welford_count += 1
        delta = equity_return - state.equity_welford_mean
        state.equity_welford_mean += delta / state.equity_welford_count
        delta2 = equity_return - state.equity_welford_mean
        state.equity_welford_m2 += delta * delta2
    
    state.previous_equity = equity
    
    return state


def get_metrics(state: MetricsState) -> dict:
    """
    Extract all metrics from state - O(1).
    """
    metrics = {
        'total_trades': state.total_trades,
        'winning_trades': state.winning_trades,
        'losing_trades': state.losing_trades,
        'win_rate': state.winning_trades / state.total_trades if state.total_trades > 0 else 0.0,
        'total_pnl': state.total_pnl,
        'gross_profit': state.gross_profit,
        'gross_loss': state.gross_loss,
        'max_drawdown': state.max_drawdown,
        'current_capital': state.current_capital,
        'return_pct': (state.current_capital - state.initial_capital) / state.initial_capital * 100,
    }
    
    # Calculate unrealized P&L for equity metrics (matches backtesting.py behavior)
    unrealized_pnl = 0.0
    if state.position_type == 'LONG':
        unrealized_pnl = (state.last_price - state.entry_price) * state.position_units
    elif state.position_type == 'SHORT':
        unrealized_pnl = (state.entry_price - state.last_price) * state.position_units
    
    metrics['equity'] = state.current_capital + unrealized_pnl
    metrics['equity_return_pct'] = (metrics['equity'] - state.initial_capital) / state.initial_capital * 100
    
    # Profit Factor
    if state.gross_loss > 0:
        metrics['profit_factor'] = state.gross_profit / state.gross_loss
    else:
        metrics['profit_factor'] = 9999.0 if state.gross_profit > 0 else 0.0  # Avoid inf for JSON
    
    # Volatility (std dev of trade PnLs) using Welford's result
    if state.welford_count > 1:
        variance = state.welford_m2 / (state.welford_count - 1)
        metrics['volatility'] = math.sqrt(variance) if variance > 0 else 0.0
    else:
        metrics['volatility'] = 0.0
    
    # Equity-Curve Sharpe Ratio (industry standard - per-bar returns)
    # Uses proper annualization factor based on interval
    annualization_factors = {
        '1m': math.sqrt(252 * 6.5 * 60),   # Minutes per year
        '5m': math.sqrt(252 * 6.5 * 12),   # 5-min bars per year
        '15m': math.sqrt(252 * 6.5 * 4),   # 15-min bars per year
        '30m': math.sqrt(252 * 6.5 * 2),   # 30-min bars per year
        '1h': math.sqrt(252 * 6.5),        # Hours per year (~1638)
        '4h': math.sqrt(252 * 1.625),      # 4-hour bars per year
        '1d': math.sqrt(252),              # Trading days per year
        '1w': math.sqrt(52),               # Weeks per year
    }
    ann_factor = annualization_factors.get(state.interval, math.sqrt(252))
    
    if state.equity_welford_count > 1:
        equity_variance = state.equity_welford_m2 / (state.equity_welford_count - 1)
        equity_std = math.sqrt(equity_variance) if equity_variance > 0 else 0.0
        
        if equity_std > 0:
            # Sharpe = (mean return / std return) * annualization factor
            metrics['sharpe_ratio'] = (state.equity_welford_mean / equity_std) * ann_factor
        else:
            metrics['sharpe_ratio'] = 0.0
    else:
        metrics['sharpe_ratio'] = 0.0
    
    # Sortino Ratio (would need separate downside deviation tracking)
    # For now, using simplified version
    
    # Average Win/Loss
    metrics['avg_win'] = state.gross_profit / state.winning_trades if state.winning_trades > 0 else 0.0
    metrics['avg_loss'] = state.gross_loss / state.losing_trades if state.losing_trades > 0 else 0.0
    
    # Expectancy
    if state.total_trades > 0:
        win_rate = state.winning_trades / state.total_trades
        loss_rate = state.losing_trades / state.total_trades
        metrics['expectancy'] = (win_rate * metrics['avg_win']) - (loss_rate * metrics['avg_loss'])
    else:
        metrics['expectancy'] = 0.0
    
    # Streaks
    metrics['max_win_streak'] = state.max_win_streak
    metrics['max_loss_streak'] = state.max_loss_streak
    
    # Exit reason breakdown
    metrics['exits_by_signal'] = state.exits_by_signal
    metrics['exits_by_stop_loss'] = state.exits_by_stop_loss
    metrics['exits_by_take_profit'] = state.exits_by_take_profit
    metrics['exits_by_trailing_stop'] = state.exits_by_trailing_stop
    metrics['last_exit_reason'] = state.last_exit_reason
    
    # Position info
    metrics['position'] = state.position_type
    metrics['position_size'] = state.position_size
    metrics['position_units'] = state.position_units
    metrics['entry_price'] = state.entry_price
    metrics['stop_loss_price'] = state.stop_loss_price
    metrics['take_profit_price'] = state.take_profit_price
    metrics['trailing_stop_price'] = state.trailing_stop_price
    metrics['last_signal'] = state.last_signal
    metrics['last_price'] = state.last_price
    metrics['candles_processed'] = state.candles_processed
    
    return metrics
