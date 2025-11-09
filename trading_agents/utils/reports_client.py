"""
Client to fetch reports from the Pathway Reports API.
This allows trading agents to retrieve the latest analysis reports.
"""

import os
import requests
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class StockReports:
    """Container for all stock reports"""
    symbol: str
    fundamental_report: Optional[str] = None
    market_report: Optional[str] = None
    news_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if all 4 reports are available"""
        return all([
            self.fundamental_report,
            self.market_report,
            self.news_report,
            self.sentiment_report
        ])
    
    def missing_reports(self) -> list[str]:
        """Get list of missing report types"""
        missing = []
        if not self.fundamental_report:
            missing.append("fundamental")
        if not self.market_report:
            missing.append("market")
        if not self.news_report:
            missing.append("news")
        if not self.sentiment_report:
            missing.append("sentiment")
        return missing


class PathwayReportsClient:
    """Client to fetch reports from Pathway FastAPI service"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the Pathway Reports API. 
                     If not provided, uses PATHWAY_API_URL env var or defaults to localhost
        """
        if base_url:
            self.base_url = base_url.rstrip('/')
        else:
            self.base_url = os.getenv('PATHWAY_API_URL', 'http://localhost:8000').rstrip('/')
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def health_check(self) -> bool:
        """
        Check if the Pathway API is healthy and responsive.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    def get_all_reports(self, symbol: str) -> StockReports:
        """
        Get all available reports for a stock symbol.
        
        Args:
            symbol: Stock ticker symbol (e.g., AAPL, GOOGL)
        
        Returns:
            StockReports object with all available reports
            
        Raises:
            Exception: If API request fails or symbol not found
        """
        symbol = symbol.upper()
        
        try:
            response = self.session.get(
                f"{self.base_url}/reports/{symbol}",
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            return StockReports(
                symbol=data['symbol'],
                fundamental_report=data.get('fundamental_report'),
                market_report=data.get('market_report'),
                news_report=data.get('news_report'),
                sentiment_report=data.get('sentiment_report')
            )
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(
                    f"No reports found for {symbol}. "
                    "Make sure the symbol is correct and data has been processed."
                ) from e
            else:
                raise Exception(f"API request failed: {e}") from e
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to connect to Pathway API: {e}") from e
    
    def get_fundamental_report(self, symbol: str) -> str:
        """Get fundamental analysis report for a stock"""
        symbol = symbol.upper()
        
        try:
            response = self.session.get(
                f"{self.base_url}/reports/{symbol}/fundamental",
                timeout=30
            )
            response.raise_for_status()
            return response.json()['content']
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Fundamental report not found for {symbol}") from e
            raise
    
    def get_market_report(self, symbol: str) -> str:
        """Get market analysis report for a stock"""
        symbol = symbol.upper()
        
        try:
            response = self.session.get(
                f"{self.base_url}/reports/{symbol}/market",
                timeout=30
            )
            response.raise_for_status()
            return response.json()['content']
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Market report not found for {symbol}") from e
            raise
    
    def get_news_report(self, symbol: str) -> str:
        """Get news analysis report for a stock"""
        symbol = symbol.upper()
        
        try:
            response = self.session.get(
                f"{self.base_url}/reports/{symbol}/news",
                timeout=30
            )
            response.raise_for_status()
            return response.json()['content']
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"News report not found for {symbol}") from e
            raise
    
    def get_sentiment_report(self, symbol: str) -> str:
        """Get sentiment analysis report for a stock"""
        symbol = symbol.upper()
        
        try:
            response = self.session.get(
                f"{self.base_url}/reports/{symbol}/sentiment",
                timeout=30
            )
            response.raise_for_status()
            return response.json()['content']
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Sentiment report not found for {symbol}") from e
            raise
    
    def get_available_symbols(self) -> list[str]:
        """
        Get list of all stock symbols that have at least one report available.
        
        Returns:
            List of stock symbols
        """
        try:
            response = self.session.get(
                f"{self.base_url}/symbols",
                timeout=10
            )
            response.raise_for_status()
            return response.json()['symbols']
        except Exception as e:
            print(f"Failed to get available symbols: {e}")
            return []
    
    def wait_for_reports(self, symbol: str, timeout: int = 300, check_interval: int = 10) -> StockReports:
        """
        Wait for all 4 reports to be available for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            timeout: Maximum time to wait in seconds (default: 300)
            check_interval: Time between checks in seconds (default: 10)
        
        Returns:
            StockReports with all 4 reports
            
        Raises:
            TimeoutError: If reports are not available within timeout
        """
        import time
        
        symbol = symbol.upper()
        elapsed = 0
        
        print(f"⏳ Waiting for all reports for {symbol}...")
        
        while elapsed < timeout:
            try:
                reports = self.get_all_reports(symbol)
                
                if reports.is_complete():
                    print(f"✅ All reports ready for {symbol}")
                    return reports
                else:
                    missing = reports.missing_reports()
                    print(f"⏳ Still waiting for: {', '.join(missing)}")
                    
            except Exception as e:
                print(f"⏳ Reports not yet available: {e}")
            
            time.sleep(check_interval)
            elapsed += check_interval
        
        raise TimeoutError(
            f"Timeout waiting for reports for {symbol}. "
            f"Waited {timeout} seconds."
        )


# Convenience function for quick usage
def fetch_reports(symbol: str, api_url: Optional[str] = None) -> StockReports:
    """
    Convenience function to quickly fetch all reports for a symbol.
    
    Args:
        symbol: Stock ticker symbol
        api_url: Optional custom API URL
    
    Returns:
        StockReports object
    """
    client = PathwayReportsClient(base_url=api_url)
    return client.get_all_reports(symbol)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python reports_client.py <SYMBOL>")
        print("Example: python reports_client.py AAPL")
        sys.exit(1)
    
    symbol = sys.argv[1]
    
    client = PathwayReportsClient()
    
    print(f"🔍 Fetching reports for {symbol}...")
    
    # Check health
    if not client.health_check():
        print("❌ Pathway API is not healthy!")
        sys.exit(1)
    
    print("✅ Pathway API is healthy")
    
    # Fetch reports
    try:
        reports = client.get_all_reports(symbol)
        
        print(f"\n📊 Reports for {reports.symbol}:")
        print(f"  - Fundamental: {'✓' if reports.fundamental_report else '✗'}")
        print(f"  - Market: {'✓' if reports.market_report else '✗'}")
        print(f"  - News: {'✓' if reports.news_report else '✗'}")
        print(f"  - Sentiment: {'✓' if reports.sentiment_report else '✗'}")
        
        if reports.is_complete():
            print("\n✅ All reports available!")
        else:
            missing = reports.missing_reports()
            print(f"\n⚠️  Missing reports: {', '.join(missing)}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
