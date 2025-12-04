"""
Incremental Technical Indicators

All indicators are O(1) per update - no recalculation from history.
Uses running sums, EMAs, and monotonic deques for efficiency.
"""

import json
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
import math


@dataclass
class IndicatorState:
    """
    Holds all running state for incremental indicator calculation.
    Every indicator is O(1) per candle update.
    """
    
    # Candle count for warmup tracking
    candle_count: int = 0
    
    # Current OHLC (most recent)
    current_open: float = 0.0
    current_high: float = 0.0
    current_low: float = 0.0
    current_close: float = 0.0
    prev_close: float = 0.0
    
    # === SMA State (rolling sums + circular buffers) ===
    # SMA_5
    sma_5_sum: float = 0.0
    sma_5_buffer: List[float] = field(default_factory=list)
    # SMA_10
    sma_10_sum: float = 0.0
    sma_10_buffer: List[float] = field(default_factory=list)
    # SMA_20
    sma_20_sum: float = 0.0
    sma_20_buffer: List[float] = field(default_factory=list)
    # SMA_50
    sma_50_sum: float = 0.0
    sma_50_buffer: List[float] = field(default_factory=list)
    # SMA_200
    sma_200_sum: float = 0.0
    sma_200_buffer: List[float] = field(default_factory=list)
    
    # === EMA State (just previous values) ===
    ema_9: float = float('nan')
    ema_12: float = float('nan')
    ema_26: float = float('nan')
    ema_9_initialized: bool = False
    ema_12_initialized: bool = False
    ema_26_initialized: bool = False
    
    # === RSI State (Wilder smoothing) ===
    rsi_avg_gain: float = 0.0
    rsi_avg_loss: float = 0.0
    rsi_initialized: bool = False
    rsi_init_gains: List[float] = field(default_factory=list)
    rsi_init_losses: List[float] = field(default_factory=list)
    
    # === MACD (uses EMA_12 and EMA_26) ===
    # MACD line = EMA_12 - EMA_26 (computed from above)
    # MACD signal = 9-period EMA of MACD line
    macd_signal_ema: float = float('nan')
    macd_signal_initialized: bool = False
    
    # === Bollinger Bands (rolling sum and sum of squares) ===
    bb_sum: float = 0.0
    bb_sum_sq: float = 0.0
    bb_buffer: List[float] = field(default_factory=list)
    
    # === ATR State (Wilder smoothing on True Range) ===
    atr_value: float = float('nan')
    atr_initialized: bool = False
    atr_init_tr: List[float] = field(default_factory=list)
    
    # === Stochastic/Williams %R (min/max deques) ===
    stoch_highs: List[float] = field(default_factory=list)  # Circular buffer
    stoch_lows: List[float] = field(default_factory=list)   # Circular buffer
    
    # === Stochastic %D (3-period SMA of %K) ===
    stoch_k_buffer: List[float] = field(default_factory=list)  # Last 3 %K values
    
    # === CCI State (rolling typical price) ===
    cci_tp_buffer: List[float] = field(default_factory=list)
    cci_tp_sum: float = 0.0
    
    # === ADX State (proper implementation with Wilder smoothing) ===
    adx_plus_dm_ema: float = 0.0
    adx_minus_dm_ema: float = 0.0
    adx_tr_ema: float = 0.0
    adx_dx_ema: float = 0.0
    adx_initialized: bool = False
    adx_init_plus_dm: List[float] = field(default_factory=list)
    adx_init_minus_dm: List[float] = field(default_factory=list)
    adx_init_tr: List[float] = field(default_factory=list)
    prev_high: float = 0.0
    prev_low: float = 0.0
    
    def to_json(self) -> str:
        """Serialize state to JSON"""
        data = asdict(self)
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'IndicatorState':
        """Deserialize state from JSON"""
        data = json.loads(json_str)
        return cls(**data)


def _update_sma(price: float, buffer: List[float], current_sum: float, period: int) -> tuple:
    """
    Incremental SMA update - O(1)
    Returns: (new_sma, new_sum, updated_buffer)
    """
    buffer.append(price)
    new_sum = current_sum + price
    
    if len(buffer) > period:
        dropped = buffer.pop(0)
        new_sum -= dropped
    
    if len(buffer) >= period:
        return new_sum / period, new_sum, buffer
    else:
        return float('nan'), new_sum, buffer


