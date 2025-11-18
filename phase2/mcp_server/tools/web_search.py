"""Web Search Tool using DuckDuckGo"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer, PathwayMcp
from duckduckgo_search import DDGS
import json
import logging

logger = logging.getLogger(__name__)


class WebSearchTool(McpServable):
    """
    MCP Tool for web searching trading strategies via DuckDuckGo
    
    Searches web and returns raw results for parent LLM to process
    """
    
    class WebSearchRequestSchema(pw.Schema):
        query: str
        max_results: int = 5
    
    def __init__(self):
        logger.info("Web Search Tool initialized")
    
    def search_handler(self, request: pw.Table) -> pw.Table:
        """
        Handle web search requests
        
        Args:
            request: Table with query and max_results
        
        Returns:
            Table with synthesized strategy
        """


        @pw.udf
        def _web_search_strategy(query: str, max_results: int) -> str:
            """
            Search web and return raw results
            
            Returns JSON string with search results
            """
            
            try:
                # Search DuckDuckGo
                logger.info(f"Searching web for: {query}")
                
                with DDGS() as ddgs:
                    results = list(ddgs.text(
                        keywords=f"{query}",
                        max_results=max_results
                    ))
                
                if not results:
                    logger.warning(f"No web results found for: {query}")
                    return json.dumps({"error": "No results found"})
                
                logger.info(f"Found {len(results)} web results")
                
                # Format search results
                formatted_results = {
                    "query": query,
                    "results_count": len(results),
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "body": r.get("body", ""),
                            "url": r.get("href", "")
                        }
                        for r in results
                    ]
                }
                
                return json.dumps(formatted_results)
                
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                return json.dumps({"error": str(e)})
        
        return request.select(
            result=_web_search_strategy(
                pw.this.query,
                pw.this.max_results,
            )
        )

    
    def register_mcp(self, server: McpServer):
        """Register this tool with MCP server"""
        
        server.tool(
            name="web_search_strategy",
            description=(
                "Search the web for trading strategy information using DuckDuckGo. "
                "Returns raw search results (title, body, URL) for the parent LLM to process. "
                "Useful for discovering new strategies not in the backtesting database."
            ),
            request_handler=self.search_handler,
            schema=self.WebSearchRequestSchema
        )
        
        logger.info("Registered web_search_strategy tool")

basic_tools = WebSearchTool()

pathway_mcp_server = PathwayMcp(
    name="Streamable MCP Server",
    transport="streamable-http",
    host="localhost",
    port=8005,
    serve=[basic_tools],
)

pw.run()