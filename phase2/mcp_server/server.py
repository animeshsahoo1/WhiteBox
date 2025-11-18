"""MCP Server using Pathway"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServer
import logging

from ..config.settings import mcp_settings
from .tools.backtesting_search import BacktestingSearchTool
from ..risk_managers.risk_assessment import RiskAssessmentTool
from .tools.web_search import WebSearchTool
from .resources.hypotheses import HypothesesResource
from .resources.phase1_reports import Phase1ReportsResource
from .resources.market_conditions import MarketConditionsResource

logger = logging.getLogger(__name__)


def create_mcp_server() -> McpServer:
    """Create and configure MCP server"""
    
    logger.info("Creating MCP Server")
    
    # Initialize server
    server = McpServer()
    
    # Register tools
    backtesting_tool = BacktestingSearchTool()
    backtesting_tool.register_mcp(server)
    
    risk_tool = RiskAssessmentTool()
    risk_tool.register_mcp(server)
    
    web_tool = WebSearchTool()
    web_tool.register_mcp(server)
    
    # Register resources
    hypotheses_resource = HypothesesResource()
    hypotheses_resource.register_mcp(server)
    
    phase1_resource = Phase1ReportsResource()
    phase1_resource.register_mcp(server)
    
    market_resource = MarketConditionsResource()
    market_resource.register_mcp(server)
    
    logger.info("MCP Server configured successfully")
    return server


def run_mcp_server():
    """Main entry point for MCP server"""
    
    logger.info("Starting MCP Server")
    
    server = create_mcp_server()
    
    # Run Pathway with MCP server
    pw.run(
        host=mcp_settings.host,
        port=mcp_settings.port,
        with_mcp_server=server
    )
    
    logger.info(f"MCP Server running at {mcp_settings.server_url}")
