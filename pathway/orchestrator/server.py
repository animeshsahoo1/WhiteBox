"""
Risk Assessment MCP Server - Main entry point.

A modular MCP server that provides:
- Risk assessment tools (3-tier: no-risk, neutral, aggressive)
- Backtesting API tools (list, search, create, compare strategies)
- Web search tools (smart search with query decomposition)
- Report tools (facilitator/bull-bear debate reports)

Usage:
    python server.py
"""

from fastmcp import FastMCP

from config import MCP_SERVER_HOST, MCP_SERVER_PORT, print_config
from tools import register_all_tools


# Initialize MCP server
mcp = FastMCP(name="Risk Assessment Server")

# Register all tools
register_all_tools(mcp)


def main():
    print("=" * 60)
    print("Starting Risk Assessment MCP Server (Modular)")
    print("=" * 60)
    print_config()

    mcp.run(
        transport="streamable-http",
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT
    )


if __name__ == "__main__":
    main()
