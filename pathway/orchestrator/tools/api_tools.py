"""
API MCP tools - Exposes all gateway API endpoints as MCP tools.
"""

from typing import Dict, Any, Optional, List
import httpx

from config import REPORTS_API_URL


# ============================================================================
# HTTP CLIENT HELPER
# ============================================================================

async def call_api(
    endpoint: str,
    method: str = "GET",
    json_data: dict = None,
    timeout: float = 30.0
) -> dict:
    """Make HTTP request to the gateway API."""
    url = f"{REPORTS_API_URL}/{endpoint.lstrip('/')}"
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                response = await client.post(url, json=json_data or {})
            elif method == "DELETE":
                response = await client.delete(url)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API returned {response.status_code}", "detail": response.text}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# TOOL REGISTRATION
# ============================================================================

def register_api_tools(mcp):
    """Register API-related MCP tools."""

    # ========================================================================
    # REPORTS TOOLS
    # ========================================================================

    @mcp.tool()
    async def get_market_report(symbol: str) -> Dict[str, Any]:
        """
        Get the technical analysis market report for a stock symbol.
        
        Use this when user asks about:
        - Price action and trends
        - Technical indicators (RSI, MACD, Bollinger Bands, etc.)
        - Support/resistance levels
        - Chart patterns
        - Entry/exit signals
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA", "GOOGL")
        
        Returns:
            Market analysis report with technical indicators and trading signals.
        """
        print(f"[INFO] Fetching market report for {symbol}")
        result = await call_api(f"reports/{symbol.upper()}/market")
        return {"symbol": symbol.upper(), "report_type": "market", "data": result}

    @mcp.tool()
    async def get_news_report(symbol: str) -> Dict[str, Any]:
        """
        Get the latest news summary report for a stock symbol.
        
        Use this when user asks about:
        - Recent news and headlines
        - Press releases
        - Analyst commentary
        - Market-moving events
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA", "GOOGL")
        
        Returns:
            News summary report with key headlines and sentiment.
        """
        print(f"[INFO] Fetching news report for {symbol}")
        result = await call_api(f"reports/{symbol.upper()}/news")
        return {"symbol": symbol.upper(), "report_type": "news", "data": result}

    @mcp.tool()
    async def get_sentiment_report(symbol: str) -> Dict[str, Any]:
        """
        Get the social sentiment analysis report for a stock symbol.
        
        Use this when user asks about:
        - Social media sentiment (Reddit, Twitter)
        - Retail investor sentiment
        - Buzz and mentions
        - Community discussions
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA", "GOOGL")
        
        Returns:
            Sentiment analysis report from social sources.
        """
        print(f"[INFO] Fetching sentiment report for {symbol}")
        result = await call_api(f"reports/{symbol.upper()}/sentiment")
        return {"symbol": symbol.upper(), "report_type": "sentiment", "data": result}

    @mcp.tool()
    async def get_fundamental_report(symbol: str) -> Dict[str, Any]:
        """
        Get the fundamental analysis report for a stock symbol.
        
        Use this when user asks about:
        - Financial statements (revenue, earnings, margins)
        - Valuation metrics (P/E, P/S, EV/EBITDA)
        - Balance sheet health
        - Cash flow analysis
        - Growth metrics
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA", "GOOGL")
        
        Returns:
            Fundamental analysis report with financial metrics.
        """
        print(f"[INFO] Fetching fundamental report for {symbol}")
        result = await call_api(f"reports/{symbol.upper()}/fundamental")
        return {"symbol": symbol.upper(), "report_type": "fundamental", "data": result}

    @mcp.tool()
    async def get_all_reports(symbol: str) -> Dict[str, Any]:
        """
        Get ALL available reports for a stock symbol at once.
        
        Use this when user wants:
        - Comprehensive stock overview
        - Full analysis across all dimensions
        - To compare multiple aspects (technical + fundamental + sentiment)
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA", "GOOGL")
        
        Returns:
            All reports: market, news, sentiment, fundamental, and facilitator.
        """
        print(f"[INFO] Fetching all reports for {symbol}")
        result = await call_api(f"reports/{symbol.upper()}")
        return {"symbol": symbol.upper(), "report_type": "all", "data": result}

    @mcp.tool()
    async def list_available_symbols() -> Dict[str, Any]:
        """
        List all stock symbols that have cached reports available.
        
        Use this when:
        - User asks what stocks/symbols are available
        - Need to check if data exists for a symbol
        - User wants to browse available options
        
        Returns:
            List of symbols with cached reports and count.
        """
        print("[INFO] Listing available symbols")
        result = await call_api("symbols")
        return result

    # ========================================================================
    # DEBATE TOOLS
    # ========================================================================

    @mcp.tool()
    async def run_bull_bear_debate(
        symbol: str,
        max_rounds: int = 2
    ) -> Dict[str, Any]:
        """
        Start a Bull vs Bear debate for a stock symbol.
        
        Use this when user wants:
        - Balanced analysis with both bullish and bearish perspectives
        - Investment thesis validation
        - To understand both sides of an investment
        - A recommendation based on debate outcome
        
        The debate runs in background. Use get_debate_status to check progress.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            max_rounds: Number of debate rounds (1-5, default 2)
        
        Returns:
            Debate start confirmation with status polling instructions.
        """
        print(f"[INFO] Starting bull-bear debate for {symbol}")
        result = await call_api(
            f"debate/{symbol.upper()}",
            method="POST",
            json_data={"max_rounds": max_rounds, "background": True},
            timeout=120.0
        )
        return {"symbol": symbol.upper(), "action": "debate_started", "data": result}

    @mcp.tool()
    async def get_debate_status(symbol: str) -> Dict[str, Any]:
        """
        Check the status of a bull-bear debate for a symbol.
        
        Use this to:
        - Check if a debate is still running
        - Get the final result once complete
        - See debate progress
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
        
        Returns:
            Debate status including progress and result if complete.
        """
        print(f"[INFO] Checking debate status for {symbol}")
        result = await call_api(f"debate/{symbol.upper()}/status")
        return {"symbol": symbol.upper(), "data": result}

    # ========================================================================
    # SENTIMENT TOOLS
    # ========================================================================

    @mcp.tool()
    async def get_market_sentiment() -> Dict[str, Any]:
        """
        Get overall market sentiment from all clusters.
        
        Use this when user asks about:
        - Overall market mood
        - General sentiment across stocks
        - Market-wide sentiment score
        - Which stocks are trending
        
        Returns:
            Market sentiment score, total posts, clusters by symbol.
        """
        print("[INFO] Fetching market sentiment clusters")
        result = await call_api("clusters")
        return result

    @mcp.tool()
    async def get_symbol_sentiment(symbol: str) -> Dict[str, Any]:
        """
        Get sentiment clusters for a specific stock symbol.
        
        Use this when user asks about:
        - Sentiment for a specific stock
        - Social media buzz for a symbol
        - Community discussions about a stock
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
        
        Returns:
            Sentiment clusters and metrics for the symbol.
        """
        print(f"[INFO] Fetching sentiment for {symbol}")
        result = await call_api(f"clusters/{symbol.upper()}")
        return {"symbol": symbol.upper(), "data": result}

    # ========================================================================
    # ANALYSIS TOOLS
    # ========================================================================

    @mcp.tool()
    async def run_historical_analysis(
        ticker: str,
        period: str = "7d",
        interval: str = "1m"
    ) -> Dict[str, Any]:
        """
        Run historical analysis on a stock using downloaded data.
        
        Use this when user wants to:
        - Analyze historical price data
        - Backtest on specific time periods
        - Get detailed technical analysis on past data
        
        Args:
            ticker: Stock symbol (e.g., "AAPL", "TSLA")
            period: Time period to analyze (e.g., "1d", "5d", "1mo", "3mo", "1y")
            interval: Candle interval (e.g., "1m", "5m", "15m", "1h", "1d")
        
        Returns:
            Historical analysis report with charts and insights.
        """
        print(f"[INFO] Running historical analysis for {ticker}")
        result = await call_api(
            "analyze",
            method="POST",
            json_data={
                "ticker": ticker.upper(),
                "period": period,
                "interval": interval
            },
            timeout=120.0  # Historical analysis can take time
        )
        return {"ticker": ticker.upper(), "period": period, "interval": interval, "data": result}

    @mcp.tool()
    async def query_knowledge_base(question: str) -> Dict[str, Any]:
        """
        Query the knowledge base using RAG (Retrieval Augmented Generation).
        
        Use this when user asks:
        - General finance/trading questions
        - Questions that need document lookup
        - Educational questions about trading concepts
        - Questions where cached reports don't have the answer
        
        Args:
            question: The question to search for in the knowledge base
        
        Returns:
            Answer from the knowledge base with source documents.
        """
        print(f"[INFO] Querying knowledge base: {question[:50]}...")
        result = await call_api(
            "query",
            method="POST",
            json_data={"question": question},
            timeout=30.0
        )
        return result

    # ========================================================================
    # KNOWLEDGE BASE CRUD TOOLS
    # ========================================================================

    @mcp.tool()
    async def ingest_text_to_kb(text: str, symbol: str = "UNKNOWN") -> Dict[str, Any]:
        """
        Add a single text chunk to the knowledge base.
        
        Use this when user wants to:
        - Add custom information to the knowledge base
        - Store a note or insight for later retrieval
        - Add small pieces of text data
        
        Args:
            text: The text content to ingest
            symbol: Stock symbol to associate with (default: "UNKNOWN")
        
        Returns:
            Confirmation with filename and ingestion status.
        """
        print(f"[INFO] Ingesting text to KB for {symbol}")
        result = await call_api(
            "ingest/text",
            method="POST",
            json_data={"text": text, "symbol": symbol.upper()}
        )
        return {"action": "ingest_text", "symbol": symbol.upper(), "data": result}

    @mcp.tool()
    async def ingest_document_to_kb(
        text: str,
        symbol: str = "UNKNOWN",
        chunk_size: int = 999
    ) -> Dict[str, Any]:
        """
        Add a document to the knowledge base with automatic chunking.
        
        Use this when user wants to:
        - Add a long document or article
        - Store research reports or analysis
        - Ingest large text that needs to be split into searchable chunks
        
        Args:
            text: The full document text to ingest
            symbol: Stock symbol to associate with (default: "UNKNOWN")
            chunk_size: Characters per chunk (default: 999)
        
        Returns:
            Confirmation with number of chunks created.
        """
        print(f"[INFO] Ingesting document to KB for {symbol}")
        result = await call_api(
            "ingest/document",
            method="POST",
            json_data={"text": text, "symbol": symbol.upper(), "chunk_size": chunk_size}
        )
        return {"action": "ingest_document", "symbol": symbol.upper(), "data": result}

    @mcp.tool()
    async def list_kb_files() -> Dict[str, Any]:
        """
        List all files in the knowledge base.
        
        Use this when user wants to:
        - See what documents are in the knowledge base
        - Check if specific data has been ingested
        - Browse available knowledge base content
        
        Returns:
            List of ingested files with metadata.
        """
        print("[INFO] Listing knowledge base files")
        result = await call_api("ingest/list")
        return result

    @mcp.tool()
    async def delete_kb_file(filename: str) -> Dict[str, Any]:
        """
        Delete a file from the knowledge base.
        
        Use this when user wants to:
        - Remove outdated information
        - Clean up the knowledge base
        - Delete specific ingested content
        
        Args:
            filename: Name of the file to delete (from list_kb_files)
        
        Returns:
            Confirmation of deletion.
        """
        print(f"[INFO] Deleting KB file: {filename}")
        result = await call_api(f"ingest/{filename}", method="DELETE")
        return {"action": "delete", "filename": filename, "data": result}
