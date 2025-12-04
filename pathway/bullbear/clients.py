"""
External Service Clients for Bull-Bear Debate
Handles communication with Reports API and RAG Server
"""
import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .config import ReportsConfig, RAGConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class Report:
    """Represents a fetched report"""
    report_type: str
    content: str
    timestamp: str
    symbol: str
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_type": self.report_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "metadata": self.metadata or {}
        }


class ReportsClient:
    """
    Client for fetching reports from the Reports API.
    Fetches news, sentiment, market, and fundamental reports.
    """
    
    def __init__(self, config: Optional[ReportsConfig] = None):
        self.config = config or get_config().reports
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )
    
    async def fetch_all_reports(self, symbol: str) -> Dict[str, Report]:
        """
        Fetch all 4 reports for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with keys: news, sentiment, market, fundamental
        """
        report_types = ["news", "sentiment", "market", "fundamental"]
        reports = {}
        
        for report_type in report_types:
            try:
                report = await self.fetch_report(symbol, report_type)
                reports[report_type] = report
            except Exception as e:
                logger.error(f"Error fetching {report_type} report for {symbol}: {e}")
                reports[report_type] = Report(
                    report_type=report_type,
                    content="",
                    timestamp=datetime.utcnow().isoformat(),
                    symbol=symbol,
                    metadata={"error": str(e)}
                )
        
        return reports
    
    async def fetch_report(self, symbol: str, report_type: str) -> Report:
        """
        Fetch a single report.
        
        Args:
            symbol: Stock symbol
            report_type: One of 'news', 'sentiment', 'market', 'fundamental'
            
        Returns:
            Report object
        """
        try:
            response = await self._client.get(
                f"/reports/{symbol}/{report_type}"
            )
            response.raise_for_status()
            data = response.json()
            
            return Report(
                report_type=report_type,
                content=data.get("content", data.get("report", "")),
                timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
                symbol=symbol,
                metadata=data.get("metadata", {})
            )
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching report: {e}")
            raise
    
    async def fetch_facilitator_report(self, symbol: str) -> Optional[Report]:
        """Fetch the previous facilitator report if available"""
        try:
            response = await self._client.get(
                f"/reports/{symbol}/facilitator"
            )
            response.raise_for_status()
            data = response.json()
            
            return Report(
                report_type="facilitator",
                content=data.get("content", data.get("report", "")),
                timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
                symbol=symbol,
                metadata=data.get("metadata", {})
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.warning(f"Could not fetch facilitator report: {e}")
            return None
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()


class RAGClient:
    """
    Client for the RAG (Retrieval Augmented Generation) server.
    Used to fetch additional context for counter-arguments.
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or get_config().rag
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )
    
    async def query(
        self,
        query: str,
        symbol: Optional[str] = None,
        context_type: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Query the RAG server for relevant information.
        
        Args:
            query: The search query
            symbol: Optional symbol to filter results
            context_type: Optional context type filter
            limit: Maximum results to return
            
        Returns:
            Dict with 'results' list and 'metadata'
        """
        try:
            payload = {
                "query": query,
                "limit": limit
            }
            if symbol:
                payload["symbol"] = symbol
            if context_type:
                payload["context_type"] = context_type
            
            response = await self._client.post(
                "/query",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"RAG query error: {e}")
            return {"results": [], "error": str(e)}
    
    async def get_counter_evidence(
        self,
        point: str,
        opposing_party: str,
        symbol: str
    ) -> List[str]:
        """
        Get evidence to counter a specific point.
        
        Args:
            point: The point to counter
            opposing_party: 'bull' or 'bear' (the party being countered)
            symbol: Stock symbol
            
        Returns:
            List of relevant counter-evidence strings
        """
        # Build counter-query based on opposing position
        if opposing_party == "bull":
            query = f"risks concerns negative indicators for {symbol}: {point}"
        else:
            query = f"opportunities positive indicators growth for {symbol}: {point}"
        
        result = await self.query(query, symbol=symbol, limit=5)
        
        return [
            r.get("content", r.get("text", ""))
            for r in result.get("results", [])
            if r
        ]
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()


class SyncReportsClient:
    """Synchronous version of ReportsClient for non-async contexts"""
    
    def __init__(self, config: Optional[ReportsConfig] = None, use_dummy: bool = False):
        self.config = config or get_config().reports
        self.use_dummy = use_dummy
    
    def _get_dummy_reports(self, symbol: str) -> Dict[str, Report]:
        """Generate dummy reports for testing"""
        print(f"    📄 [SyncReportsClient] Generating dummy reports for {symbol}")
        
        dummy_news = f"""
# News Report for {symbol}
## Latest Headlines

1. **{symbol} Announces Q4 Earnings Beat** - The company reported earnings of $2.15 per share, beating estimates by 12%.
2. **New Product Launch Success** - The latest product line has seen unprecedented demand with 2M units sold in first week.
3. **Expansion into Asian Markets** - {symbol} announced plans to expand operations in India and Southeast Asia.
4. **Analyst Upgrades** - Morgan Stanley upgraded {symbol} to "Overweight" with a price target of $250.
5. **Supply Chain Concerns** - Some analysts note ongoing semiconductor supply constraints may impact Q1 production.

Last Updated: {datetime.utcnow().isoformat()}
"""
        
        dummy_sentiment = f"""
# Sentiment Analysis for {symbol}

## Overall Sentiment: BULLISH (Score: 7.2/10)

### Social Media Sentiment
- Twitter: 68% Positive, 22% Neutral, 10% Negative
- Reddit (r/stocks): Very Bullish - mentioned 1,234 times this week
- StockTwits: Bullish momentum with 5,432 messages

### News Sentiment
- Positive articles: 45
- Neutral articles: 23
- Negative articles: 8

### Key Themes
- Earnings optimism
- Product innovation
- Market expansion
- Some supply chain concerns

Last Updated: {datetime.utcnow().isoformat()}
"""
        
        dummy_market = f"""
# Market Analysis for {symbol}

## Price Action
- Current Price: $187.45
- 24h Change: +2.3%
- 52-Week High: $199.62
- 52-Week Low: $142.00
- Volume: 45.2M (above average)

## Technical Indicators
- RSI (14): 62 (Neutral-Bullish)
- MACD: Bullish crossover 3 days ago
- 50-Day MA: $178.20 (price above)
- 200-Day MA: $165.50 (price above)
- Support: $180, $175
- Resistance: $195, $200

## Trend Analysis
The stock is in a clear uptrend, trading above all major moving averages.
Recent breakout from consolidation pattern suggests continuation.

Last Updated: {datetime.utcnow().isoformat()}
"""
        
        dummy_fundamental = f"""
# Fundamental Analysis for {symbol}

## Valuation Metrics
- P/E Ratio: 28.5 (Industry avg: 25.2)
- Forward P/E: 24.1
- P/S Ratio: 7.2
- P/B Ratio: 45.3
- EV/EBITDA: 21.8

## Financial Health
- Revenue (TTM): $385.6B (+8% YoY)
- Net Income: $97.2B (+12% YoY)
- Free Cash Flow: $102.3B
- Debt/Equity: 1.52
- Current Ratio: 1.07

## Growth Metrics
- Revenue Growth (5Y CAGR): 11.2%
- EPS Growth (5Y CAGR): 15.8%
- Dividend Yield: 0.52%
- Payout Ratio: 14.8%

## Competitive Position
- Market leader in core segments
- Strong brand value and ecosystem
- High customer retention rates
- R&D investment: $29.9B annually

Last Updated: {datetime.utcnow().isoformat()}
"""
        
        return {
            "news": Report("news", dummy_news, datetime.utcnow().isoformat(), symbol),
            "sentiment": Report("sentiment", dummy_sentiment, datetime.utcnow().isoformat(), symbol),
            "market": Report("market", dummy_market, datetime.utcnow().isoformat(), symbol),
            "fundamental": Report("fundamental", dummy_fundamental, datetime.utcnow().isoformat(), symbol)
        }
    
    def fetch_all_reports(self, symbol: str) -> Dict[str, Report]:
        """Fetch all reports synchronously from Pathway API"""
        print(f"  📥 [SyncReportsClient] Fetching all reports for {symbol}")
        
        if self.use_dummy:
            reports = self._get_dummy_reports(symbol)
            print(f"    ✅ Generated 4 dummy reports")
            return reports
        
        with httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout) as client:
            try:
                # Pathway API returns all reports in one call
                print(f"    📄 Fetching all reports from {self.config.base_url}/reports/{symbol}")
                response = client.get(f"/reports/{symbol}")
                response.raise_for_status()
                data = response.json()
                
                reports = {}
                report_types = ["news", "sentiment", "market", "fundamental"]
                
                for report_type in report_types:
                    # Pathway API uses {report_type}_report as keys
                    content = data.get(f"{report_type}_report", "")
                    reports[report_type] = Report(
                        report_type=report_type,
                        content=content or "",
                        timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
                        symbol=symbol,
                        metadata={}
                    )
                    status = "✅" if content else "⚠️ empty"
                    print(f"    {status} {report_type} report")
                
                return reports
                
            except Exception as e:
                logger.error(f"Error fetching reports: {e}")
                print(f"    ❌ Error fetching reports: {e}")
                # Return empty reports on error
                return {
                    rt: Report(rt, "", datetime.utcnow().isoformat(), symbol, {"error": str(e)})
                    for rt in ["news", "sentiment", "market", "fundamental"]
                }
    
    def fetch_facilitator_report(self, symbol: str) -> Optional[Report]:
        """Fetch facilitator report synchronously from Pathway API"""
        print(f"  📥 [SyncReportsClient] Fetching facilitator report for {symbol}")
        
        if self.use_dummy:
            # Return None for first run (no previous facilitator report)
            print(f"    ℹ️ No previous facilitator report (first run)")
            return None
        
        with httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout) as client:
            try:
                # Use the main reports endpoint which includes facilitator_report
                response = client.get(f"/reports/{symbol.upper()}")
                response.raise_for_status()
                data = response.json()
                
                facilitator_content = data.get("facilitator_report")
                if facilitator_content:
                    print(f"    ✅ Facilitator report fetched")
                    return Report(
                        report_type="facilitator",
                        content=facilitator_content,
                        timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
                        symbol=symbol,
                        metadata={}
                    )
                else:
                    print(f"    ℹ️ No previous facilitator report found")
                    return None
            except Exception:
                print(f"    ℹ️ No previous facilitator report found")
                return None


