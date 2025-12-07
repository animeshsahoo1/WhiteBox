# Backtesting Validation

Validates our backtesting system against the industry-standard `backtesting.py` library.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run validation (requires services running)
python validate_strategies.py

# Test API strategy generation
python test_api_generation.py
```

## Validation Strategies

| Strategy | Interval | Lookback | Description |
|----------|----------|----------|-------------|
| `val_sma_crossover` | 1d | 2y | SMA 20/50 crossover |
| `val_ema_crossover` | 1h | 3mo | EMA 9/12 crossover |
| `val_macd_crossover` | 1h | 3mo | MACD/Signal crossover |

## Metrics Compared

| Metric | Tolerance | Notes |
|--------|-----------|-------|
| Total Trades | ±1 | Edge cases at boundaries |
| Win Rate | ±5% | Rounded differences |
| Max Drawdown | ±5% | Timing differences |
| Equity Return | ±10% | Open position handling |
| Equity | ±10% | Match with backtesting.py |
| Sharpe Ratio | ±0.5 | Equity-curve based |
| Profit Factor | ±20% | Division edge cases |

## Latest Results (Dec 7, 2025)

```
✅ val_sma_crossover (1d, 2y): 7/7 metrics matched
   - 5 trades, 20% win rate, 25.17% max_drawdown
   - 36.41% return, $13,641 equity
   - 0.95 sharpe, 1.15 profit factor

✅ val_macd_crossover (1h, 3mo): 6/7 metrics matched  
   - 14 trades, 50% win rate, 5.83% max_drawdown
   - 12% return, $11,202 equity
   - 2.95 sharpe, 2.75 profit factor
   - Minor warning: equity_return (12% vs 13%)

⚠️ val_ema_crossover (1h, 3mo): 4/7 metrics matched
   - Trade count: 14 vs 13 (±1 edge case)
   - Cascades to sharpe/profit_factor differences
```

## Key Findings

### ✅ Sharpe Ratio
- Implemented **equity-curve based** sharpe (industry standard)
- Uses per-bar returns with interval-aware annualization
- Matches backtesting.py for daily and hourly strategies

### ✅ Equity Calculation  
- Includes unrealized P&L for open positions
- Matches backtesting.py's final equity calculation

### ⚠️ Trade Count Edge Cases
- ±1 trade difference possible at boundaries
- Caused by floating-point crossover detection
- Cascades to other metric differences

## Files

- `validate_strategies.py` - Compare 3 strategies against backtesting.py
- `test_api_generation.py` - Test LLM strategy generation API
- `requirements.txt` - Python dependencies
