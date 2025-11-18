"""Tool functions for orchestrator - MCP calls, API calls, web search"""

import asyncio
import requests
from fastmcp import Client
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import orchestrator_settings, trading_settings


# ============================================================================
# CONFIGURATION
# ============================================================================

STRATEGY_API_ENDPOINT = orchestrator_settings.strategy_api_endpoint
RISK_ANALYSIS_MCP = orchestrator_settings.risk_analysis_mcp
HYPOTHESIS_MCP = orchestrator_settings.hypothesis_mcp
TRADING_SYMBOL = trading_settings.symbol


# ============================================================================
# MCP TOOL FUNCTIONS
# ============================================================================

async def call_risk_analysis_mcp_async(symbol: str, strategy: dict, risk_levels: list) -> dict:
    """Call Risk Analysis MCP Server using fastmcp Client"""
    try:
        client = Client(RISK_ANALYSIS_MCP)
        async with client:
            result = await client.call_tool(
                name="analyze_risk",
                arguments={
                    "symbol": symbol,
                    "strategy": strategy,
                    "risk_levels": risk_levels
                }
            )
            return result
    except Exception as e:
        print(f"Error calling Risk Analysis MCP: {e}")
        return {}


def call_risk_analysis_mcp(symbol: str, strategy: dict, risk_levels: list) -> dict:
    """Synchronous wrapper for Risk Analysis MCP call"""
    return asyncio.run(call_risk_analysis_mcp_async(symbol, strategy, risk_levels))


async def call_hypothesis_mcp_async() -> list:
    """Call Hypothesis Generator MCP Server using fastmcp Client"""
    try:
        client = Client(HYPOTHESIS_MCP)
        async with client:
            result = await client.call_tool(
                name="get_hypotheses",
                arguments={}
            )
            return result.get("hypotheses", []) if isinstance(result, dict) else result
    except Exception as e:
        print(f"Error calling Hypothesis MCP: {e}")
        return []


def call_hypothesis_mcp() -> list:
    """Synchronous wrapper for Hypothesis MCP call"""
    return asyncio.run(call_hypothesis_mcp_async())


# ============================================================================
# STRATEGY API FUNCTIONS
# ============================================================================

def call_strategy_api_search(search_params: dict) -> dict:
    """
    Call FastAPI endpoint for strategy search
    Endpoint expects: {"operation": "get_strategies", "search_params": {...}}
    """
    try:
        payload = {
            "operation": "get_strategies",
            "search_params": search_params
        }
        response = requests.post(
            STRATEGY_API_ENDPOINT, 
            json=payload, 
            timeout=orchestrator_settings.strategy_api_search_timeout
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling Strategy API (search): {e}")
        return {"results": {"strategies": []}}


def call_strategy_api_backtest(strategy: dict) -> dict:
    """
    Call FastAPI endpoint to input strategy and backtest
    Endpoint expects: {"operation": "input_and_backtest", "strategy": {...}}
    """
    try:
        payload = {
            "operation": "input_and_backtest",
            "strategy": strategy
        }
        response = requests.post(
            STRATEGY_API_ENDPOINT, 
            json=payload, 
            timeout=orchestrator_settings.strategy_api_backtest_timeout
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling Strategy API (backtest): {e}")
        return {}


# ============================================================================
# WEB SEARCH FUNCTIONS
# ============================================================================

def web_search_tool(query: str) -> str:
    """
    Web search tool that can be called by the LLM
    Returns search results as a formatted string
    """
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        return f"Search results for '{query}':\n{results[:orchestrator_settings.web_search_result_length]}"
    except Exception as e:
        return f"Error performing search: {str(e)}"


@tool
def web_search(query: str) -> str:
    """
    Search the web for trading strategy information.
    Use this tool to find technical trading strategies, indicators, entry/exit rules, etc.
    
    Args:
        query: The search query (e.g., "RSI oversold strategy", "MACD crossover trading")
    
    Returns:
        Search results as text
    """
    return web_search_tool(query)
