import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from streaming.producers.base_producer import BaseProducer

load_dotenv()


class NewsProducer(BaseProducer):
    """Producer for stock-related news using NewsAPI"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,GOOGL,MSFT').split(',')
        fetch_interval = int(os.getenv('NEWS_DATA_INTERVAL', '1800'))  # 30 minutes
        
        super().__init__(
            kafka_topic='news-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        self.api_key = os.getenv('NEWS_API_KEY')
        self.base_url = 'https://newsapi.org/v2/everything'
    
    def setup(self):
        """Setup NewsAPI client"""
        if not self.api_key:
            print("ERROR: NEWS_API_KEY not found in .env")
            return False
        
        print("✓ NewsAPI ready")
        return True
    
    def fetch_data(self, stock_symbol):
        """Fetch latest news for stock symbol"""
        try:
            # NewsAPI parameters
            params = {
                'q': f'{stock_symbol} stock OR {self._get_company_name(stock_symbol)}',
                'apiKey': self.api_key,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 5  # Get top 5 articles
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            news_data = response.json()
            
            if news_data['status'] != 'ok' or news_data['totalResults'] == 0:
                print(f"No news for {stock_symbol}")
                return None
            
            articles = []
            for article in news_data['articles']:
                articles.append({
                    'title': article.get('title'),
                    'description': article.get('description'),
                    'source': article.get('source', {}).get('name'),
                    'url': article.get('url'),
                    'published_at': article.get('publishedAt')
                })
            
            data = {
                'symbol': stock_symbol,
                'timestamp': datetime.now().isoformat(),
                'total_results': news_data['totalResults'],
                'articles': articles
            }
            
            print(f"✓ {stock_symbol}: {len(articles)} news articles")
            return data
            
        except Exception as e:
            print(f"Error fetching news for {stock_symbol}: {e}")
            return None
    
    def _get_company_name(self, symbol):
        """Get company name from stock symbol"""
        company_map = {
            'AAPL': 'Apple',
            'GOOGL': 'Google',
            'MSFT': 'Microsoft',
            'TSLA': 'Tesla',
            'AMZN': 'Amazon',
            'META': 'Meta',
            'NVDA': 'NVIDIA'
        }
        return company_map.get(symbol, symbol)


def main():
    """For standalone testing"""
    producer = NewsProducer()
    if producer.initialize():
        producer.fetch_and_send()
        producer.cleanup()


if __name__ == '__main__':
    main()