def _update_ema(price: float, prev_ema: float, period: int, initialized: bool, candle_count: int) -> tuple:
    """
    Incremental EMA update - O(1)
    Returns: (new_ema, is_initialized)
    """
    alpha = 2.0 / (period + 1)
    
    if not initialized:
        if candle_count < period:
            return float('nan'), False
        elif candle_count == period:
            # Initialize with first price (simplified - ideally use SMA)
            return price, True
        else:
            return price, True
    
    new_ema = alpha * price + (1 - alpha) * prev_ema
    return new_ema, True


def _wilder_smooth(prev_val: float, new_val: float, period: int) -> float:
    """Wilder's smoothing method - O(1)"""
    return (prev_val * (period - 1) + new_val) / period


def update_indicators(state: IndicatorState, open_price: float, high: float, 
                      low: float, close: float) -> IndicatorState:
    """
    Update all indicators incrementally with new candle - O(1) total.
    """
    state.candle_count += 1
    
    # Store previous values
    state.prev_close = state.current_close if state.candle_count > 1 else close
    prev_high = state.prev_high
    prev_low = state.prev_low
    
    # Update current OHLC
    state.current_open = open_price
    state.current_high = high
    state.current_low = low
    state.current_close = close
    
    # === Update SMAs (O(1) each) ===
    _, state.sma_5_sum, state.sma_5_buffer = _update_sma(
        close, state.sma_5_buffer, state.sma_5_sum, 5)
    _, state.sma_10_sum, state.sma_10_buffer = _update_sma(
        close, state.sma_10_buffer, state.sma_10_sum, 10)
    _, state.sma_20_sum, state.sma_20_buffer = _update_sma(
        close, state.sma_20_buffer, state.sma_20_sum, 20)
    _, state.sma_50_sum, state.sma_50_buffer = _update_sma(
        close, state.sma_50_buffer, state.sma_50_sum, 50)
    _, state.sma_200_sum, state.sma_200_buffer = _update_sma(
        close, state.sma_200_buffer, state.sma_200_sum, 200)
    
    # === Update EMAs (O(1) each) ===
    state.ema_9, state.ema_9_initialized = _update_ema(
        close, state.ema_9, 9, state.ema_9_initialized, state.candle_count)
    state.ema_12, state.ema_12_initialized = _update_ema(
        close, state.ema_12, 12, state.ema_12_initialized, state.candle_count)
    state.ema_26, state.ema_26_initialized = _update_ema(
        close, state.ema_26, 26, state.ema_26_initialized, state.candle_count)
    
    # === Update MACD Signal Line (9-period EMA of MACD line) - O(1) ===
    if state.ema_12_initialized and state.ema_26_initialized:
        macd_line = state.ema_12 - state.ema_26
        # Use same EMA logic for signal line
        if not state.macd_signal_initialized:
            # Initialize with first MACD value
            state.macd_signal_ema = macd_line
            state.macd_signal_initialized = True
        else:
            alpha = 2.0 / (9 + 1)
            state.macd_signal_ema = alpha * macd_line + (1 - alpha) * state.macd_signal_ema
    
    # === Update RSI (Wilder smoothing - O(1)) ===
    if state.candle_count > 1:
        delta = close - state.prev_close
        gain = max(0, delta)
        loss = max(0, -delta)
        
        if not state.rsi_initialized:
            state.rsi_init_gains.append(gain)
            state.rsi_init_losses.append(loss)
            
            if len(state.rsi_init_gains) >= 14:
                state.rsi_avg_gain = sum(state.rsi_init_gains) / 14
                state.rsi_avg_loss = sum(state.rsi_init_losses) / 14
                state.rsi_initialized = True
        else:
            state.rsi_avg_gain = _wilder_smooth(state.rsi_avg_gain, gain, 14)
            state.rsi_avg_loss = _wilder_smooth(state.rsi_avg_loss, loss, 14)
    
    # === Update Bollinger Bands (O(1) using sum and sum of squares) ===
    state.bb_buffer.append(close)
    state.bb_sum += close
    state.bb_sum_sq += close * close
    
    if len(state.bb_buffer) > 20:
        dropped = state.bb_buffer.pop(0)
        state.bb_sum -= dropped
        state.bb_sum_sq -= dropped * dropped
    
    # === Update ATR (Wilder smoothing - O(1)) ===
    if state.candle_count > 1:
        tr = max(
            high - low,
            abs(high - state.prev_close),
            abs(low - state.prev_close)
        )
        
        if not state.atr_initialized:
            state.atr_init_tr.append(tr)
            if len(state.atr_init_tr) >= 14:
                state.atr_value = sum(state.atr_init_tr) / 14
                state.atr_initialized = True
        else:
            state.atr_value = _wilder_smooth(state.atr_value, tr, 14)
    
    # === Update Stochastic/Williams %R buffers (O(1) amortized) ===
    state.stoch_highs.append(high)
    state.stoch_lows.append(low)
    if len(state.stoch_highs) > 14:
        state.stoch_highs.pop(0)
        state.stoch_lows.pop(0)
    
    # === Compute current %K and update %D buffer (for later averaging) ===
    if len(state.stoch_highs) >= 14:
        lowest_low = min(state.stoch_lows)
        highest_high = max(state.stoch_highs)
        if highest_high != lowest_low:
            current_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        else:
            current_k = 50.0
        
        # Store in %K buffer for %D calculation (3-period SMA of %K)
        state.stoch_k_buffer.append(current_k)
        if len(state.stoch_k_buffer) > 3:
            state.stoch_k_buffer.pop(0)
    
    # === Update CCI (O(1)) ===
    tp = (high + low + close) / 3
    state.cci_tp_buffer.append(tp)
    state.cci_tp_sum += tp
    if len(state.cci_tp_buffer) > 20:
        dropped = state.cci_tp_buffer.pop(0)
        state.cci_tp_sum -= dropped
    
    # === Update ADX (proper Wilder smoothing - O(1)) ===
    if state.candle_count > 1:
        # Calculate +DM and -DM
        up_move = high - prev_high
        down_move = prev_low - low
        
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0
        
        tr = max(high - low, abs(high - state.prev_close), abs(low - state.prev_close))
        
        if not state.adx_initialized:
            state.adx_init_plus_dm.append(plus_dm)
            state.adx_init_minus_dm.append(minus_dm)
            state.adx_init_tr.append(tr)
            
            if len(state.adx_init_tr) >= 14:
                state.adx_plus_dm_ema = sum(state.adx_init_plus_dm)
                state.adx_minus_dm_ema = sum(state.adx_init_minus_dm)
                state.adx_tr_ema = sum(state.adx_init_tr)
                state.adx_initialized = True
        else:
            state.adx_plus_dm_ema = _wilder_smooth(state.adx_plus_dm_ema, plus_dm, 14)
            state.adx_minus_dm_ema = _wilder_smooth(state.adx_minus_dm_ema, minus_dm, 14)
            state.adx_tr_ema = _wilder_smooth(state.adx_tr_ema, tr, 14)
    
    # Store for next iteration
    state.prev_high = high
    state.prev_low = low
    
    return state


