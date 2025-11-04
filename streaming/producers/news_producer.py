"""
Enhanced News Producer with multi-source fallback support
Sources: NewsAPI, Financial Modeling Prep, Alpha Vantage, Web Scraping
NOTE: Twitter and Reddit moved to SentimentProducer
"""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dotenv import load_dotenv
from producers.base_producer import BaseProducer
from bs4 import BeautifulSoup

load_dotenv()


class NewsProducer(BaseProducer):
    """Producer for stock-related news with multiple sources and fallback"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,GOOGL,MSFT').split(',')
        fetch_interval = int(os.getenv('NEWS_DATA_INTERVAL', '1800'))  # 30 minutes
        
        super().__init__(
            kafka_topic='news-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # API Keys
        self.newsapi_key = os.getenv('NEWS_API_KEY')
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.fmp_key = os.getenv('FMP_API_KEY')
        
        # Cache for deduplication
        self.cache_file = os.path.join(os.path.dirname(__file__), 'news_cache.json')
        self.seen_articles = self._load_cache()
    
    def _load_cache(self):
        """Load previously seen articles from cache file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save seen articles to cache file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.seen_articles, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache file: {e}")
    
    def _is_article_new(self, article_url: str) -> bool:
        """Check if article is new"""
        return article_url not in self.seen_articles
    
    def _mark_article_seen(self, article_url: str):
        """Mark article as seen"""
        self.seen_articles[article_url] = datetime.now().isoformat()
        # Clean old entries (older than 7 days)
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        self.seen_articles = {k: v for k, v in self.seen_articles.items() if v > cutoff}
        self._save_cache()
    
    def setup_sources(self):
        """Setup all news sources"""
        
        # Priority 0: NewsAPI
        if self.newsapi_key:
            self.register_source("NewsAPI", self._fetch_from_newsapi, priority=0)

        # Priority 1: Alpha Vantage
        if self.alpha_vantage_key:
            self.register_source("AlphaVantage", self._fetch_from_alpha_vantage, priority=1)
        
        # Priority 2: Financial Modeling Prep
        if self.fmp_key:
            self.register_source("FMP", self._fetch_from_fmp, priority=2)
        

    
    def _fetch_from_newsapi(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch news from NewsAPI"""
        params = {
            'q': stock_symbol,
            'apiKey': self.newsapi_key,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 5
        }
        
        response = requests.get('https://newsapi.org/v2/everything', params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data['status'] != 'ok' or data['totalResults'] == 0:
            return None
        
        articles = []
        for article in data['articles'][:5]:
            url = article.get('url', '')
            if self._is_article_new(url):
                articles.append({
                    'symbol': stock_symbol,
                    'timestamp': datetime.now().isoformat(),
                    'title': article.get('title', 'No Title'),
                    'description': article.get('description', ''),
                    'url': url,
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': article.get('publishedAt', ''),
                    'image_url': article.get('urlToImage', ''),
                    'data_source': 'NewsAPI'
                })
                self._mark_article_seen(url)
        
        return articles if articles else None
    
    def _fetch_from_fmp(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch news from Financial Modeling Prep API"""
        url = "https://financialmodelingprep.com/stable/news/stock"
        
        # Note: The stable API uses 'symbols' instead of the legacy 'tickers'
        params = {
            'symbols': stock_symbol,
            'limit': 5,
            'apikey': self.fmp_key
        }
        
        articles = []

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or not isinstance(data, list):
            return None
        
        for item in data:
            url = item.get('url', '')
            
            if url and self._is_article_new(url):
                articles.append({
                    'symbol': stock_symbol,
                    'timestamp': datetime.now().isoformat(),
                    'title': item.get('title', 'No Title'),
                    'description': item.get('text', ''),
                    'url': url,
                    'source': item.get('site', 'Unknown'),
                    'published_at': item.get('publishedDate', ''),
                    'image_url': item.get('image', ''),
                    'data_source': 'FMP'
                })
                self._mark_article_seen(url)
        
        return articles if articles else None
    
    def _fetch_from_alpha_vantage(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch news from Alpha Vantage"""
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'NEWS_SENTIMENT',
            'tickers': stock_symbol,
            'apikey': self.alpha_vantage_key,
            'limit': 5
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'feed' not in data or not data['feed']:
            return None
        
        articles = []
        for item in data['feed'][:5]:
            url = item.get('url', '')
            if self._is_article_new(url):
                articles.append({
                    'symbol': stock_symbol,
                    'timestamp': datetime.now().isoformat(),
                    'title': item.get('title', 'No Title'),
                    'description': item.get('summary', ''),
                    'url': url,
                    'source': item.get('source', 'Unknown'),
                    'published_at': item.get('time_published', ''),
                    'sentiment_score': item.get('overall_sentiment_score', 0),
                    'sentiment_label': item.get('overall_sentiment_label', 'Neutral'),
                    'image_url': item.get('banner_image', ''),
                    'data_source': 'AlphaVantage'
                })
                self._mark_article_seen(url)
        
        return articles if articles else None


def main():
    """For standalone testing"""
    producer = NewsProducer()
    producer.run()


if __name__ == '__main__':
    main()