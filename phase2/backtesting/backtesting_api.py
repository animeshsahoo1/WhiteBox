#!/usr/bin/env python3
"""
Minimal Backtesting API Server
Returns hardcoded strategy data for testing purposes
"""

from fastapi import FastAPI
from typing import Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import backtesting_server_settings

app = FastAPI(title="Backtesting API", version="1.0.0")


HARDCODED_STRATEGIES = {
    "strategies": [
        {
            "id": "strategy_001",
            "name": "Moving Average Crossover",
            "type": "trend_following",
            "parameters": {
                "fast_ma": 50,
                "slow_ma": 200,
                "timeframe": "1d"
            },
            "performance": {
                "total_return": 0.245,
                "sharpe_ratio": 1.85,
                "max_drawdown": -0.12,
                "win_rate": 0.62
            },
            "risk_tier": "neutral"
        },
        {
            "id": "strategy_002",
            "name": "RSI Mean Reversion",
            "type": "mean_reversion",
            "parameters": {
                "rsi_period": 14,
                "oversold": 30,
                "overbought": 70
            },
            "performance": {
                "total_return": 0.18,
                "sharpe_ratio": 1.45,
                "max_drawdown": -0.08,
                "win_rate": 0.58
            },
            "risk_tier": "no_risk"
        },
        {
            "id": "strategy_003",
            "name": "Momentum Breakout",
            "type": "momentum",
            "parameters": {
                "lookback_period": 20,
                "breakout_threshold": 1.5
            },
            "performance": {
                "total_return": 0.35,
                "sharpe_ratio": 2.1,
                "max_drawdown": -0.18,
                "win_rate": 0.65
            },
            "risk_tier": "aggressive"
        }
    ],
    "metadata": {
        "total_strategies": 3,
        "backtest_period": "2020-01-01 to 2024-12-31",
        "data_source": "hardcoded_mock"
    }
}


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "ok", "service": "backtesting-api"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/strategies")
async def get_strategies() -> dict[str, Any]:
    """Return all strategies"""
    return HARDCODED_STRATEGIES


@app.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str) -> dict[str, Any]:
    """Return specific strategy by ID"""
    for strategy in HARDCODED_STRATEGIES["strategies"]:
        if strategy["id"] == strategy_id:
            return strategy
    return {"error": "Strategy not found"}


@app.post("/backtest")
async def run_backtest(request: dict[str, Any]) -> dict[str, Any]:
    """Run backtest (returns hardcoded data)"""
    return HARDCODED_STRATEGIES


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=backtesting_server_settings.host, 
        port=backtesting_server_settings.port
    )
