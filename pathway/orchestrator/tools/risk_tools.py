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
        strategy: dict,
        risk_levels: Optional[List[str]] = None
    ) -> str:
        if risk_levels is None:
            risk_levels = ["no-risk", "neutral", "aggressive"]

        print(f"[INFO] Assessing risk for {symbol} with levels: {risk_levels}")

        reports = await fetch_reports(symbol)
        strategy_str = json.dumps(strategy) if isinstance(strategy, dict) else str(strategy)

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
        strategy: dict,
        risk_level: str = "neutral"
    ) -> str:
        print(f"[INFO] Single tier assessment for {symbol} at {risk_level} level")

        reports = await fetch_reports(symbol)
        strategy_str = json.dumps(strategy) if isinstance(strategy, dict) else str(strategy)

        messages = build_prompt(strategy_str, reports, risk_level)
        response = await call_llm(messages)

        return f"--- Risk Level: {risk_level.upper()} ---\n{response}"

    # no return; tools are registered via decorators
