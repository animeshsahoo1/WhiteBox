"""Tool functions for orchestrator - MCP calls, API calls, web search"""

import asyncio
import json
from xmlrpc import client
import requests
from fastmcp import Client
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import centralized configuration
from config import config

# Validate configuration
config.validate()

# ============================================================================
# CONFIGURATION FROM config.py
# ============================================================================

# Orchestrator settings
STRATEGY_API_ENDPOINT = config.backtesting.API_URL
RISK_ANALYSIS_MCP = config.risk_manager.MCP_URL
HYPOTHESIS_MCP = config.hypothesis.MCP_URL

# Trading settings
TRADING_SYMBOL = config.trading.SYMBOL

# Orchestrator configuration
ORCH_LLM_TEMPERATURE = config.orch_llm.TEMPERATURE
ORCH_LLM_MAX_TOKENS = config.orch_llm.MAX_TOKENS
ORCH_TIME_WINDOW = config.orch_search.TIME_WINDOW
ORCH_STRATEGY_LIMIT = config.orch_search.STRATEGY_LIMIT
ORCH_MAX_WEB_SEARCHES = config.orch_search.MAX_WEB_SEARCHES
ORCH_MAX_SYNTHESIS_ITERATIONS = config.orch_search.MAX_SYNTHESIS_ITERATIONS
ORCH_MIN_WIN_RATE = config.orch_performance.MIN_WIN_RATE
ORCH_MIN_SHARPE = config.orch_performance.MIN_SHARPE
ORCH_MIN_TRADE_COUNT = config.orch_performance.MIN_TRADE_COUNT
STRATEGY_API_SEARCH_TIMEOUT = config.orch_timeouts.STRATEGY_API_SEARCH_TIMEOUT
STRATEGY_API_BACKTEST_TIMEOUT = config.orch_timeouts.STRATEGY_API_BACKTEST_TIMEOUT
WEB_SEARCH_RESULT_LENGTH = config.orch_timeouts.WEB_SEARCH_RESULT_LENGTH

# OpenAI settings
OPENAI_API_KEY = config.openai.API_KEY
OPENAI_API_BASE = config.openai.API_BASE
OPENAI_MODEL_ORCHESTRATOR = config.openai.MODEL_ORCHESTRATOR


# ============================================================================
# MCP TOOL FUNCTIONS
# ============================================================================
client2 = Client(RISK_ANALYSIS_MCP)
async def call_risk_analysis_mcp_async(symbol: str, strategy: dict, risk_levels: list) -> dict:
    """Call Risk Analysis MCP Server using fastmcp Client"""
    
    async with client2:
        result = await client2.call_tool(
            name="assess_risk_all_tiers",
            arguments={}
        )
        return result if isinstance(result, dict) else {}


def call_risk_analysis_mcp(symbol: str, strategy: dict, risk_levels: list) -> dict:
    """Synchronous wrapper for Risk Analysis MCP call"""
    return asyncio.run(call_risk_analysis_mcp_async(symbol, strategy, risk_levels))


async def call_hypothesis_mcp_async() -> list:
    """Call Hypothesis Generator MCP Server using fastmcp Client"""
    try:
        client = Client(HYPOTHESIS_MCP)
        async with client:
            result = await client.call_tool(
                name="get_hypothesis",
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
    Uses GET /strategies and filters results locally
    """
    try:
        response = requests.get(
            "http://backtesting-api:8001/strategies", 
            json={"hello":"world"},
            timeout=STRATEGY_API_SEARCH_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        
        # Return strategies in expected format
        return {"results": data}
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
            timeout=STRATEGY_API_BACKTEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling Strategy API (backtest): {e}")
        return {}


# ============================================================================
# WEB SEARCH FUNCTIONS
# ============================================================================

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
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        return f"Search results for '{query}':\n{results[:WEB_SEARCH_RESULT_LENGTH]}"
    except Exception as e:
        return f"Error performing search: {str(e)}"


def web_search_tool(query: str) -> str:
    """
    Web search tool that can be called by the LLM
    Returns search results as a formatted string
    """
    print("="*20)
    print("Websearch Query:")
    print(json.dumps(query, indent=2))
    print("="*20)
    return web_search.invoke({"query": query})


# ============================================================================
# LLM INITIALIZATION (must be after web_search definition)
# ============================================================================

# Initialize LLM for orchestrator
llm = ChatOpenAI(
    model=OPENAI_MODEL_ORCHESTRATOR,
    temperature=ORCH_LLM_TEMPERATURE,
    api_key=OPENAI_API_KEY,
    max_tokens=ORCH_LLM_MAX_TOKENS,
    base_url=OPENAI_API_BASE,
)

# LLM with web search tool
llm_with_tools = llm.bind_tools([web_search])
