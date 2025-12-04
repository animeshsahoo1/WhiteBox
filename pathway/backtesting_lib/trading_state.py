"""
Trading State Management - Incremental Version

Combines incremental indicators and metrics.
No price history storage - everything is O(1) per candle.

Reset Detection:
- Tracks the latest processed timestamp
- If an older candle arrives, assumes config change and resets state
- This handles candle API config changes gracefully
"""

import json
import numpy as np
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any

from indicators import IndicatorState, update_indicators, get_indicators
from metrics import MetricsState, record_trade, update_equity, get_metrics


@dataclass
class TradingState:
    """
    Complete trading state with incremental indicator and metrics calculation.
    
    Key differences from non-incremental version:
    - No price history lists (opens, highs, lows, closes)
    - Indicators calculated incrementally via IndicatorState
    - Metrics tracked incrementally via MetricsState
    - Total memory: O(indicator_periods) instead of O(candles)
    
    Reset Detection:
    - Tracks latest_timestamp to detect out-of-order candles
    - If older candle arrives, state is reset (config change detected)
    """
    
    # Incremental indicator state
    indicator_state: Dict[str, Any] = field(default_factory=dict)
    
    # Incremental metrics state  
    metrics_state: Dict[str, Any] = field(default_factory=dict)
    
    # For detecting config changes / out-of-order candles
    latest_timestamp: str = ""  # Track the most recent timestamp
    
    # For deduplication (small buffer for exact duplicates)
    processed_timestamps: list = field(default_factory=list)
    max_timestamps: int = 100  # Reduced - just for immediate dedup
    
    @classmethod
    def initial(cls, initial_capital: float = 10000.0, commission: float = 0.001) -> 'TradingState':
        """Create initial trading state"""
        indicator_state = IndicatorState()
        metrics_state = MetricsState.initial(initial_capital, commission)
        
        return cls(
            indicator_state=asdict(indicator_state),
            metrics_state=asdict(metrics_state),
            latest_timestamp="",
            processed_timestamps=[]
        )
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TradingState':
        data = json.loads(json_str)
        return cls(**data)
    
    def get_indicator_state(self) -> IndicatorState:
        """Reconstruct IndicatorState from dict"""
        return IndicatorState(**self.indicator_state)
    
    def set_indicator_state(self, state: IndicatorState):
        """Store IndicatorState as dict"""
        self.indicator_state = asdict(state)
    
    def get_metrics_state(self) -> MetricsState:
        """Reconstruct MetricsState from dict"""
        return MetricsState(**self.metrics_state)
    
    def set_metrics_state(self, state: MetricsState):
        """Store MetricsState as dict"""
        self.metrics_state = asdict(state)
    
    def get_all_metrics(self) -> dict:
        """Get all metrics for output"""
        metrics_obj = self.get_metrics_state()
        return get_metrics(metrics_obj)


def execute_strategy_code(code: str, indicators: dict, position_info: dict) -> Optional[dict]:
    """
    Execute strategy code and return signal dict.
    
    Args:
        code: Strategy Python code
        indicators: Dict of indicator values
        position_info: Dict with current position state:
            - position: 'NONE', 'LONG', or 'SHORT'
            - entry_price: Entry price if in position
            - unrealized_pnl: Current unrealized P&L
    
    Returns:
        Signal dict with keys:
            - action: 'BUY', 'SELL', 'SHORT', 'COVER', or None
            - stop_loss: Price level (optional)
            - take_profit: Price level (optional)
            - trailing_stop: Percentage as decimal, e.g. 0.02 for 2% (optional)
            - size: Position size as fraction 0-1 (optional, default 1.0)
        
        For backward compatibility, also accepts simple string 'BUY'/'SELL'
    """
    try:
        namespace = {
            'np': np, 
            'indicators': indicators,
            'position': position_info.get('position', 'NONE'),
            'entry_price': position_info.get('entry_price', 0.0),
            'unrealized_pnl': position_info.get('unrealized_pnl', 0.0),
        }
        exec(code, namespace)
        
        if 'strategy' in namespace:
            result = namespace['strategy'](indicators)
            
            # Handle dict return (new format)
            if isinstance(result, dict):
                action = result.get('action')
                if action in ('BUY', 'SELL', 'SHORT', 'COVER'):
                    return {
                        'action': action,
                        'stop_loss': result.get('stop_loss'),
                        'take_profit': result.get('take_profit'),
                        'trailing_stop': result.get('trailing_stop'),
                        'size': result.get('size', 1.0)
                    }
            
            # Handle string return (backward compatible)
            elif result in ('BUY', 'SELL'):
                return {'action': result, 'size': 1.0}
            elif result == 'SHORT':
                return {'action': 'SHORT', 'size': 1.0}
            elif result == 'COVER':
                return {'action': 'COVER', 'size': 1.0}
                
    except Exception as e:
        pass  # Strategy error, return None
    return None


