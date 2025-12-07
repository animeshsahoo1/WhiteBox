"""
Backtesting API MCP tools.
"""

from typing import Optional, Dict, List

from api_clients import call_backtesting_api


def register_backtesting_tools(mcp):
    """Register backtesting-related MCP tools."""

    @mcp.tool()
    async def list_all_strategies() -> dict:
        """
        List all available trading strategies with their live backtesting metrics.
        
        Metrics are updated in real-time as new candles arrive. Each strategy includes:
        - total_pnl: Total profit/loss
        - win_rate: Percentage of winning trades (0-1)
        - sharpe_ratio: Risk-adjusted return metric
        - max_drawdown: Maximum peak-to-trough decline
        - profit_factor: Gross profit / gross loss
        - total_trades: Number of completed trades
        - And more...
        
        Returns:
            Dictionary with list of strategies and their current metrics.
        """
        print("[INFO] Fetching all strategies from backtesting API")
        result = await call_backtesting_api("strategies")
        return result

    @mcp.tool()
    async def get_strategy_details(strategy_name: str) -> dict:
        """
        Get detailed information about a specific strategy.
        
        Args:
            strategy_name: Name of the strategy (e.g., "sma_crossover", "rsi_mean_reversion")
        
        Returns:
            Dictionary containing:
            - name: Strategy name
            - description: What the strategy does
            - code: The actual strategy Python code
            - metrics: Live backtesting performance metrics
        """
        print(f"[INFO] Fetching strategy details: {strategy_name}")
        result = await call_backtesting_api(f"strategies/{strategy_name}")
        return result

    @mcp.tool()
    async def search_strategies(
        query: str,
        limit: int = 5,
        metric_weights: Optional[Dict[str, float]] = None
    ) -> dict:
        """
        Search for strategies using natural language with optional metric-weighted ranking.
        
        This uses semantic search (embeddings) to find strategies matching your description,
        then optionally ranks them by performance metrics using min-max normalization.
        
        IMPORTANT: Rankings update LIVE as new candles arrive! The metrics used for scoring
        are fetched fresh from Redis on every call.
        
        Args:
            query: Natural language description of what you're looking for
                   Examples: "momentum strategy", "mean reversion with RSI", "trend following"
            limit: Maximum number of results to return (1-50, default 5)
            metric_weights: Optional dict mapping metric names to weights for ranking.
                           Higher weights = more influence on final score.
                           Available metrics:
                           - sharpe_ratio: Risk-adjusted returns (higher better)
                           - win_rate: Percentage of winning trades (higher better)
                           - profit_factor: Gross profit / gross loss (higher better)
                           - max_drawdown: Maximum decline (LOWER is better, auto-inverted)
                           - return_pct: Total return percentage (higher better)
                           - total_pnl: Absolute profit/loss (higher better)
                           
                           Example: {"sharpe_ratio": 0.4, "win_rate": 0.3, "max_drawdown": 0.3}
        
        Returns:
            Dictionary with:
            - query: Your search query
            - sort_method: "weighted" or "similarity"
            - results: List of matching strategies with similarity scores, 
                       weighted_score (if weights provided), and live metrics
            - note: Reminder that rankings update live
        """
        print(f"[INFO] Searching strategies: '{query}' with weights: {metric_weights}")

        payload = {
            "query": query,
            "limit": limit
        }
        if metric_weights:
            payload["metric_weights"] = metric_weights

        result = await call_backtesting_api("strategies/search", method="POST", json_data=payload)
        return result

    @mcp.tool()
    async def create_strategy(
        description: str,
        name: Optional[str] = None
    ) -> dict:
        """
        Create a new trading strategy from a natural language description using LLM.
        
        The LLM will generate Python code for a strategy function based on your description.
        The strategy will automatically be picked up by the backtesting pipeline and 
        start generating live metrics as candles arrive.
        
        CRITICAL: Only use the EXACT indicators listed below. Custom periods are NOT supported.
        
        SUPPORTED INDICATORS (use these exact names in your strategy):
        
        Moving Averages:
            - sma_5, sma_10, sma_20, sma_50, sma_200 (Simple Moving Averages)
            - ema_9, ema_12, ema_26 (Exponential Moving Averages)
        
        MACD:
            - macd_line (EMA_12 - EMA_26)
            - macd_signal (9-period EMA of MACD line)
            - macd_histogram (macd_line - macd_signal)
        
        Momentum Indicators:
            - rsi_14 (Relative Strength Index, 14-period ONLY - no rsi_7, rsi_21, etc.)
            - stoch_k (Stochastic %K, 14-period)
            - stoch_d (Stochastic %D, 3-period SMA of %K)
            - williams_r (Williams %R, 14-period)
            - cci_20 (Commodity Channel Index, 20-period)
            - adx_14 / adx (Average Directional Index, 14-period)
            - plus_di, minus_di (Directional Indicators for ADX)
        
        Volatility Indicators:
            - bb_upper, bb_middle, bb_lower (Bollinger Bands, 20-period, 2 std dev)
            - atr_14 (Average True Range, 14-period ONLY - no atr_20, atr_60, etc.)
        
        Price Data:
            - open, high, low, close (Current candle OHLC)
        
        Position State:
            - position (current position: 'long', 'short', or 'none')
            - entry_price (entry price if in a position)
        
        NOT AVAILABLE (DO NOT USE):
            - Custom periods: sma_100, ema_50, rsi_7, atr_20, avg_atr_60, etc.
            - Performance metrics: profit_factor, return_pct, total_trades, win_rate, 
              sharpe_ratio, duration - THESE ARE BACKTESTING METRICS, NOT INDICATORS
            - volume - NOT AVAILABLE
        
        STRATEGY FORMAT:
        The generated strategy must be a Python function that:
        1. Takes 'indicators' dict as parameter
        2. Returns None (no action), or dict with:
           - 'action': 'BUY', 'SELL', 'SHORT', or 'COVER'
           - 'size': Position size 0.0-1.0 (optional, default 1.0)
           - 'stop_loss': Stop loss percentage (optional, e.g., 0.02 for 2%)
           - 'take_profit': Take profit percentage (optional)
           - 'trailing_stop': Trailing stop percentage (optional)
        
        Args:
            description: Natural language description of the strategy you want.
                        Be specific about:
                        - Entry conditions (when to buy/short)
                        - Exit conditions (when to sell/cover)
                        - Which indicators to use (from the list above)
                        - Stop loss percentage
                        - Take profit percentage
                        - Position size (0.0-1.0, where 1.0 = 100% of capital)
                        
                        Examples:
                        - "RSI oversold bounce: buy when rsi_14 < 30, sell when rsi_14 > 70, 2% stop loss"
                        - "SMA crossover: buy when sma_50 crosses above sma_200, sell on reverse"
                        - "Bollinger band breakout: buy when close > bb_upper, sell when close < bb_middle"
                        - "MACD momentum: buy when macd_histogram > 0 and rsi_14 < 70"
            
            name: Optional custom name for the strategy. If not provided, 
                  a name will be generated from the description.
        
        Returns:
            Dictionary with:
            - name: The strategy name (to use with other tools)
            - code: The generated Python code
            - description: Your original description
            - message: Confirmation message
        """
        print(f"[INFO] Creating strategy: '{description[:50]}...'")

        payload = {"description": description}
        if name:
            payload["name"] = name

        result = await call_backtesting_api("strategies", method="POST", json_data=payload)
        return result

    @mcp.tool()
    async def get_strategy_metrics(strategy_name: str) -> dict:
        """
        Get ONLY the live metrics for a specific strategy (no code).
        
        Faster than get_strategy_details if you only need performance data.
        Metrics update in real-time as new candles are processed.
        
        Args:
            strategy_name: Name of the strategy
        
        Returns:
            Dictionary with live metrics including:
            - total_pnl, win_rate, sharpe_ratio, max_drawdown
            - profit_factor, return_pct, total_trades
            - last_signal, position, candles_processed
            - last_updated timestamp
        """
        print(f"[INFO] Fetching metrics for: {strategy_name}")
        result = await call_backtesting_api(f"metrics/{strategy_name}")
        return result

    @mcp.tool()
    async def compare_strategies(strategy_names: List[str]) -> dict:
        """
        Compare multiple strategies side-by-side with their live metrics.
        
        Useful for deciding which strategy to use or for risk assessment.
        
        Args:
            strategy_names: List of strategy names to compare
                           Example: ["sma_crossover", "rsi_mean_reversion", "macd_rsi_confluence"]
        
        Returns:
            Dictionary with each strategy's metrics for easy comparison.
        """
        print(f"[INFO] Comparing strategies: {strategy_names}")

        results = {}
        for name in strategy_names:
            metrics = await call_backtesting_api(f"metrics/{name}")
            results[name] = metrics

        summary = {
            "strategies_compared": len(strategy_names),
            "comparison": results,
            "best_by_sharpe": None,
            "best_by_win_rate": None,
            "best_by_pnl": None
        }

        valid_strategies = {k: v for k, v in results.items() if "error" not in v and v}
        if valid_strategies:
            try:
                summary["best_by_sharpe"] = max(valid_strategies.keys(),
                    key=lambda k: valid_strategies[k].get("sharpe_ratio", float("-inf")) or float("-inf"))
                summary["best_by_win_rate"] = max(valid_strategies.keys(),
                    key=lambda k: valid_strategies[k].get("win_rate", 0) or 0)
                summary["best_by_pnl"] = max(valid_strategies.keys(),
                    key=lambda k: valid_strategies[k].get("total_pnl", float("-inf")) or float("-inf"))
            except:
                pass

        return summary

    @mcp.tool()
    async def find_best_strategy(
        metric: str = "sharpe_ratio",
        min_trades: int = 1
    ) -> dict:
        """
        Find the best performing strategy based on a specific metric.
        
        Args:
            metric: Which metric to optimize for. Options:
                   - "sharpe_ratio" (default): Best risk-adjusted returns
                   - "win_rate": Highest win percentage
                   - "profit_factor": Best profit/loss ratio
                   - "total_pnl": Highest absolute profit
                   - "return_pct": Best percentage return
                   - "max_drawdown": Lowest drawdown (most stable)
            min_trades: Minimum number of trades required (to filter out untested strategies)
        
        Returns:
            Dictionary with the best strategy and its metrics.
        """
        print(f"[INFO] Finding best strategy by {metric} (min {min_trades} trades)")

        all_strategies = await call_backtesting_api("strategies")

        if "error" in all_strategies:
            return all_strategies

        strategies = all_strategies.get("strategies", [])

        # Metrics are at top level, not nested (API returns: name, total_pnl, win_rate, etc.)
        # Filter by has_metrics flag OR presence of metrics fields, and min_trades threshold
        valid = [s for s in strategies
                 if (s.get("has_metrics") or s.get("total_pnl") is not None) 
                 and (s.get("total_trades") or 0) >= min_trades]

        if not valid:
            return {"error": f"No strategies found with at least {min_trades} trades", "total_strategies": len(strategies)}

        reverse = metric != "max_drawdown"

        try:
            best = max(valid, key=lambda s: s.get(metric, float("-inf") if reverse else float("inf")) or (float("-inf") if reverse else float("inf")))

            return {
                "best_strategy": best.get("name", "unknown"),
                "optimized_metric": metric,
                "metric_value": best.get(metric),
                "full_metrics": {
                    "total_pnl": best.get("total_pnl"),
                    "total_trades": best.get("total_trades"),
                    "win_rate": best.get("win_rate"),
                    "candles_processed": best.get("candles_processed")
                },
                "total_strategies_evaluated": len(valid),
                "min_trades_filter": min_trades
            }
        except Exception as e:
            return {"error": f"Failed to find best strategy: {str(e)}"}
