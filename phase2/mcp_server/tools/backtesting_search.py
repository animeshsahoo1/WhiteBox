"""Backtesting API Search Tool"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer
import httpx
import json
import logging
from typing import Dict, Any

from ...config.settings import backtesting_settings

logger = logging.getLogger(__name__)


class BacktestingSearchTool(McpServable):
    """
    MCP Tool for searching backtesting API for strategies
    
    Accepts filters, sorting, and returns matching strategies with performance metrics
    """
    
    class SearchRequestSchema(pw.Schema):
        filters_json: str
        sort_by_json: str
        sort_by_weight_json: str
        limit: int = 10
    
    def __init__(self):
        self.api_url = backtesting_settings.base_url
        self.timeout = backtesting_settings.timeout
        logger.info(f"Backtesting Search Tool initialized: {self.api_url}")
    
    def search_handler(self, request: pw.Table) -> pw.Table:
        """
        Handle backtesting search requests
        
        Args:
            request: Table with filters_json, sort_by_json, sort_by_weight_json, limit
        
        Returns:
            Table with search results
        """
        
        return request.select(
            result=pw.apply(
                self._search_strategies,
                pw.this.filters_json,
                pw.this.sort_by_json,
                pw.this.sort_by_weight_json,
                pw.this.limit,
            )
        )
    
    def _search_strategies(
        self,
        filters_json: str,
        sort_by_json: str,
        sort_by_weight_json: str,
        limit: int
    ) -> str:
        """
        Search backtesting API for strategies
        
        Returns JSON string with search results
        """
        
        try:
            filters = json.loads(filters_json)
            sort_by = json.loads(sort_by_json)
            sort_by_weight = json.loads(sort_by_weight_json)
            
            # Make API request
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_url}/api/v1/strategies/search",
                    json={
                        "filters": filters,
                        "sort_by": sort_by,
                        "sort_by_weight": sort_by_weight,
                        "limit": limit
                    }
                )
                
                response.raise_for_status()
                
                results = response.json()
                
                logger.info(f"Found {len(results.get('results', {}).get('strategies', []))} strategies")
                
                return json.dumps({"results": results})
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error searching backtesting API: {e}")
            return json.dumps({"error": f"API error: {str(e)}", "results": {"strategies": []}})
        except Exception as e:
            logger.error(f"Error searching backtesting API: {e}")
            return json.dumps({"error": str(e), "results": {"strategies": []}})
    
    def register_mcp(self, server: McpServer):
        """Register this tool with MCP server"""
        
        server.tool(
            name="search_backtesting_api",
            description=(
                "Search backtesting API for trading strategies. "
                "Accepts filters (performance criteria, technical indicators, time window), "
                "sorting preferences, and returns matching strategies with full performance metrics."
            ),
            request_handler=self.search_handler,
            schema=self.SearchRequestSchema
        )
        
        logger.info("Registered search_backtesting_api tool")
