"""
Risk assessment MCP tools. Registered via `register_risk_tools(mcp)` so the decorator
is applied with the provided `mcp` instance (keeps modularization without changing
external tool names).
"""

import asyncio
import json
from typing import Optional, List, Dict, Any

from api_clients import fetch_reports, build_prompt, call_llm


def register_risk_tools(mcp):
    """Register risk-related MCP tools on given `mcp` instance."""

    @mcp.tool()
    async def assess_risk_all_tiers(
        symbol: str,
        strategy: str,
        risk_levels: Optional[List[str]] = None
    ) -> str:
        """
        Assess a trading strategy across multiple risk tolerance levels.
        
        Use this when user wants:
        - Complete risk analysis across conservative to aggressive profiles
        - To understand how a strategy performs under different risk appetites
        - Recommendations for different investor types
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            strategy: Trading strategy as JSON string or text description. Should include:
                     - name: Strategy name
                     - entry_condition: When to enter position
                     - exit_condition: When to exit position
                     - stop_loss: Stop loss percentage or condition
                     - take_profit: Take profit target
                     - position_size: Position size as decimal (e.g., 0.3 for 30%)
                     Example: '{"name":"Bollinger Breakout","entry_condition":"price breaks above upper band","exit_condition":"price below middle band","stop_loss":"lower band","take_profit":"2x band width","position_size":0.3}'
            risk_levels: List of risk levels to assess. Options: "no-risk", "neutral", "aggressive"
        
        Returns:
            Risk assessment for each tier with recommendations.
        """
        if risk_levels is None:
            risk_levels = ["no-risk", "neutral", "aggressive"]

        print(f"[INFO] Assessing risk for {symbol} with levels: {risk_levels}")

        reports = await fetch_reports(symbol)
        # strategy is already a string, no conversion needed
        strategy_str = strategy

        async def process_risk_level(level: str) -> str:
            print(f"[INFO] Processing {level}...")
            messages = build_prompt(strategy_str, reports, level)
            response = await call_llm(messages)
            print(f"[INFO] Completed {level}")
            return f"--- Risk Level: {level.upper()} ---\n{response}"

        tasks = [process_risk_level(level) for level in risk_levels]
        results = await asyncio.gather(*tasks)

        separator = "\n\n" + "=" * 80 + "\n\n"
        final_result = separator.join(results)

        print(f"[INFO] Assessment complete, total length: {len(final_result)}")
        return final_result


    @mcp.tool()
    async def assess_single_risk_tier(
        symbol: str,
        strategy: str,
        risk_level: str = "neutral"
    ) -> str:
        """
        Assess a trading strategy for a specific risk tolerance level.
        
        Use this when user wants:
        - Quick risk assessment for one risk profile
        - Analysis tailored to their specific risk appetite
        - Faster response than full multi-tier assessment
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            strategy: Trading strategy as JSON string or text description. Should include:
                     - name: Strategy name
                     - entry_condition: When to enter position
                     - exit_condition: When to exit position
                     - stop_loss: Stop loss percentage or condition
                     - take_profit: Take profit target
                     - position_size: Position size as decimal (e.g., 0.3 for 30%)
                     Example: '{"name":"Bollinger Breakout","entry_condition":"price breaks above upper band","exit_condition":"price below middle band","stop_loss":"lower band","take_profit":"2x band width","position_size":0.3}'
            risk_level: One of "no-risk", "neutral", or "aggressive"
        
        Returns:
            Risk assessment and recommendation for the specified tier.
        """
        print(f"[INFO] Single tier assessment for {symbol} at {risk_level} level")

        reports = await fetch_reports(symbol)
        # strategy is already a string, no conversion needed
        strategy_str = strategy

        messages = build_prompt(strategy_str, reports, risk_level)
        response = await call_llm(messages)

        return f"--- Risk Level: {risk_level.upper()} ---\n{response}"

    # no return; tools are registered via decorators
