"""
Enhanced Market Data Producer with multi-source fallback
Sources: Finnhub, Alpha Vantage, Yahoo Finance, CoinCap (for crypto), FMP
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
        self.coincap_key = os.getenv('COINCAP_API_KEY')  # Optional
        
        # Clients
        self.finnhub_client = None
        
        # Headers for scraping
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def setup_sources(self):
        """Setup all market data sources"""
        
        # Priority 0: Finnhub (primary)
        if self.finnhub_key:
            self.finnhub_client = finnhub.Client(api_key=self.finnhub_key)
            self.register_source("Finnhub", self._fetch_from_finnhub, priority=0)
        
        # Priority 1: Financial Modeling Prep
        if self.fmp_key:
            self.register_source("FMP", self._fetch_from_fmp, priority=1)
        
        # Priority 2: Alpha Vantage
        if self.alpha_vantage_key:
            self.register_source("AlphaVantage", self._fetch_from_alpha_vantage, priority=2)
        
        # Priority 3: CoinCap (for crypto symbols)
        self.register_source("CoinCap", self._fetch_from_coincap, priority=3)
        
        # Priority 4: Yahoo Finance Scraper (fallback)
        self.register_source("YahooScraper", self._fetch_from_yahoo_scraper, priority=4)
    
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
        """Fetch from Financial Modeling Prep"""
        url = f"https://financialmodelingprep.com/api/v3/quote/{stock_symbol}"
        params = {'apikey': self.fmp_key}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or len(data) == 0:
            return None
        
        quote = data[0]
        
        return {
            'symbol': stock_symbol,
            'timestamp': datetime.now().isoformat(),
            'current_price': quote.get('price', 0),
            'high': quote.get('dayHigh', 0),
            'low': quote.get('dayLow', 0),
            'open': quote.get('open', 0),
            'previous_close': quote.get('previousClose', 0),
            'change': quote.get('change', 0),
            'change_percent': quote.get('changesPercentage', 0),
            'volume': quote.get('volume', 0),
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
    
    def _fetch_from_coincap(self, stock_symbol: str) -> Optional[Dict]:
        """Fetch from CoinCap API (for crypto)"""
        # CoinCap uses different symbols (e.g., 'bitcoin' not 'BTC')
        # This is a simplified mapping - you may want to expand this
        crypto_map = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'DOGE': 'dogecoin'
        }
        
        asset_id = crypto_map.get(stock_symbol.upper())
        if not asset_id:
            # Try using the symbol directly
            asset_id = stock_symbol.lower()
        
        url = f"https://api.coincap.io/v2/assets/{asset_id}"
        headers = {}
        if self.coincap_key:
            headers['Authorization'] = f'Bearer {self.coincap_key}'
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' not in data:
            return None
        
        asset = data['data']
        current_price = float(asset.get('priceUsd', 0))
        change_percent = float(asset.get('changePercent24Hr', 0))
        
        return {
            'symbol': stock_symbol,
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'change_percent': change_percent,
            'volume_24h': float(asset.get('volumeUsd24Hr', 0)),
            'market_cap': float(asset.get('marketCapUsd', 0)),
            'data_source': 'CoinCap'
        }
    
    def _fetch_from_yahoo_scraper(self, stock_symbol: str) -> Optional[Dict]:
        """Web scrape from Yahoo Finance (final fallback)"""
        url = f"https://finance.yahoo.com/quote/{stock_symbol}"
        
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract price data (Yahoo Finance structure - may need updates)
        try:
            # Current price
            price_elem = soup.find('fin-streamer', {'data-symbol': stock_symbol, 'data-field': 'regularMarketPrice'})
            current_price = float(price_elem.get('value', 0)) if price_elem else 0
            
            # Change
            change_elem = soup.find('fin-streamer', {'data-symbol': stock_symbol, 'data-field': 'regularMarketChange'})
            change = float(change_elem.get('value', 0)) if change_elem else 0
            
            # Change percent
            change_pct_elem = soup.find('fin-streamer', {'data-symbol': stock_symbol, 'data-field': 'regularMarketChangePercent'})
            change_percent = float(change_pct_elem.get('value', 0)) if change_pct_elem else 0
            
            if current_price == 0:
                return None
            
            return {
                'symbol': stock_symbol,
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price,
                'change': change,
                'change_percent': change_percent,
                'data_source': 'YahooScraper'
            }
            
        except Exception as e:
            raise Exception(f"Yahoo scraping parse error: {e}")


def main():
    """For standalone testing"""
    producer = MarketDataProducer()
    producer.run()


if __name__ == '__main__':
    main()