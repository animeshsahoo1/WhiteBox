#!/usr/bin/env python3
"""
Entry point for Orchestrator (CLI interface for testing)

Run: python -m phase2.run_orchestrator
"""

import asyncio
import logging
from phase2.orchestrator.graph import TradingStrategyGraph
from phase2.orchestrator.mcp_client import MCPClientWrapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def interactive_mode():
    """Interactive CLI for testing orchestrator with LangGraph"""
    
    print("=" * 80)
    print("PHASE 2: TRADING STRATEGY ORCHESTRATOR (LangGraph)")
    print("=" * 80)
    print("\nThis AI assistant can help you with:")
    print("  • Finding strategies for current market conditions")
    print("  • Searching for specific types of strategies (RSI, MACD, etc.)")
    print("  • Assessing risk across no-risk, neutral, and aggressive tiers")
    print("  • Web searching for trading strategy information")
    print("\nType 'exit' to quit\n")
    
    # Initialize MCP client and graph
    logger.info("Initializing MCP client and LangGraph...")
    mcp_client = MCPClientWrapper()
    graph = TradingStrategyGraph(mcp_client)
    
    print("✅ System ready!\n")
    
    while True:
        try:
            query = input("You> ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            print("\n🤔 Processing your query...\n")
            
            # Run the graph
            response = await graph.run(query)
            
            print("=" * 80)
            print(response)
            print("=" * 80)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}\n")


def main():
    """Start interactive orchestrator"""
    asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