def process_single_candle(
    state: TradingState,
    timestamp: str,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    strategy_code: str,
    is_insertion: bool = True
) -> TradingState:
    """
    Process a single candle with T+1 execution model.
    All operations are O(1) - no history recalculation.
    
    Enhanced with:
    - Stop-loss execution (checked against low for LONG, high for SHORT)
    - Take-profit execution (checked against high for LONG, low for SHORT)
    - Trailing stop updates and execution
    - Position sizing
    - Short selling support
    - Auto-reset on config change (detects old candles)
    
    T+1 Execution:
    - Signal is generated at the END of the current bar (using close price)
    - Order is executed at the OPEN of the NEXT bar
    - SL/TP are checked during the bar using high/low
    
    Reset Detection:
    - If incoming timestamp < latest_timestamp, config changed
    - Reset state and start fresh with this candle
    """
    
    if not is_insertion:
        return state
    
    # Check if already processed (exact duplicate)
    if timestamp in state.processed_timestamps:
        return state
    
    # === DETECT CONFIG CHANGE: Old candle arriving means reset needed ===
    if state.latest_timestamp and timestamp < state.latest_timestamp:
        # Old candle detected! Config must have changed.
        # Reset state completely and start fresh.
        state = TradingState.initial()
        # Note: We don't return - we continue to process this candle as the first one
    
    # Get current states
    ind_state = state.get_indicator_state()
    met_state = state.get_metrics_state()
    
    # === STEP 1: Check stop-loss / take-profit / trailing stop FIRST ===
    # These are checked intra-bar using high/low
    exit_triggered = False
    exit_reason = None
    exit_price = None
    
    if met_state.position_type == 'LONG':
        # Check stop-loss (price hits low)
        if met_state.stop_loss_price > 0 and low <= met_state.stop_loss_price:
            exit_triggered = True
            exit_reason = 'stop_loss'
            exit_price = met_state.stop_loss_price  # Assume filled at SL price
        
        # Check trailing stop
        elif met_state.trailing_stop_price > 0 and low <= met_state.trailing_stop_price:
            exit_triggered = True
            exit_reason = 'trailing_stop'
            exit_price = met_state.trailing_stop_price
        
        # Check take-profit (price hits high)
        elif met_state.take_profit_price > 0 and high >= met_state.take_profit_price:
            exit_triggered = True
            exit_reason = 'take_profit'
            exit_price = met_state.take_profit_price
            
    elif met_state.position_type == 'SHORT':
        # Check stop-loss (price hits high)
        if met_state.stop_loss_price > 0 and high >= met_state.stop_loss_price:
            exit_triggered = True
            exit_reason = 'stop_loss'
            exit_price = met_state.stop_loss_price
        
        # Check trailing stop
        elif met_state.trailing_stop_price > 0 and high >= met_state.trailing_stop_price:
            exit_triggered = True
            exit_reason = 'trailing_stop'
            exit_price = met_state.trailing_stop_price
        
        # Check take-profit (price hits low)
        elif met_state.take_profit_price > 0 and low <= met_state.take_profit_price:
            exit_triggered = True
            exit_reason = 'take_profit'
            exit_price = met_state.take_profit_price
    
    # Execute SL/TP/Trailing exit
    if exit_triggered and exit_price is not None:
        if met_state.position_type == 'LONG':
            pnl = (exit_price - met_state.entry_price) * met_state.position_units
            pnl -= (met_state.entry_price + exit_price) * met_state.position_units * met_state.commission
        else:  # SHORT
            pnl = (met_state.entry_price - exit_price) * met_state.position_units
            pnl -= (met_state.entry_price + exit_price) * met_state.position_units * met_state.commission
        
        met_state = record_trade(met_state, pnl, exit_reason)
        met_state = _reset_position(met_state)
        # Clear any pending signal to prevent immediate re-entry after forced exit
        met_state.pending_signal = {}
    
    # === STEP 2: Execute pending signal from previous bar at THIS bar's open ===
    pending = met_state.pending_signal
    if pending and isinstance(pending, dict) and pending.get('action'):
        action = pending.get('action')
        size = pending.get('size', 1.0)
        
        # BUY signal - enter LONG
        if action == 'BUY' and met_state.position_type == 'NONE':
            # Calculate position size
            capital_to_use = met_state.current_capital * size
            units = capital_to_use / open_price
            commission_cost = capital_to_use * met_state.commission
            
            met_state.current_capital -= commission_cost
            met_state.position_type = 'LONG'
            met_state.entry_price = open_price
            met_state.entry_time = timestamp
            met_state.position_size = size
            met_state.position_units = units
            met_state.highest_since_entry = high
            met_state.lowest_since_entry = low
            
            # Set SL/TP levels - for LONG: stop_loss BELOW entry, take_profit ABOVE
            if pending.get('stop_loss'):
                sl = pending['stop_loss']
                # If < 1, treat as percentage; otherwise as absolute price
                if sl < 1:
                    met_state.stop_loss_price = open_price * (1 - sl)
                else:
                    met_state.stop_loss_price = sl
            if pending.get('take_profit'):
                tp = pending['take_profit']
                if tp < 1:
                    met_state.take_profit_price = open_price * (1 + tp)
                else:
                    met_state.take_profit_price = tp
            if pending.get('trailing_stop'):
                met_state.trailing_stop_pct = pending['trailing_stop']
                met_state.trailing_stop_price = open_price * (1 - pending['trailing_stop'])
        
        # SHORT signal - enter SHORT
        elif action == 'SHORT' and met_state.position_type == 'NONE':
            capital_to_use = met_state.current_capital * size
            units = capital_to_use / open_price
            commission_cost = capital_to_use * met_state.commission
            
            met_state.current_capital -= commission_cost
            met_state.position_type = 'SHORT'
            met_state.entry_price = open_price
            met_state.entry_time = timestamp
            met_state.position_size = size
            met_state.position_units = units
            met_state.highest_since_entry = high
            met_state.lowest_since_entry = low
            
            # For SHORT: stop_loss is ABOVE entry, take_profit is BELOW entry
            if pending.get('stop_loss'):
                sl = pending['stop_loss']
                # If < 1, treat as percentage; otherwise as absolute price
                if sl < 1:
                    met_state.stop_loss_price = open_price * (1 + sl)
                else:
                    met_state.stop_loss_price = sl
            if pending.get('take_profit'):
                tp = pending['take_profit']
                if tp < 1:
                    met_state.take_profit_price = open_price * (1 - tp)
                else:
                    met_state.take_profit_price = tp
            if pending.get('trailing_stop'):
                met_state.trailing_stop_pct = pending['trailing_stop']
                met_state.trailing_stop_price = open_price * (1 + pending['trailing_stop'])
        
        # SELL signal - exit LONG
        elif action == 'SELL' and met_state.position_type == 'LONG':
            pnl = (open_price - met_state.entry_price) * met_state.position_units
            pnl -= (met_state.entry_price + open_price) * met_state.position_units * met_state.commission
            met_state = record_trade(met_state, pnl, 'signal')
            met_state = _reset_position(met_state)
        
        # COVER signal - exit SHORT
        elif action == 'COVER' and met_state.position_type == 'SHORT':
            pnl = (met_state.entry_price - open_price) * met_state.position_units
            pnl -= (met_state.entry_price + open_price) * met_state.position_units * met_state.commission
            met_state = record_trade(met_state, pnl, 'signal')
            met_state = _reset_position(met_state)
    
    # Clear pending signal
    met_state.pending_signal = {}
    
    # === STEP 3: Update indicators incrementally ===
    ind_state = update_indicators(ind_state, open_price, high, low, close)
    
    # === STEP 4: Get current indicator values ===
    indicators = get_indicators(ind_state)
    
    # === STEP 5: Generate signal for NEXT bar ===
    # Skip signal generation if we just exited via SL/TP/trailing (prevent immediate re-entry)
    if exit_triggered:
        met_state.last_signal = 'HOLD'
        # Don't set pending_signal - cooldown after forced exit
    else:
        position_info = {
            'position': met_state.position_type,
            'entry_price': met_state.entry_price,
            'unrealized_pnl': 0.0
        }
        if met_state.position_type == 'LONG':
            position_info['unrealized_pnl'] = (close - met_state.entry_price) * met_state.position_units
        elif met_state.position_type == 'SHORT':
            position_info['unrealized_pnl'] = (met_state.entry_price - close) * met_state.position_units
        
        signal = execute_strategy_code(strategy_code, indicators, position_info)
        
        if signal:
            met_state.last_signal = signal.get('action', 'HOLD')
            met_state.pending_signal = signal
        else:
            met_state.last_signal = 'HOLD'
    
    # === STEP 6: Update equity tracking (also updates trailing stop) ===
    met_state = update_equity(met_state, close, high, low)
    
    # === STEP 7: Store states back ===
    state.set_indicator_state(ind_state)
    state.set_metrics_state(met_state)
    
    # === STEP 8: Update tracking ===
    # Update latest timestamp for reset detection
    state.latest_timestamp = timestamp
    
    # Track processed timestamps for immediate dedup (bounded)
    state.processed_timestamps.append(timestamp)
    if len(state.processed_timestamps) > state.max_timestamps:
        state.processed_timestamps = state.processed_timestamps[-state.max_timestamps:]
    
    return state


def _reset_position(met_state: MetricsState) -> MetricsState:
    """Reset position-related fields after exit."""
    met_state.position_type = 'NONE'
    met_state.entry_price = 0.0
    met_state.entry_time = ''
    met_state.position_size = 1.0
    met_state.position_units = 0.0
    met_state.stop_loss_price = 0.0
    met_state.take_profit_price = 0.0
    met_state.trailing_stop_pct = 0.0
    met_state.trailing_stop_price = 0.0
    met_state.highest_since_entry = 0.0
    met_state.lowest_since_entry = 0.0
    return met_state
