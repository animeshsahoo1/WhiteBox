"""
Tools package for MCP server.
"""

from tools.risk_tools import register_risk_tools
from tools.backtesting_tools import register_backtesting_tools
from tools.search_tools import register_search_tools
from tools.report_tools import register_report_tools


def register_all_tools(mcp):
    """Register all MCP tools on the server."""
    register_risk_tools(mcp)
    register_backtesting_tools(mcp)
    register_search_tools(mcp)
    register_report_tools(mcp)
