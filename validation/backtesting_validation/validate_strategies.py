#!/usr/bin/env python3
"""
Validation Script: Compare our metrics with backtesting.py

Tests 3 unique validation strategies:
1. val_sma_crossover (1d, 2y) - SMA 20/50 crossover
2. val_ema_crossover (1h, 3mo) - EMA 9/12 crossover  
3. val_macd_crossover (1h, 3mo) - MACD/Signal crossover

Compares 7 key metrics: trades, win_rate, max_drawdown, equity_return, equity, sharpe_ratio, profit_factor
"""

import json
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:8000"
SYMBOL = "AAPL"
INITIAL_CAPITAL = 10000.0

# Strategies to validate (name -> config)
STRATEGIES = {
    "val_sma_crossover": {
        "interval": "1d",
        "lookback": "2y",
        "yf_period": "2y",
        "yf_interval": "1d"
    },
    "val_ema_crossover": {
        "interval": "1h",
        "lookback": "3mo",
        "yf_period": "3mo",
        "yf_interval": "1h"
    },
    "val_macd_crossover": {
        "interval": "1h",
        "lookback": "3mo",
        "yf_period": "3mo",
        "yf_interval": "1h"
    },
}


# ============================================================================
# BACKTESTING.PY STRATEGY CLASSES
# ============================================================================

class SMA_Crossover(Strategy):
    """SMA 20/50 Crossover matching val_sma_crossover.txt"""
    def init(self):
        close = pd.Series(self.data.Close)
        self.sma20 = self.I(lambda: close.rolling(20).mean())
        self.sma50 = self.I(lambda: close.rolling(50).mean())
    
    def next(self):
        if crossover(self.sma20, self.sma50):
            self.buy()
        elif crossover(self.sma50, self.sma20):
            if self.position:
                self.position.close()


class EMA_Crossover(Strategy):
    """EMA 9/12 Crossover matching val_ema_crossover.txt"""
    def init(self):
        close = pd.Series(self.data.Close)
        self.ema9 = self.I(lambda: close.ewm(span=9, adjust=False).mean())
        self.ema12 = self.I(lambda: close.ewm(span=12, adjust=False).mean())
    
    def next(self):
        if crossover(self.ema9, self.ema12):
            self.buy()
        elif crossover(self.ema12, self.ema9):
            if self.position:
                self.position.close()


class MACD_Crossover(Strategy):
    """MACD/Signal Crossover matching val_macd_crossover.txt"""
    def init(self):
        close = pd.Series(self.data.Close)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        self.macd = self.I(lambda: macd)
        self.signal = self.I(lambda: signal)
    
    def next(self):
        if crossover(self.macd, self.signal):
            self.buy()
        elif crossover(self.signal, self.macd):
            if self.position:
                self.position.close()


