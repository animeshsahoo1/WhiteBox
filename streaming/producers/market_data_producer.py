import os
import finnhub
from datetime import datetime
from dotenv import load_dotenv
from streaming.producers.base_producer import BaseProducer

load_dotenv()


class MarketDataProducer(BaseProducer):
    """Producer for real-time market data using Finnhub"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS').split(',')
        fetch_interval = int(os.getenv('MARKET_DATA_INTERVAL'))
        
        super().__init__(
            kafka_topic='market-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        self.finnhub_client = None
    
    def setup(self):
        """Setup Finnhub client"""
        if not self.finnhub_key:
            print("ERROR: FINNHUB_API_KEY not found in .env")
            return False
        
        self.finnhub_client = finnhub.Client(api_key=self.finnhub_key)
        print("✓ Connected to Finnhub API")
        return True
    
    def fetch_data(self, stock_symbol):
        """Fetch real-time quote data"""
        try:
            quote = self.finnhub_client.quote(stock_symbol)
            
            if not quote or quote.get('c') == 0:
                print(f"No data for {stock_symbol}")
                return None
            
            data = {
                'symbol': stock_symbol,
                'timestamp': datetime.now().isoformat(),
                'current_price': quote['c'],
                'high': quote['h'],
                'low': quote['l'],
                'open': quote['o'],
                'previous_close': quote['pc'],
                'change': quote['c'] - quote['pc'],
                'change_percent': ((quote['c'] - quote['pc']) / quote['pc']) * 100
            }
            
            print(f"✓ {stock_symbol}: ${data['current_price']:.2f} ({data['change_percent']:+.2f}%)")
            return data
            
        except Exception as e:
            print(f"Error fetching {stock_symbol}: {e}")
            return None


def main():
    """For standalone testing"""
    producer = MarketDataProducer()
    if producer.initialize():
        producer.fetch_and_send()
        producer.cleanup()


if __name__ == '__main__':
    main()