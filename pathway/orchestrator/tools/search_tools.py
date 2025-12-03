"""
Web search MCP tools.
"""

from typing import Dict, Any

from web_search import smart_search


def register_search_tools(mcp):
    """Register web search MCP tools."""

    @mcp.tool()
    async def smart_search_trading(
        query: str,
        max_results: int = 6,
        fetch_content: bool = True,
        content_max_length: int = 2500
    ) -> Dict[str, Any]:
        """
        Smart search that automatically decomposes complex queries, searches in parallel,
        and aggregates results. This is the recommended search tool for comprehensive
        trading strategy research.
        
        The tool will:
        1. Use LLM to break down your query into focused sub-queries
        2. Search all sub-queries in parallel
        3. Deduplicate and rank results from trusted trading sites
        4. Fetch page content from top results
        
        Args:
            query: Your trading research question (can be complex/multi-part)
                   Examples:
                   - "How to build a momentum strategy using RSI and MACD?"
                   - "Best mean reversion strategies for swing trading"
                   - "Stop loss and take profit rules for day trading"
            max_results: Maximum total results to return (default: 6)
            fetch_content: Automatically fetch page content (default: True)
            content_max_length: Max characters per page (default: 2500)
        
        Returns:
            Dictionary with decomposed queries, aggregated results, and fetched content.
        """
        return await smart_search(
            query=query,
            max_results=max_results,
            fetch_content=fetch_content,
            content_max_length=content_max_length
        )
