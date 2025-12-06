"""
OPTIONAL: Pathway-Native Market Data Source
============================================
This demonstrates how to use Pathway's ConnectorSubject to create a
data source that integrates directly with Pathway's streaming engine.

Benefits:
- No Kafka required (direct streaming)
- Pathway handles backpressure
- Integrated with Pathway's persistence

Trade-offs:
- Less flexible than standalone producers
- Requires Pathway runtime
- Circuit breaker needs custom implementation

Usage:
    import pathway as pw
    from producers.pathway_market_source import MarketDataSubject
    
    # Create Pathway table directly from market data
    table = pw.io.python.read(
        MarketDataSubject(symbols=["AAPL", "GOOGL"], poll_interval=60),
        schema=MarketDataSchema,
        autocommit_duration_ms=5000
    )
"""

import os
import time
import requests
from datetime import datetime
from typing import List, Optional, Dict, Any

import pathway as pw
from pathway.io.python import ConnectorSubject
from dotenv import load_dotenv

load_dotenv()


class MarketDataSchema(pw.Schema):
    """Schema for market data - matches Kafka message format."""
    symbol: str
    timestamp: str
    current_price: float
    high: float
    low: float
    open: float
    previous_close: float
    change: float
    change_percent: float
    volume: float = 0.0
    data_source: str = "unknown"


class MarketDataSubject(ConnectorSubject):
    """
    Pathway ConnectorSubject that polls market data APIs.
    
    This is an alternative to the Kafka-based approach.
    Use when you want direct Pathway integration without Kafka.
    """
    
    # Disable deletions for better performance (market data is append-only)
    deletions_enabled = False
    
    def __init__(
        self, 
        symbols: List[str],
        poll_interval: int = 60,
        fmp_key: Optional[str] = None,
        finnhub_key: Optional[str] = None
    ):
        super().__init__(datasource_name="market_data_source")
        self.symbols = symbols
        self.poll_interval = poll_interval
        self.fmp_key = fmp_key or os.getenv('FMP_API_KEY')
        self.finnhub_key = finnhub_key or os.getenv('FINNHUB_API_KEY')
        self._running = True
    
    def run(self):
        """Main polling loop - called by Pathway in a separate thread."""
        print(f"🚀 MarketDataSubject started for {self.symbols}")
        
        while self._running:
            for symbol in self.symbols:
                try:
                    data = self._fetch_quote(symbol)
                    if data:
                        # Send data directly to Pathway
                        self.next(**data)
                except Exception as e:
                    print(f"⚠️ Error fetching {symbol}: {e}")
            
            # Commit batch after fetching all symbols
            self.commit()
            
            # Wait for next poll
            time.sleep(self.poll_interval)
    
    def _fetch_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch quote from FMP or Finnhub."""
        # Try FMP first
        if self.fmp_key:
            data = self._fetch_from_fmp(symbol)
            if data:
                return data
        
        # Fallback to Finnhub
        if self.finnhub_key:
            data = self._fetch_from_finnhub(symbol)
            if data:
                return data
        
        return None
    
    def _fetch_from_fmp(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch from Financial Modeling Prep API."""
        try:
            url = "https://financialmodelingprep.com/stable/quote"
            response = requests.get(
                url, 
                params={"symbol": symbol, "apikey": self.fmp_key},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and len(data) > 0:
                quote = data[0]
                return {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'current_price': float(quote.get('price', 0)),
                    'high': float(quote.get('dayHigh', 0)),
                    'low': float(quote.get('dayLow', 0)),
                    'open': float(quote.get('open', 0)),
                    'previous_close': float(quote.get('previousClose', 0)),
                    'change': float(quote.get('change', 0)),
                    'change_percent': float(quote.get('changesPercentage', 0)),
                    'volume': float(quote.get('volume', 0)),
                    'data_source': 'FMP'
                }
        except Exception as e:
            print(f"⚠️ FMP error: {e}")
        return None
    
    def _fetch_from_finnhub(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch from Finnhub API."""
        try:
            url = f"https://finnhub.io/api/v1/quote"
            response = requests.get(
                url,
                params={"symbol": symbol, "token": self.finnhub_key},
                timeout=10
            )
            response.raise_for_status()
            quote = response.json()
            
            if quote and quote.get('c', 0) > 0:
                return {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'current_price': float(quote['c']),
                    'high': float(quote['h']),
                    'low': float(quote['l']),
                    'open': float(quote['o']),
                    'previous_close': float(quote['pc']),
                    'change': float(quote['c'] - quote['pc']),
                    'change_percent': float((quote['c'] - quote['pc']) / quote['pc'] * 100),
                    'volume': 0.0,  # Finnhub quote doesn't include volume
                    'data_source': 'Finnhub'
                }
        except Exception as e:
            print(f"⚠️ Finnhub error: {e}")
        return None
    
    def on_stop(self):
        """Called when Pathway stops the connector."""
        self._running = False
        print("🛑 MarketDataSubject stopped")


# Example usage (when run directly)
if __name__ == "__main__":
    # This shows how to use the subject with Pathway
    symbols = os.getenv('STOCKS', 'AAPL,GOOGL').split(',')
    
    # Create Pathway table directly
    table = pw.io.python.read(
        MarketDataSubject(symbols=symbols, poll_interval=60),
        schema=MarketDataSchema,
        autocommit_duration_ms=5000
    )
    
    # Example: Print the table
    pw.io.csv.write(table, "market_data_output.csv")
    
    print("Starting Pathway with MarketDataSubject...")
    pw.run()
