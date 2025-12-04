"""
Enhanced News Producer with multi-source fallback support
Sources: NewsAPI, Financial Modeling Prep, Alpha Vantage
Fetches: Company news, Sector/Peer news, Global/Macro news
"""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dotenv import load_dotenv
from producers.base_producer import BaseProducer

load_dotenv()


class NewsProducer(BaseProducer):
    """Producer for stock-related news with multiple sources and fallback
    
    Fetches three types of news:
    - Company news: Direct news about the stock symbol
    - Sector news: News about peer/competitor companies in same sector
    - Global news: Macro/market-wide news affecting all stocks
    """
    
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
        
        # Cache for stock peers (to reduce API calls)
        self.peers_cache_file = os.path.join(os.path.dirname(__file__), 'peers_cache.json')
        self.peers_cache = self._load_peers_cache()
        
        # Cache for stock profiles (sector info)
        self.profile_cache_file = os.path.join(os.path.dirname(__file__), 'profile_cache.json')
        self.profile_cache = self._load_profile_cache()
        
        # Track last global news fetch to avoid fetching every cycle
        self.last_global_fetch = None
        self.global_fetch_interval = 1800  # Fetch global news every 30 min
    
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
    
    def _load_peers_cache(self):
        """Load cached peer companies"""
        if os.path.exists(self.peers_cache_file):
            try:
                with open(self.peers_cache_file, 'r') as f:
                    cache = json.load(f)
                    # Check if cache is still valid (24 hours)
                    if cache.get('timestamp'):
                        cache_time = datetime.fromisoformat(cache['timestamp'])
                        if datetime.now() - cache_time < timedelta(hours=24):
                            return cache.get('peers', {})
            except:
                pass
        return {}
    
    def _save_peers_cache(self):
        """Save peer companies cache"""
        try:
            with open(self.peers_cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'peers': self.peers_cache
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save peers cache: {e}")
    
    def _load_profile_cache(self):
        """Load cached stock profiles (sector info)"""
        if os.path.exists(self.profile_cache_file):
            try:
                with open(self.profile_cache_file, 'r') as f:
                    cache = json.load(f)
                    # Profiles rarely change, cache for 7 days
                    if cache.get('timestamp'):
                        cache_time = datetime.fromisoformat(cache['timestamp'])
                        if datetime.now() - cache_time < timedelta(days=7):
                            return cache.get('profiles', {})
            except:
                pass
        return {}
    
    def _save_profile_cache(self):
        """Save stock profile cache"""
        try:
            with open(self.profile_cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'profiles': self.profile_cache
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save profile cache: {e}")
    
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
    
    # ==================== STOCK PROFILE & PEERS ====================
    
    def _get_stock_profile(self, stock_symbol: str) -> Optional[Dict]:
        """Get stock profile (sector, industry) from FMP - uses cache"""
        # Check cache first
        if stock_symbol in self.profile_cache:
            return self.profile_cache[stock_symbol]
        
        if not self.fmp_key:
            return None
        
        try:
            url = "https://financialmodelingprep.com/stable/profile"
            params = {
                'symbol': stock_symbol,
                'apikey': self.fmp_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and len(data) > 0:
                profile = {
                    'symbol': stock_symbol,
                    'sector': data[0].get('sector', ''),
                    'industry': data[0].get('industry', ''),
                    'companyName': data[0].get('companyName', '')
                }
                self.profile_cache[stock_symbol] = profile
                self._save_profile_cache()
                return profile
        except Exception as e:
            print(f"  ⚠️  Could not fetch profile for {stock_symbol}: {e}")
        
        return None
    
    def _get_stock_peers(self, stock_symbol: str) -> List[str]:
        """Get peer companies from FMP - uses cache"""
        # Check cache first
        if stock_symbol in self.peers_cache:
            return self.peers_cache[stock_symbol]
        
        if not self.fmp_key:
            return []
        
        try:
            url = "https://financialmodelingprep.com/stable/stock-peers"
            params = {
                'symbol': stock_symbol,
                'apikey': self.fmp_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and len(data) > 0:
                # FMP returns a flat array of peer objects: [{"symbol": "GOOGL", ...}, ...]
                # NOT a nested peersList
                if 'peersList' in data[0]:
                    # Old format
                    peers = data[0].get('peersList', [])[:5]
                else:
                    # New format: extract symbol from each peer object
                    peers = [peer.get('symbol') for peer in data if peer.get('symbol') and peer.get('symbol') != stock_symbol][:5]
                
                self.peers_cache[stock_symbol] = peers
                self._save_peers_cache()
                print(f"  📊 Found {len(peers)} peers for {stock_symbol}: {peers[:3]}...")
                return peers
        except Exception as e:
            print(f"  ⚠️  Could not fetch peers for {stock_symbol}: {e}")
        
        return []
    
    # ==================== GLOBAL NEWS ====================
    
    def _fetch_global_news_fmp(self) -> Optional[List[Dict]]:
        """Fetch global/macro news from FMP general news endpoint"""
        if not self.fmp_key:
            return None
        
        try:
            url = "https://financialmodelingprep.com/stable/news/general-latest"
            params = {
                'page': 0,
                'limit': 10,
                'apikey': self.fmp_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data or not isinstance(data, list):
                return None
            
            articles = []
            for item in data:
                article_url = item.get('url', '')
                
                if article_url and self._is_article_new(article_url):
                    articles.append({
                        'symbol': 'GLOBAL',
                        'news_type': 'global',
                        'timestamp': datetime.now().isoformat(),
                        'title': item.get('title', 'No Title'),
                        'description': item.get('text', ''),
                        'url': article_url,
                        'source': item.get('site', 'Unknown'),
                        'published_at': item.get('publishedDate', ''),
                        'image_url': item.get('image', ''),
                        'data_source': 'FMP',
                        'related_to': None
                    })
                    self._mark_article_seen(article_url)
            
            return articles if articles else None
            
        except Exception as e:
            print(f"  ❌ Global news fetch error: {e}")
            return None
    
    def _should_fetch_global_news(self) -> bool:
        """Check if we should fetch global news this cycle"""
        if self.last_global_fetch is None:
            return True
        
        time_since_last = (datetime.now() - self.last_global_fetch).total_seconds()
        return time_since_last >= self.global_fetch_interval
    
    def setup_sources(self):
        """Setup all news sources"""
        
        # Priority 0: Financial Modeling Prep (highest priority for Starter plan)
        if self.fmp_key:
            self.register_source("FMP", self._fetch_from_fmp, priority=0)
        
        # Priority 1: Alpha Vantage
        if self.alpha_vantage_key:
            self.register_source("AlphaVantage", self._fetch_from_alpha_vantage, priority=1)
        
        # Priority 2: NewsAPI (lowest priority)
        if self.newsapi_key:
            self.register_source("NewsAPI", self._fetch_from_newsapi, priority=2)

    # ==================== COMPANY NEWS SOURCES ====================

    # ==================== COMPANY NEWS SOURCES ====================
    
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
                    'news_type': 'company',
                    'timestamp': datetime.now().isoformat(),
                    'title': article.get('title', 'No Title'),
                    'description': article.get('description', ''),
                    'url': url,
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': article.get('publishedAt', ''),
                    'image_url': article.get('urlToImage', ''),
                    'data_source': 'NewsAPI',
                    'related_to': None
                })
                self._mark_article_seen(url)
        
        return articles if articles else None
    
    def _fetch_from_fmp(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch news from Financial Modeling Prep API"""
        url = "https://financialmodelingprep.com/stable/news/stock"
        
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
            article_url = item.get('url', '')
            
            if article_url and self._is_article_new(article_url):
                articles.append({
                    'symbol': stock_symbol,
                    'news_type': 'company',
                    'timestamp': datetime.now().isoformat(),
                    'title': item.get('title', 'No Title'),
                    'description': item.get('text', ''),
                    'url': article_url,
                    'source': item.get('site', 'Unknown'),
                    'published_at': item.get('publishedDate', ''),
                    'image_url': item.get('image', ''),
                    'data_source': 'FMP',
                    'related_to': None
                })
                self._mark_article_seen(article_url)
        
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
            article_url = item.get('url', '')
            if self._is_article_new(article_url):
                articles.append({
                    'symbol': stock_symbol,
                    'news_type': 'company',
                    'timestamp': datetime.now().isoformat(),
                    'title': item.get('title', 'No Title'),
                    'description': item.get('summary', ''),
                    'url': article_url,
                    'source': item.get('source', 'Unknown'),
                    'published_at': item.get('time_published', ''),
                    'sentiment_score': item.get('overall_sentiment_score', 0),
                    'sentiment_label': item.get('overall_sentiment_label', 'Neutral'),
                    'image_url': item.get('banner_image', ''),
                    'data_source': 'AlphaVantage',
                    'related_to': None
                })
                self._mark_article_seen(article_url)
        
        return articles if articles else None
    
    # ==================== SECTOR/PEER NEWS ====================
    
    def _fetch_peer_news(self, stock_symbol: str, peers: List[str]) -> List[Dict]:
        """Fetch news for peer companies and tag as sector news"""
        if not peers or not self.fmp_key:
            return []
        
        # Take top 2 peers to limit API calls
        top_peers = peers[:2]
        peer_symbols = ','.join(top_peers)
        
        try:
            url = "https://financialmodelingprep.com/stable/news/stock"
            params = {
                'symbols': peer_symbols,
                'limit': 5,
                'apikey': self.fmp_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data or not isinstance(data, list):
                return []
            
            articles = []
            for item in data:
                article_url = item.get('url', '')
                
                if article_url and self._is_article_new(article_url):
                    # Determine which peer this news is about
                    article_symbol = item.get('symbol', top_peers[0] if top_peers else 'SECTOR')
                    
                    articles.append({
                        'symbol': article_symbol,
                        'news_type': 'sector',
                        'timestamp': datetime.now().isoformat(),
                        'title': item.get('title', 'No Title'),
                        'description': item.get('text', ''),
                        'url': article_url,
                        'source': item.get('site', 'Unknown'),
                        'published_at': item.get('publishedDate', ''),
                        'image_url': item.get('image', ''),
                        'data_source': 'FMP',
                        'related_to': stock_symbol  # Link back to original stock
                    })
                    self._mark_article_seen(article_url)
            
            return articles
            
        except Exception as e:
            print(f"  ⚠️  Peer news fetch error for {stock_symbol}: {e}")
            return []
    
    # ==================== ENHANCED FETCH CYCLE ====================
    
    def fetch_and_send(self):
        """Enhanced fetch cycle: Company + Sector + Global news (global attached to each stock)"""
        print(f"\n[{self.name}] [{datetime.now().strftime('%H:%M:%S')}] Starting enhanced fetch cycle...")
        
        # Print source status summary
        self._print_source_status()
        
        all_articles = []
        global_news_cache = []  # Store global news to duplicate for each stock
        
        # 1. Fetch GLOBAL news (once per cycle if interval elapsed)
        if self._should_fetch_global_news():
            print(f"\n  🌍 Fetching global/macro news...")
            global_news = self._fetch_global_news_fmp()
            if global_news:
                global_news_cache = global_news  # Cache for duplication
                print(f"  ✅ Got {len(global_news)} global news articles (will attach to each stock)")
                self.last_global_fetch = datetime.now()
            else:
                print(f"  ℹ️  No new global news")
        
        # 2. For each stock: fetch COMPANY news + SECTOR news + attach GLOBAL news
        for stock in self.stocks:
            try:
                print(f"\n  📰 Processing {stock}...")
                
                # 2a. Fetch company-specific news
                company_news = self.fetch_data_with_fallback(stock)
                if company_news:
                    all_articles.extend(company_news)
                    print(f"    ✅ Got {len(company_news)} company news articles")
                
                # 2b. Get peers and fetch sector news
                peers = self._get_stock_peers(stock)
                if peers:
                    peer_news = self._fetch_peer_news(stock, peers)
                    if peer_news:
                        all_articles.extend(peer_news)
                        print(f"    ✅ Got {len(peer_news)} sector/peer news articles")
                
                # 2c. Attach global news to this stock (duplicate with stock's symbol)
                if global_news_cache:
                    for global_article in global_news_cache:
                        # Create a copy with this stock's symbol
                        stock_global_article = global_article.copy()
                        stock_global_article['symbol'] = stock  # Attach to this stock
                        stock_global_article['related_to'] = 'GLOBAL'  # Mark original source
                        all_articles.append(stock_global_article)
                    print(f"    ✅ Attached {len(global_news_cache)} global news articles")
                
                import time
                time.sleep(0.5)  # Rate limiting between stocks
                
            except Exception as e:
                print(f"  ❌ [{stock}] Processing error: {e}")
        
        # 3. Send all articles to Kafka
        if all_articles:
            print(f"\n  📤 Sending {len(all_articles)} total articles to Kafka...")
            for article in all_articles:
                try:
                    from utils.kafka_utils import send_to_kafka
                    send_to_kafka(self.producer, self.kafka_topic, article)
                    import time
                    time.sleep(0.1)  # Small delay between items
                except Exception as e:
                    print(f"  ❌ Kafka send error: {e}")
            
            # Summary by news type
            company_count = sum(1 for a in all_articles if a.get('news_type') == 'company')
            sector_count = sum(1 for a in all_articles if a.get('news_type') == 'sector')
            global_count = sum(1 for a in all_articles if a.get('news_type') == 'global')
            print(f"  📊 Summary: {company_count} company | {sector_count} sector | {global_count} global")
            print(f"  📊 Global news duplicated across {len(self.stocks)} stocks")
        else:
            print(f"\n  ℹ️  No new articles to send")
        
        # Print overall stats
        self._print_fetch_summary()


def main():
    """For standalone testing"""
    producer = NewsProducer()
    producer.run()


if __name__ == '__main__':
    main()