class SyncRAGClient:
    """Synchronous version of RAGClient"""
    
    def __init__(self, config: Optional[RAGConfig] = None, use_dummy: bool = False):
        self.config = config or get_config().rag
        self.use_dummy = use_dummy
    
    def query(
        self,
        query: str,
        symbol: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Query RAG server synchronously"""
        print(f"  🔍 [SyncRAGClient] Querying RAG for: {query[:50]}...")
        
        if self.use_dummy:
            # Return dummy RAG results
            dummy_results = [
                {"content": f"According to SEC filings, {symbol or 'the company'} has shown consistent revenue growth over the past 5 quarters."},
                {"content": f"Industry analysts note that {symbol or 'the company'} maintains a competitive advantage in their core market segments."},
                {"content": f"Recent market data suggests increased institutional buying in {symbol or 'the stock'}."},
            ]
            print(f"    ✅ Returned {len(dummy_results)} dummy RAG results")
            return {"results": dummy_results}
        
        with httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout) as client:
            try:
                # Pathway RAG API uses "question" field, not "query"
                payload = {"question": query}
                
                response = client.post("/query", json=payload)
                response.raise_for_status()
                result = response.json()
                
                # Convert Pathway response format to our expected format
                # Pathway returns: {question, answer, sources}
                # We need: {results: [...]}
                sources = result.get('sources', [])
                answer = result.get('answer', '')
                
                # Format as expected by our code
                formatted_results = []
                if answer:
                    formatted_results.append({"content": answer})
                for source in sources:
                    formatted_results.append({
                        "content": source.get("content", ""),
                        "metadata": source.get("metadata", {})
                    })
                
                print(f"    ✅ RAG returned answer + {len(sources)} sources")
                return {"results": formatted_results, "answer": answer, "sources": sources}
            except Exception as e:
                logger.error(f"RAG query error: {e}")
                print(f"    ❌ RAG query error: {e}")
                return {"results": [], "error": str(e)}
    
    def get_counter_evidence(self, point: str, opposing_party: str, symbol: str) -> List[str]:
        """Get counter evidence synchronously"""
        print(f"  🔍 [SyncRAGClient] Getting counter evidence against {opposing_party}")
        
        if opposing_party == "bull":
            query = f"risks concerns negative indicators for {symbol}: {point}"
        else:
            query = f"opportunities positive indicators growth for {symbol}: {point}"
        
        result = self.query(query, symbol=symbol, limit=5)
        evidence = [r.get("content", r.get("text", "")) for r in result.get("results", []) if r]
        print(f"    ✅ Found {len(evidence)} counter evidence items")
        return evidence
