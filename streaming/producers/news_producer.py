import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from producers.base_producer import BaseProducer

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
        self.cache_file = os.path.join(os.path.dirname(__file__), 'news_cache.json')
        self.seen_articles = self._load_cache()
    
    def _load_cache(self):
        """Load previously seen articles from cache file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load cache file: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Save seen articles to cache file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.seen_articles, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache file: {e}")
    
    def _is_article_new(self, stock_symbol, article_url):
        """Check if article is new for this stock"""
        if stock_symbol not in self.seen_articles:
            return True
        return article_url not in self.seen_articles[stock_symbol]
    
    def _update_cache(self, stock_symbol, article_urls, max_cache_size=5):
        """Update cache with new article URLs, keeping only the most recent ones"""
        if stock_symbol not in self.seen_articles:
            self.seen_articles[stock_symbol] = []
        
        # Add new URLs to the front of the list
        for url in article_urls:
            if url not in self.seen_articles[stock_symbol]:
                self.seen_articles[stock_symbol].insert(0, url)
        
        # Keep only the most recent max_cache_size articles
        self.seen_articles[stock_symbol] = self.seen_articles[stock_symbol][:max_cache_size]
        
        # Save to disk
        self._save_cache()
    
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
                'q': f'{stock_symbol}',
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
            
            # Filter for new articles only
            articles = []
            new_article_urls = []
            
            for article in news_data['articles']:
                article_url = article.get('url')
                
                # Skip if we've seen this article before
                if not article_url or not self._is_article_new(stock_symbol, article_url):
                    continue
                
                articles.append({
                    'symbol': stock_symbol,
                    'timestamp': datetime.now().isoformat(),
                    'title': article.get('title'),
                    'description': article.get('description'),
                    'source': article.get('source', {}).get('name'),
                    'url': article_url,
                    'published_at': article.get('publishedAt')
                })
                new_article_urls.append(article_url)
            
            # Update cache with new articles
            if new_article_urls:
                self._update_cache(stock_symbol, new_article_urls)
            
            # If no new articles, return None
            if not articles:
                print(f"No new articles for {stock_symbol}")
                return None
            
            data = articles
            
            print(f"✓ {stock_symbol}: {len(articles)} NEW news articles")
            return data
            
        except Exception as e:
            print(f"Error fetching news for {stock_symbol}: {e}")
            return None


def main():
    """For standalone testing"""
    producer = NewsProducer()
    if producer.initialize():
        producer.fetch_and_send()
        producer.cleanup()


if __name__ == '__main__':
    main()