# Strategy class mapping
STRATEGY_CLASSES = {
    "val_sma_crossover": SMA_Crossover,
    "val_ema_crossover": EMA_Crossover,
    "val_macd_crossover": MACD_Crossover,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def fetch_yf_data(period: str, interval: str) -> pd.DataFrame:
    """Fetch data from yfinance."""
    ticker = yf.Ticker(SYMBOL)
    df = ticker.history(period=period, interval=interval)
    return df


def run_backtesting_py(strategy_class, df: pd.DataFrame) -> dict:
    """Run backtesting.py and extract metrics."""
    bt = Backtest(df, strategy_class, cash=INITIAL_CAPITAL, commission=0.001)
    stats = bt.run()
    
    sharpe = stats.get("Sharpe Ratio", 0)
    if pd.isna(sharpe):
        sharpe = 0.0
    
    profit_factor = stats.get("Profit Factor", 0)
    if pd.isna(profit_factor):
        profit_factor = 0.0
    
    return {
        "total_trades": stats["# Trades"],
        "win_rate": stats["Win Rate [%]"] / 100 if stats["# Trades"] > 0 else 0,
        "equity": stats["Equity Final [$]"],
        "return_pct": stats["Return [%]"],
        "max_drawdown": abs(stats["Max. Drawdown [%]"]) / 100,
        "sharpe_ratio": sharpe,
        "profit_factor": profit_factor,
        "candles": len(df)
    }


def fetch_our_metrics(strategy_name: str, interval: str) -> dict:
    """Fetch metrics from our API."""
    endpoint = f"{API_BASE_URL}/backtesting/metrics/{strategy_name}"
    try:
        response = requests.get(endpoint, timeout=10)
        if response.status_code == 200:
            data = response.json()
            metrics = data.get("metrics", {})
            key = f"{SYMBOL}:{interval}"
            if key in metrics:
                m = metrics[key]
                return {
                    "total_trades": m.get("total_trades", 0),
                    "win_rate": m.get("win_rate", 0),
                    "equity": m.get("equity", INITIAL_CAPITAL),
                    "return_pct": m.get("equity_return_pct", 0),
                    "max_drawdown": m.get("max_drawdown", 0),
                    "sharpe_ratio": m.get("sharpe_ratio", 0),
                    "profit_factor": m.get("profit_factor", 0),
                    "candles": m.get("candles_processed", 0)
                }
    except Exception as e:
        print(f"   Error fetching {strategy_name}: {e}")
    return None


def compare_metrics(name: str, ours: dict, theirs: dict) -> dict:
    """Compare metrics and return results."""
    results = {"name": name, "matches": [], "warnings": [], "errors": []}
    
    # Trade count - should match exactly or within 1
    trade_diff = abs(ours["total_trades"] - theirs["total_trades"])
    if trade_diff == 0:
        results["matches"].append(f"total_trades: {ours['total_trades']} ✅")
    elif trade_diff <= 1:
        results["warnings"].append(f"total_trades: {ours['total_trades']} vs {theirs['total_trades']} (±1) ⚠️")
    else:
        results["errors"].append(f"total_trades: {ours['total_trades']} vs {theirs['total_trades']} ❌")
    
    # Win rate - within 5%
    wr_diff = abs(ours["win_rate"] - theirs["win_rate"])
    if wr_diff < 0.05:
        results["matches"].append(f"win_rate: {ours['win_rate']:.2%} ✅")
    elif wr_diff < 0.15:
        results["warnings"].append(f"win_rate: {ours['win_rate']:.2%} vs {theirs['win_rate']:.2%} ⚠️")
    else:
        results["errors"].append(f"win_rate: {ours['win_rate']:.2%} vs {theirs['win_rate']:.2%} ❌")
    
    # Max drawdown - within 5%
    dd_diff = abs(ours["max_drawdown"] - theirs["max_drawdown"])
    if dd_diff < 0.05:
        results["matches"].append(f"max_drawdown: {ours['max_drawdown']:.2%} ✅")
    elif dd_diff < 0.10:
        results["warnings"].append(f"max_drawdown: {ours['max_drawdown']:.2%} vs {theirs['max_drawdown']:.2%} ⚠️")
    else:
        results["errors"].append(f"max_drawdown: {ours['max_drawdown']:.2%} vs {theirs['max_drawdown']:.2%} ❌")
    
    # Equity return - within 10%
    our_ret = ours["return_pct"]
    ret_diff = abs(our_ret - theirs["return_pct"]) / max(abs(theirs["return_pct"]), 1)
    if ret_diff < 0.10:
        results["matches"].append(f"equity_return: {our_ret:.2f}% ✅")
    elif ret_diff < 0.25:
        results["warnings"].append(f"equity_return: {our_ret:.2f}% vs {theirs['return_pct']:.2f}% ⚠️")
    else:
        results["errors"].append(f"equity_return: {our_ret:.2f}% vs {theirs['return_pct']:.2f}% ❌")
    
    # Equity - within 10%
    our_equity = ours.get("equity", INITIAL_CAPITAL)
    their_equity = theirs.get("equity", INITIAL_CAPITAL)
    equity_diff = abs(our_equity - their_equity) / max(their_equity, 1)
    if equity_diff < 0.10:
        results["matches"].append(f"equity: ${our_equity:.2f} ✅")
    elif equity_diff < 0.25:
        results["warnings"].append(f"equity: ${our_equity:.2f} vs ${their_equity:.2f} ⚠️")
    else:
        results["errors"].append(f"equity: ${our_equity:.2f} vs ${their_equity:.2f} ❌")
    
    # Sharpe Ratio - within 0.5
    our_sharpe = ours.get("sharpe_ratio", 0)
    their_sharpe = theirs.get("sharpe_ratio", 0)
    sharpe_diff = abs(our_sharpe - their_sharpe)
    if sharpe_diff < 0.5:
        results["matches"].append(f"sharpe_ratio: {our_sharpe:.2f} ✅")
    elif sharpe_diff < 1.0:
        results["warnings"].append(f"sharpe_ratio: {our_sharpe:.2f} vs {their_sharpe:.2f} ⚠️")
    else:
        results["errors"].append(f"sharpe_ratio: {our_sharpe:.2f} vs {their_sharpe:.2f} ❌")
    
    # Profit Factor - within 20%
    our_pf = ours.get("profit_factor", 0)
    their_pf = theirs.get("profit_factor", 0)
    if our_pf > 9000 and their_pf > 9000:
        results["matches"].append(f"profit_factor: ∞ ✅")
    elif their_pf > 0:
        pf_diff = abs(our_pf - their_pf) / max(their_pf, 1)
        if pf_diff < 0.20:
            results["matches"].append(f"profit_factor: {our_pf:.2f} ✅")
        elif pf_diff < 0.40:
            results["warnings"].append(f"profit_factor: {our_pf:.2f} vs {their_pf:.2f} ⚠️")
        else:
            results["errors"].append(f"profit_factor: {our_pf:.2f} vs {their_pf:.2f} ❌")
    else:
        results["matches"].append(f"profit_factor: {our_pf:.2f} ✅")
    
    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🔬 BACKTESTING VALIDATION: Our System vs backtesting.py")
    print("=" * 70)
    print(f"Symbol: {SYMBOL}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print("=" * 70)
    
    all_results = []
    
    for name, config in STRATEGIES.items():
        print(f"\n📊 {name} ({config['interval']}, {config['lookback']})...")
        
        # Fetch yfinance data
        df = fetch_yf_data(config["yf_period"], config["yf_interval"])
        print(f"   yfinance: {len(df)} candles")
        
        # Run backtesting.py
        bt_metrics = run_backtesting_py(STRATEGY_CLASSES[name], df)
        print(f"   backtesting.py: {bt_metrics['total_trades']} trades")
        
        # Fetch our metrics
        our_metrics = fetch_our_metrics(name, config["interval"])
        if our_metrics:
            print(f"   Our system: {our_metrics['total_trades']} trades, {our_metrics['candles']} candles")
            
            # Compare
            results = compare_metrics(name, our_metrics, bt_metrics)
            all_results.append(results)
        else:
            print(f"   ❌ Could not fetch our metrics for {name}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION SUMMARY")
    print("=" * 70)
    
    total_matches = 0
    total_warnings = 0
    total_errors = 0
    
    for result in all_results:
        print(f"\n{result['name']}:")
        for m in result["matches"]:
            print(f"   {m}")
            total_matches += 1
        for w in result["warnings"]:
            print(f"   {w}")
            total_warnings += 1
        for e in result["errors"]:
            print(f"   {e}")
            total_errors += 1
    
    print("\n" + "=" * 70)
    print(f"Total: ✅ {total_matches} match | ⚠️ {total_warnings} warnings | ❌ {total_errors} errors")
    
    if total_errors == 0:
        print("✅ VALIDATION PASSED")
    else:
        print("❌ VALIDATION NEEDS INVESTIGATION")
    
    # Save results
    with open("validation_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n📁 Results saved to validation_results.json")


if __name__ == "__main__":
    main()
