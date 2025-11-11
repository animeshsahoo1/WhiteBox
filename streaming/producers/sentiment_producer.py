"""
Enhanced Sentiment Producer with Reddit support
Sources: Reddit
Performs sentiment analysis on social media content about stocks
"""

import os
import json
import requests
import praw
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from collections import OrderedDict
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from bs4 import BeautifulSoup
from producers.base_producer import BaseProducer
from utils.kafka_utils import get_kafka_producer, send_to_kafka

load_dotenv()


class SentimentProducer(BaseProducer):
    """Producer for social media sentiment analysis using Reddit"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,TSLA,NVDA').split(',')
        fetch_interval = int(os.getenv('SENTIMENT_DATA_INTERVAL', '300'))  # 5 minutes
        
        super().__init__(
            kafka_topic='sentiment-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # Track API calls per account for rate limiting (MUST initialize before loading accounts)
        self.api_calls = {}
        self.api_window_start = {}
        self.max_calls_per_minute = 50  # Conservative limit per account
        
        # Reddit API credentials - Multiple accounts for rotation
        self.reddit_accounts = self._load_reddit_accounts()
        self.current_reddit_index = 0
        self.reddit = None
        
        # Configuration
        self.subreddits = os.getenv('REDDIT_SUBREDDITS', 'wallstreetbets,stocks,investing,StockMarket,options').split(',')
        self.reddit_search_limit = int(os.getenv('REDDIT_SEARCH_LIMIT', '30'))  # Increased from 20
        self.comment_limit = int(os.getenv('REDDIT_COMMENT_LIMIT', '10'))
        
        # Ticker to company name mapping (optional, for display only)
        self.ticker_to_company = {ticker: ticker for ticker in stocks}
        company_names_env = os.getenv('COMPANY_NAMES', '')
        if company_names_env:
            company_names = company_names_env.split(',')
            if len(stocks) == len(company_names):
                self.ticker_to_company = dict(zip(stocks, company_names))
        
        # Deduplication cache
        self.seen_posts = OrderedDict()
        self.seen_posts_max_size = 2000
        
        # Sentiment analyzers
        self.vader_analyzer = None
    
    def _load_reddit_accounts(self) -> List[Dict]:
        """Load multiple Reddit accounts from comma-separated environment variables"""
        
        # Get comma-separated lists from .env
        client_ids_str = os.getenv('REDDIT_CLIENT_IDS', '')
        client_secrets_str = os.getenv('REDDIT_CLIENT_SECRETS', '')
        
        # Split and clean whitespace
        client_ids = [cid.strip() for cid in client_ids_str.split(',') if cid.strip()]
        client_secrets = [secret.strip() for secret in client_secrets_str.split(',') if secret.strip()]
        
        if not client_ids or not client_secrets:
            print(f"  ⚠️  No Reddit accounts configured in REDDIT_CLIENT_IDS/REDDIT_CLIENT_SECRETS")
            return []
        
        if len(client_ids) != len(client_secrets):
            print(f"  ⚠️  Warning: Mismatch between client IDs ({len(client_ids)}) and secrets ({len(client_secrets)})")
            # Use minimum length to avoid index errors
            min_len = min(len(client_ids), len(client_secrets))
            client_ids = client_ids[:min_len]
            client_secrets = client_secrets[:min_len]
        
        accounts = []
        for i, (client_id, client_secret) in enumerate(zip(client_ids, client_secrets)):
            accounts.append({
                'client_id': client_id,
                'client_secret': client_secret,
                'user_agent': f'pathway-sentiment-agent-{i+1}:v1.0'
            })
            
            # Initialize tracking for this account
            self.api_calls[i] = 0
            self.api_window_start[i] = time.time()
        
        print(f"  🔑 Loaded {len(accounts)} Reddit account(s) for rotation")
        return accounts
    
    def _get_reddit_client(self) -> Optional[praw.Reddit]:
        """Get Reddit client with rate limit checking and automatic rotation"""
        
        if not self.reddit_accounts:
            print("  ⚠️  No Reddit accounts available")
            return None
        
        # Check if current account hit rate limit
        current_idx = self.current_reddit_index
        current_time = time.time()
        
        # Reset counter if window expired (60 seconds)
        if current_time - self.api_window_start[current_idx] >= 60:
            self.api_calls[current_idx] = 0
            self.api_window_start[current_idx] = current_time
        
        # If current account approaching limit, rotate to next
        if self.api_calls[current_idx] >= self.max_calls_per_minute:
            print(f"  ⚠️  Account {current_idx + 1} hit rate limit ({self.api_calls[current_idx]}/{self.max_calls_per_minute})")
            
            # Calculate next index
            next_idx = (current_idx + 1) % len(self.reddit_accounts)
            
            # If we've cycled through all accounts, need to wait
            all_limited = all(
                self.api_calls[i] >= self.max_calls_per_minute 
                for i in range(len(self.reddit_accounts))
            )
            
            if next_idx == current_idx or all_limited:
                sleep_time = 60 - (current_time - self.api_window_start[current_idx])
                if sleep_time > 0:
                    print(f"  ⏳ All {len(self.reddit_accounts)} account(s) rate limited. Sleeping {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                    # Reset all counters
                    for i in range(len(self.reddit_accounts)):
                        self.api_calls[i] = 0
                        self.api_window_start[i] = time.time()
            else:
                # Rotate to next account
                self.current_reddit_index = next_idx
                self.reddit = None  # Force recreation with new account
                print(f"  🔄 Rotating to Reddit account {self.current_reddit_index + 1}/{len(self.reddit_accounts)}")
        
        # Create/recreate Reddit client if needed
        if self.reddit is None:
            account = self.reddit_accounts[self.current_reddit_index]
            try:
                self.reddit = praw.Reddit(
                    client_id=account['client_id'],
                    client_secret=account['client_secret'],
                    user_agent=account['user_agent']
                )
                # Test connection (works without username/password)
                try:
                    self.reddit.user.me()
                except:
                    pass  # It's okay if this fails, client still works for reading
                print(f"  ✅ Connected to Reddit using account {self.current_reddit_index + 1}/{len(self.reddit_accounts)}")
            except Exception as e:
                print(f"  ❌ Failed to connect with account {self.current_reddit_index + 1}: {e}")
                # Try next account
                self.current_reddit_index = (self.current_reddit_index + 1) % len(self.reddit_accounts)
                self.reddit = None
                return None
        
        # Increment API call counter
        self.api_calls[self.current_reddit_index] += 1
        
        return self.reddit
    
    def setup_sources(self):
        """Setup Reddit as the sentiment data source"""
        
        # Reddit (rich discussions, good for sentiment)
        if self.reddit_accounts:
            try:
                # Try to initialize first Reddit client
                reddit = self._get_reddit_client()
                if reddit:
                    self.register_source("Reddit", self._fetch_from_reddit, priority=0)
                else:
                    print(f"  ⚠️  Could not initialize any Reddit accounts")
            except Exception as e:
                print(f"  ⚠️  Could not initialize Reddit: {e}")
        else:
            print(f"  ⚠️  No Reddit accounts configured. Skipping Reddit source.")
        
        # Initialize VADER sentiment analyzer
        self.vader_analyzer = SentimentIntensityAnalyzer()
    
    def analyze_sentiment_vader(self, text: str) -> float:
        """
        Analyze sentiment using VADER (best for social media)
        
        Returns:
            Compound score (-1 to 1)
        """
        if not text or not text.strip():
            return 0.0
        
        scores = self.vader_analyzer.polarity_scores(text)
        return scores['compound']
    
    def analyze_sentiment_textblob(self, text: str) -> float:
        """
        Analyze sentiment using TextBlob (alternative method)
        
        Returns:
            Polarity score (-1 to 1)
        """
        if not text or not text.strip():
            return 0.0
        
        try:
            blob = TextBlob(text)
            return blob.sentiment.polarity
        except:
            return 0.0
    
    def classify_sentiment(self, score: float) -> str:
        """
        Classify sentiment score into category
        
        Args:
            score: Sentiment score (-1 to 1)
            
        Returns:
            'bullish', 'bearish', or 'neutral'
        """
        if score >= 0.05:
            return 'bullish'
        elif score <= -0.05:
            return 'bearish'
        else:
            return 'neutral'

    def fetch_and_send(self):
        """Override to group posts by symbol before sending"""
        print(f"\n[{self.name}] [{datetime.now().strftime('%H:%M:%S')}] Starting fetch cycle...")
        
        self._print_source_status()
        
        # Collect all posts from all stocks
        all_posts = []
        
        for stock in self.stocks:
            try:
                data = self.fetch_data_with_fallback(stock)
                
                if data:
                    if isinstance(data, list):
                        all_posts.extend(data)
                    else:
                        all_posts.append(data)
                
                time.sleep(0.5)
            except Exception as e:
                print(f"  ❌ [{stock}] Processing error: {e}")
        
        # Group posts by symbol
        if all_posts:
            grouped_data = self._group_posts_by_symbol(all_posts)
            
            # Send grouped messages
            for symbol, grouped_message in grouped_data.items():
                send_to_kafka(self.producer, self.kafka_topic, grouped_message)
                print(f"  ✅ [{symbol}] Sent {grouped_message['posts_count']} posts to Kafka")
        
        self._print_fetch_summary()
    
    # ========== REDDIT SOURCE ==========

    def _group_posts_by_symbol(self, all_posts: List[Dict]) -> Dict[str, Dict]:
        """Group individual posts by symbol into the expected Kafka message format"""
        grouped = {}
        
        for post in all_posts:
            # Support both 'ticker_symbol' (consumer schema) and 'symbol' (old format)
            symbol = post.get('ticker_symbol') or post.get('symbol')
            if not symbol:
                print(f"  ⚠️ Skipping post without symbol/ticker_symbol")
                continue
            
            if symbol not in grouped:
                grouped[symbol] = {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'posts_count': 0,
                    'posts': []
                }
            
            # Add this post to the symbol's posts array
            grouped[symbol]['posts'].append(post)
            grouped[symbol]['posts_count'] += 1
        
        print(f"  📦 Grouped {len(all_posts)} posts into {len(grouped)} symbol(s)")
        return grouped
    
    def _fetch_from_reddit(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch sentiment data from Reddit with automatic account rotation"""
        company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
        all_posts_data = []
        
        print(f"  🔍 [{stock_symbol}] Searching Reddit for: {stock_symbol} OR {company_name}")
        
        # Search more subreddits (increased from 2 to 3)
        subreddits_to_search = self.subreddits
        
        for subreddit_name in subreddits_to_search:
            try:
                # Get Reddit client (handles rotation automatically)
                reddit = self._get_reddit_client()
                if not reddit:
                    print(f"  ❌ No Reddit client available, skipping r/{subreddit_name}")
                    continue
                
                subreddit = reddit.subreddit(subreddit_name)
                
                # INTELLIGENT SEARCH: Cast a wide net with multiple search strategies
                # We want ALL recent discussions, Reddit's search will handle relevance
                search_queries = [
                    f"${stock_symbol}",  # Cashtag (most common on Reddit)
                    stock_symbol,         # Raw ticker
                ]
                
                # Increased search limit
                search_limit = min(self.reddit_search_limit, 30)
                
                # Collect posts from all search variations
                posts_list = []
                posts_seen_ids = set()  # Avoid duplicates within same subreddit
                
                try:
                    for query in search_queries:
                        # Search recent week for sentiment analysis
                        results = list(subreddit.search(
                            query,
                            limit=search_limit,
                            time_filter='week',  # Recent discussions for sentiment
                            sort='relevance'
                        ))
                        
                        # Add only unique posts
                        for post in results:
                            if post.id not in posts_seen_ids:
                                posts_list.append(post)
                                posts_seen_ids.add(post.id)
                        
                        # Break early if we have enough posts
                        if len(posts_list) >= search_limit:
                            break
                    
                except Exception as search_error:
                    print(f"  ⚠️  Search error in r/{subreddit_name}: {search_error}")
                    continue
                
                posts_found = 0
                posts_skipped_seen = 0
                
                for post in posts_list:
                    # Each iteration counts as API call
                    self.api_calls[self.current_reddit_index] += 1
                    
                    posts_found += 1
                    post_id = f"reddit_{post.id}"
                    
                    # Skip if already seen
                    if post_id in self.seen_posts:
                        posts_skipped_seen += 1
                        continue
                    
                    # Mark as seen (LRU cache)
                    self.seen_posts[post_id] = datetime.now().timestamp()
                    if len(self.seen_posts) > self.seen_posts_max_size:
                        self.seen_posts.popitem(last=False)
                    
                    # NO FILTERING - Trust Reddit's search!
                    # If Reddit returned it for our cashtag search, it's relevant
                    
                    # Get comments (only if REDDIT_COMMENT_LIMIT > 0)
                    comments = []
                    if self.comment_limit > 0:
                        comments = self._get_post_comments(post, limit=self.comment_limit)
                    
                    # Perform sentiment analysis
                    title_sentiment = self.analyze_sentiment_vader(post.title)
                    content_sentiment = self.analyze_sentiment_vader(post.selftext if post.selftext else "")
                    
                    # Analyze comments if any
                    avg_comment_sentiment = 0.0
                    if comments:
                        comment_sentiments = [self.analyze_sentiment_vader(c) for c in comments]
                        avg_comment_sentiment = sum(comment_sentiments) / len(comment_sentiments)
                    
                    # Simple match type detection (for metadata only)
                    title_text = post.title.upper()
                    content_text = post.selftext.upper() if post.selftext else ""
                    cashtag = f"${stock_symbol.upper()}"
                    
                    if cashtag in title_text:
                        match_type = 'cashtag_in_title'
                    elif cashtag in content_text:
                        match_type = 'cashtag_in_content'
                    elif stock_symbol.upper() in title_text:
                        match_type = 'ticker_in_title'
                    else:
                        match_type = 'reddit_search_result'
                    
                    # Format data to match consumer schema EXACTLY
                    post_data = {
                        'post_id': post_id,
                        'ticker_symbol': stock_symbol,
                        'company_name': company_name,
                        'subreddit': subreddit_name,
                        'post_title': post.title,
                        'post_content': post.selftext[:500] if post.selftext else "",
                        'post_comments': " | ".join(comments[:3]) if comments else "",
                        'sentiment_post_title': round(title_sentiment, 4),
                        'sentiment_post_content': round(content_sentiment, 4),
                        'sentiment_comments': round(avg_comment_sentiment, 4),
                        'post_url': f"https://reddit.com{post.permalink}",
                        'num_comments': post.num_comments,
                        'score': post.score,
                        'created_utc': datetime.fromtimestamp(post.created_utc).isoformat(),
                        'match_type': match_type,
                        'timestamp': datetime.now().isoformat(),
                    }
                    
                    all_posts_data.append(post_data)
                
                print(f"  📊 r/{subreddit_name}: Found {posts_found}, Skipped (seen): {posts_skipped_seen}, Added: {len([p for p in all_posts_data if p['subreddit'] == subreddit_name])}")
                
                # Small delay between subreddits to be nice to API
                time.sleep(1)
            
            except Exception as e:
                print(f"  ⚠️  Error in r/{subreddit_name}: {e}")
                # Try rotating to next account on error
                self.reddit = None
                continue
        
        # Show current API usage
        if self.reddit_accounts:
            current_idx = self.current_reddit_index
            print(f"  📊 API Usage: Account {current_idx + 1}/{len(self.reddit_accounts)} used {self.api_calls[current_idx]}/{self.max_calls_per_minute} calls")
        
        print(f"  📦 [{stock_symbol}] Total posts collected: {len(all_posts_data)}")
        return all_posts_data if all_posts_data else None
    
    def _get_post_comments(self, post, limit=10) -> List[str]:
        """Fetch top-level comments from Reddit post"""
        try:
            post.comments.replace_more(limit=0)
            comments = post.comments.list()
            
            comment_texts = []
            for comment in comments[:limit]:
                if hasattr(comment, 'body') and comment.body:
                    comment_texts.append(comment.body)
            
            return comment_texts
        except:
            return []


def main():
    """For standalone testing"""
    producer = SentimentProducer()
    producer.run()


if __name__ == '__main__':
    main()


def main():
    """For standalone testing"""
    producer = SentimentProducer()
    producer.run()


if __name__ == '__main__':
    main()