def get_indicators(state: IndicatorState) -> Dict[str, float]:
    """
    Extract current indicator values from state.
    All calculations here are O(1).
    """
    indicators = {}
    
    # === SMAs ===
    indicators['sma_5'] = state.sma_5_sum / 5 if len(state.sma_5_buffer) >= 5 else float('nan')
    indicators['sma_10'] = state.sma_10_sum / 10 if len(state.sma_10_buffer) >= 10 else float('nan')
    indicators['sma_20'] = state.sma_20_sum / 20 if len(state.sma_20_buffer) >= 20 else float('nan')
    indicators['sma_50'] = state.sma_50_sum / 50 if len(state.sma_50_buffer) >= 50 else float('nan')
    indicators['sma_200'] = state.sma_200_sum / 200 if len(state.sma_200_buffer) >= 200 else float('nan')
    
    # === EMAs ===
    indicators['ema_9'] = state.ema_9 if state.ema_9_initialized else float('nan')
    indicators['ema_12'] = state.ema_12 if state.ema_12_initialized else float('nan')
    indicators['ema_26'] = state.ema_26 if state.ema_26_initialized else float('nan')
    
    # === RSI ===
    if state.rsi_initialized and state.rsi_avg_loss > 0:
        rs = state.rsi_avg_gain / state.rsi_avg_loss
        indicators['rsi_14'] = 100 - (100 / (1 + rs))
    elif state.rsi_initialized and state.rsi_avg_loss == 0:
        indicators['rsi_14'] = 100.0
    else:
        indicators['rsi_14'] = float('nan')
    
    # === MACD ===
    if state.ema_12_initialized and state.ema_26_initialized:
        indicators['macd_line'] = state.ema_12 - state.ema_26
        # MACD Signal line (9-period EMA of MACD line)
        if state.macd_signal_initialized:
            indicators['macd_signal'] = state.macd_signal_ema
            indicators['macd_histogram'] = indicators['macd_line'] - indicators['macd_signal']
        else:
            indicators['macd_signal'] = float('nan')
            indicators['macd_histogram'] = float('nan')
    else:
        indicators['macd_line'] = float('nan')
        indicators['macd_signal'] = float('nan')
        indicators['macd_histogram'] = float('nan')
    
    # === Bollinger Bands (using sum and sum of squares for std dev) ===
    n = len(state.bb_buffer)
    if n >= 20:
        mean = state.bb_sum / n
        variance = (state.bb_sum_sq / n) - (mean * mean)
        std = math.sqrt(max(0, variance))  # Protect against floating point errors
        indicators['bb_upper'] = mean + 2 * std
        indicators['bb_middle'] = mean
        indicators['bb_lower'] = mean - 2 * std
    else:
        indicators['bb_upper'] = float('nan')
        indicators['bb_middle'] = float('nan')
        indicators['bb_lower'] = float('nan')
    
    # === ATR ===
    indicators['atr_14'] = state.atr_value if state.atr_initialized else float('nan')
    
    # === Stochastic %K (O(n) for min/max, but n=14 is constant) ===
    if len(state.stoch_highs) >= 14:
        lowest_low = min(state.stoch_lows)
        highest_high = max(state.stoch_highs)
        if highest_high != lowest_low:
            indicators['stoch_k'] = 100 * (state.current_close - lowest_low) / (highest_high - lowest_low)
        else:
            indicators['stoch_k'] = 50.0
    else:
        indicators['stoch_k'] = float('nan')
    
    # === Stochastic %D (3-period SMA of %K) ===
    if len(state.stoch_k_buffer) >= 3:
        indicators['stoch_d'] = sum(state.stoch_k_buffer) / 3
    else:
        indicators['stoch_d'] = float('nan')
    
    # === Williams %R ===
    if len(state.stoch_highs) >= 14:
        lowest_low = min(state.stoch_lows)
        highest_high = max(state.stoch_highs)
        if highest_high != lowest_low:
            indicators['williams_r'] = -100 * (highest_high - state.current_close) / (highest_high - lowest_low)
        else:
            indicators['williams_r'] = -50.0
    else:
        indicators['williams_r'] = float('nan')
    
    # === CCI ===
    n = len(state.cci_tp_buffer)
    if n >= 20:
        sma_tp = state.cci_tp_sum / n
        # Mean absolute deviation (this is O(n) but n=20 is constant)
        mad = sum(abs(tp - sma_tp) for tp in state.cci_tp_buffer) / n
        if mad > 0:
            indicators['cci_20'] = (state.cci_tp_buffer[-1] - sma_tp) / (0.015 * mad)
        else:
            indicators['cci_20'] = 0.0
    else:
        indicators['cci_20'] = float('nan')
    
    # === ADX and Directional Indicators (+DI, -DI) ===
    if state.adx_initialized and state.adx_tr_ema > 0:
        plus_di = 100 * state.adx_plus_dm_ema / state.adx_tr_ema
        minus_di = 100 * state.adx_minus_dm_ema / state.adx_tr_ema
        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx = 100 * abs(plus_di - minus_di) / di_sum
            # ADX is smoothed DX (simplified - just use current DX)
            indicators['adx_14'] = dx
            indicators['adx'] = dx  # Alias for strategies that use 'adx'
        else:
            indicators['adx_14'] = 0.0
            indicators['adx'] = 0.0
        # Expose +DI and -DI for directional strategies
        indicators['plus_di'] = plus_di
        indicators['minus_di'] = minus_di
    else:
        indicators['adx_14'] = float('nan')
        indicators['adx'] = float('nan')
        indicators['plus_di'] = float('nan')
        indicators['minus_di'] = float('nan')
    
    # === Current OHLC ===
    indicators['open'] = state.current_open
    indicators['high'] = state.current_high
    indicators['low'] = state.current_low
    indicators['close'] = state.current_close
    
    return indicators
