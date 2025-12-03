"""
Report MCP tools (Facilitator report).
"""

from typing import Dict, Any

from api_clients import fetch_facilitator_report


def register_report_tools(mcp):
    """Register report-related MCP tools."""

    @mcp.tool()
    async def get_facilitator_report(symbol: str) -> Dict[str, Any]:
        """
        Fetch the facilitator report (Bull vs Bear debate summary) for a stock symbol.
        
        The facilitator report contains:
        - Bull case: Key bullish arguments and supporting evidence
        - Bear case: Key bearish arguments and supporting evidence
        - Debate summary: Key disagreements and areas of agreement
        - Outcome: Winner, confidence level, and recommendation
        
        This is the synthesized output from the Bull vs Bear analyst debate,
        providing a balanced view of both perspectives.
        
        Args:
            symbol: Stock/asset symbol (e.g., "AAPL", "MSFT", "GOOGL")
        
        Returns:
            Dictionary containing the full facilitator report with bull/bear analysis.
        """
        print(f"[INFO] Fetching facilitator report for {symbol}")

        try:
            report = await fetch_facilitator_report(symbol)
            return {
                "symbol": symbol.upper(),
                "status": "success",
                "report": report
            }
        except Exception as e:
            return {
                "symbol": symbol.upper(),
                "status": "error",
                "error": str(e)
            }
