#!/usr/bin/env python3
"""
Verify that configuration is properly set up
Run this to ensure your .env file has the required variables
"""

import sys
from pathlib import Path

# Add current directory to path for config import
sys.path.insert(0, str(Path(__file__).parent))

from config import config

def verify_configuration():
    """Verify that configuration is properly loaded"""
    print("=" * 80)
    print("CONFIGURATION VERIFICATION")
    print("=" * 80)
    print()
    
    print("📋 OpenAI Configuration:")
    print("-" * 80)
    api_key_display = f"{config.openai.API_KEY[:8]}...***MASKED***" if len(config.openai.API_KEY) > 8 else "***MASKED***" if config.openai.API_KEY else "❌ NOT SET"
    print(f"  API_KEY:             {api_key_display}")
    print(f"  API_BASE:            {config.openai.API_BASE}")
    print(f"  MODEL_HYPOTHESIS:    {config.openai.MODEL_HYPOTHESIS}")
    print(f"  MODEL_RISK:          {config.openai.MODEL_RISK}")
    print(f"  MODEL_ORCHESTRATOR:  {config.openai.MODEL_ORCHESTRATOR}")
    
    print("\n📋 Trading Configuration:")
    print("-" * 80)
    print(f"  SYMBOL:              {config.trading.SYMBOL}")
    license_display = f"{config.trading.PATHWAY_LICENSE_KEY[:8]}...***MASKED***" if len(config.trading.PATHWAY_LICENSE_KEY) > 8 else "***MASKED***" if config.trading.PATHWAY_LICENSE_KEY else "❌ NOT SET"
    print(f"  PATHWAY_LICENSE_KEY: {license_display}")
    
    print("\n📋 Pathway API Configuration:")
    print("-" * 80)
    print(f"  REPORTS_API_URL:     {config.pathway_api.REPORTS_API_URL}")
    
    print("\n📋 Hypothesis Generator Configuration:")
    print("-" * 80)
    print(f"  API_HOST:            {config.hypothesis.API_HOST}")
    print(f"  API_PORT:            {config.hypothesis.API_PORT}")
    print(f"  API_URL:             {config.hypothesis.API_URL}")
    print(f"  MCP_HOST:            {config.hypothesis.MCP_HOST}")
    print(f"  MCP_PORT:            {config.hypothesis.MCP_PORT}")
    print(f"  MCP_URL:             {config.hypothesis.MCP_URL}")
    
    print("\n📋 Redis Configuration:")
    print("-" * 80)
    print(f"  HOST:                {config.redis.HOST}")
    print(f"  PORT:                {config.redis.PORT}")
    print(f"  DB:                  {config.redis.DB}")
    
    print("\n📋 Risk Manager Configuration:")
    print("-" * 80)
    print(f"  MCP_HOST:            {config.risk_manager.MCP_HOST}")
    print(f"  MCP_PORT:            {config.risk_manager.MCP_PORT}")
    print(f"  MCP_URL:             {config.risk_manager.MCP_URL}")
    
    print("\n📋 Backtesting Configuration:")
    print("-" * 80)
    print(f"  SERVER_HOST:         {config.backtesting.SERVER_HOST}")
    print(f"  SERVER_PORT:         {config.backtesting.SERVER_PORT}")
    print(f"  API_URL:             {config.backtesting.API_URL}")
    
    print("\n📋 Orchestrator LLM Settings:")
    print("-" * 80)
    print(f"  TEMPERATURE:         {config.orch_llm.TEMPERATURE}")
    print(f"  MAX_TOKENS:          {config.orch_llm.MAX_TOKENS}")
    
    print("\n📋 Orchestrator Search Settings:")
    print("-" * 80)
    print(f"  TIME_WINDOW:         {config.orch_search.TIME_WINDOW}")
    print(f"  STRATEGY_LIMIT:      {config.orch_search.STRATEGY_LIMIT}")
    print(f"  MAX_WEB_SEARCHES:    {config.orch_search.MAX_WEB_SEARCHES}")
    print(f"  MAX_SYNTHESIS_ITER:  {config.orch_search.MAX_SYNTHESIS_ITERATIONS}")
    
    print("\n📋 Orchestrator Performance Thresholds:")
    print("-" * 80)
    print(f"  MIN_WIN_RATE:        {config.orch_performance.MIN_WIN_RATE}")
    print(f"  MIN_SHARPE:          {config.orch_performance.MIN_SHARPE}")
    print(f"  MIN_TRADE_COUNT:     {config.orch_performance.MIN_TRADE_COUNT}")
    
    print("\n📋 Orchestrator API Timeouts:")
    print("-" * 80)
    print(f"  STRATEGY_SEARCH:     {config.orch_timeouts.STRATEGY_API_SEARCH_TIMEOUT}s")
    print(f"  STRATEGY_BACKTEST:   {config.orch_timeouts.STRATEGY_API_BACKTEST_TIMEOUT}s")
    print(f"  WEB_SEARCH_LENGTH:   {config.orch_timeouts.WEB_SEARCH_RESULT_LENGTH}")
    
    print("\n" + "=" * 80)
    
    try:
        config.validate()
        print("✅ All required environment variables are set!")
        print("\nConfiguration loaded from config.py with sensitive values from .env")
        return 0
    except ValueError as e:
        print(f"❌ Configuration validation failed!")
        print(f"\n{str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(verify_configuration())
