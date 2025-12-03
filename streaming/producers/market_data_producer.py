"""
Enhanced Market Data Producer with multi-source fallback
Sources: Finnhub, Alpha Vantage, FMP
"""
import os
import requests
import finnhub
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv
from producers.base_producer import BaseProducer
from bs4 import BeautifulSoup

load_dotenv()


class MarketDataProducer(BaseProducer):
    """Producer for real-time market data with multiple sources"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,GOOGL,MSFT').split(',')
        fetch_interval = int(os.getenv('MARKET_DATA_INTERVAL', '60'))
        
        super().__init__(
            kafka_topic='market-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # API Keys
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.fmp_key = os.getenv('FMP_API_KEY')
        
        # Clients
        self.finnhub_client = None
    
    def setup_sources(self):
        """Setup all market data sources"""
        
        # Priority 0: fmp
        if self.fmp_key:
            self.register_source("FMP", self._fetch_from_fmp, priority=0)
        

        # Priority 1: finhub
        if self.finnhub_key:
            self.finnhub_client = finnhub.Client(api_key=self.finnhub_key)
            self.register_source("Finnhub", self._fetch_from_finnhub, priority=1)
        
        
        # Priority 2: Alpha Vantage
        if self.alpha_vantage_key:
            self.register_source("AlphaVantage", self._fetch_from_alpha_vantage, priority=2)
    
    def _fetch_from_finnhub(self, stock_symbol: str) -> Optional[Dict]:
        """Fetch from Finnhub API"""
        quote = self.finnhub_client.quote(stock_symbol)
        
        if not quote or quote.get('c') == 0:
            return None
        
        return {
            'symbol': stock_symbol,
            'timestamp': datetime.now().isoformat(),
            'current_price': quote['c'],
            'high': quote['h'],
            'low': quote['l'],
            'open': quote['o'],
            'previous_close': quote['pc'],
            'change': quote['c'] - quote['pc'],
            'change_percent': ((quote['c'] - quote['pc']) / quote['pc']) * 100,
            'data_source': 'Finnhub'
        }
    
    def _fetch_from_fmp(self, stock_symbol: str) -> Optional[Dict]:
        url = "https://financialmodelingprep.com/stable/quote"
        params = {
            "symbol": stock_symbol,
            "apikey": self.fmp_key
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        
        # The Stock Quote API returns a list, even for a single symbol.
        if not data or not isinstance(data, list) or len(data) == 0:
            print(f"FMP returned no data for symbol: {stock_symbol}")
            return None
        
        quote = data[0]
        
        # Extract and standardize the data fields
        return {
            'symbol': stock_symbol,
            # Capture the time the data was successfully fetched
            'timestamp': datetime.now().isoformat(),
            'current_price': quote.get('price'),  # FMP returns floats, 0.0 might be better default if expecting numerical ops later
            'high': quote.get('dayHigh'),
            'low': quote.get('dayLow'),
            'open': quote.get('open'),
            'previous_close': quote.get('previousClose'),
            'change': quote.get('change'),
            'change_percent': quote.get('changesPercentage'),
            'volume': quote.get('volume'),
            'data_source': 'FMP'
        }
    
    def _fetch_from_alpha_vantage(self, stock_symbol: str) -> Optional[Dict]:
        """Fetch from Alpha Vantage"""
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': stock_symbol,
            'apikey': self.alpha_vantage_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'Global Quote' not in data or not data['Global Quote']:
            return None
        
        quote = data['Global Quote']
        
        current_price = float(quote.get('05. price', 0))
        previous_close = float(quote.get('08. previous close', 0))
        
        return {
            'symbol': stock_symbol,
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'high': float(quote.get('03. high', 0)),
            'low': float(quote.get('04. low', 0)),
            'open': float(quote.get('02. open', 0)),
            'previous_close': previous_close,
            'change': float(quote.get('09. change', 0)),
            'change_percent': float(quote.get('10. change percent', '0').replace('%', '')),
            'volume': int(quote.get('06. volume', 0)),
            'data_source': 'AlphaVantage'
        }

def main():
    """For standalone testing"""
    producer = MarketDataProducer()
    producer.run()


if __name__ == '__main__':
    main()