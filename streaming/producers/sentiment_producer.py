"""
Enhanced Sentiment Producer with multi-source support
Sources: Reddit, Twitter/X, StockTwits, Web Scraping
Performs sentiment analysis on social media content about stocks
"""

import os
import json
import requests
import praw
import time
import tweepy
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
    """Producer for social media sentiment analysis with multi-source fallback"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,TSLA,NVDA').split(',')
        fetch_interval = int(os.getenv('SENTIMENT_DATA_INTERVAL', '300'))  # 5 minutes
        
        super().__init__(
            kafka_topic='sentiment-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # Reddit API credentials
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.reddit_username = os.getenv('REDDIT_USERNAME')
        self.reddit_password = os.getenv('REDDIT_PASSWORD')
        self.reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'pathway-sentiment-agent:v1.0')
        self.reddit = None
        
        # Twitter/X API credentials
        self.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.twitter_api_key = os.getenv('TWITTER_API_KEY')
        self.twitter_api_secret = os.getenv('TWITTER_API_SECRET')
        self.twitter_access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.twitter_access_secret = os.getenv('TWITTER_ACCESS_SECRET')
        self.twitter_client = None
        
        # Configuration
        self.subreddits = os.getenv('REDDIT_SUBREDDITS', 'wallstreetbets,stocks,investing').split(',')
        self.reddit_search_limit = int(os.getenv('REDDIT_SEARCH_LIMIT', '20'))
        self.comment_limit = int(os.getenv('REDDIT_COMMENT_LIMIT', '10'))
        self.twitter_max_results = int(os.getenv('TWITTER_MAX_RESULTS', '20'))
        
        # Ticker to company name mapping
        company_names = os.getenv('COMPANY_NAMES', '').split(',')
        self.ticker_to_company = {}
        if len(stocks) == len(company_names) and company_names[0]:
            self.ticker_to_company = dict(zip(stocks, company_names))
        else:
            self.ticker_to_company = {ticker: ticker for ticker in stocks}
            print("⚠️  Using tickers as company names")
        
        # Deduplication cache
        self.seen_posts = OrderedDict()
        self.seen_posts_max_size = 2000
        
        # Sentiment analyzers
        self.vader_analyzer = None
        
        # Headers for web scraping
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def setup_sources(self):
        """Setup all sentiment data sources"""
        
        # Priority 0: Reddit (rich discussions, good for sentiment)
        if all([self.reddit_client_id, self.reddit_client_secret]):
            try:
                self.reddit = praw.Reddit(
                    client_id=self.reddit_client_id,
                    client_secret=self.reddit_client_secret,
                    username=self.reddit_username,
                    password=self.reddit_password,
                    user_agent=self.reddit_user_agent
                )
                # Test connection
                _ = self.reddit.user.me()
                self.register_source("Reddit", self._fetch_from_reddit, priority=0)
            except Exception as e:
                print(f"  ⚠️  Could not initialize Reddit: {e}")
        
        # Priority 1: Twitter/X (real-time sentiment)
        if self.twitter_bearer_token:
            try:
                self.twitter_client = tweepy.Client(
                    bearer_token=self.twitter_bearer_token,
                    consumer_key=self.twitter_api_key,
                    consumer_secret=self.twitter_api_secret,
                    access_token=self.twitter_access_token,
                    access_token_secret=self.twitter_access_secret,
                    wait_on_rate_limit=True
                )
                self.register_source("Twitter", self._fetch_from_twitter, priority=1)
            except Exception as e:
                print(f"  ⚠️  Could not initialize Twitter: {e}")
        
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
        """Fetch sentiment data from Reddit"""
        company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
        all_posts_data = []
        
        print(f"  🔍 [{stock_symbol}] Searching Reddit for: {stock_symbol} OR {company_name}")
        
        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                search_query = f"{stock_symbol} OR {company_name}"
                
                posts = subreddit.search(
                    search_query,
                    limit=self.reddit_search_limit,
                    time_filter='day',
                    sort='new'
                )
                
                posts_found = 0
                posts_skipped_seen = 0
                posts_skipped_nomatch = 0
                
                for post in posts:
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
                    
                    # Check if ticker/company actually mentioned
                    matches = self._check_ticker_match(
                        post.title.upper() + " " + post.selftext.upper(),
                        stock_symbol,
                        company_name
                    )
                    
                    if not matches:
                        posts_skipped_nomatch += 1
                        continue
                    
                    # Get comments
                    comments = self._get_post_comments(post, limit=self.comment_limit)
                    
                    # Perform sentiment analysis
                    title_sentiment = self.analyze_sentiment_vader(post.title)
                    content_sentiment = self.analyze_sentiment_vader(post.selftext if post.selftext else "")
                    
                    # Analyze comments
                    comment_sentiments = [self.analyze_sentiment_vader(c) for c in comments]
                    avg_comment_sentiment = (
                        sum(comment_sentiments) / len(comment_sentiments)
                        if comment_sentiments else 0.0
                    )
                    
                    # Determine match type
                    title_text = post.title.upper()
                    content_text = post.selftext.upper() if post.selftext else ""
                    ticker_in_title = stock_symbol.upper() in title_text or company_name.upper() in title_text
                    ticker_in_content = stock_symbol.upper() in content_text or company_name.upper() in content_text
                    
                    if ticker_in_title and ticker_in_content:
                        match_type = 'title_and_content'
                    elif ticker_in_title:
                        match_type = 'title_only'
                    elif ticker_in_content:
                        match_type = 'content_only'
                    else:
                        match_type = 'unknown'
                    
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
                    print(f"    ✅ Added post: {post.title[:50]}...")
                
                print(f"  📊 r/{subreddit_name}: Found {posts_found}, Skipped (seen): {posts_skipped_seen}, Skipped (no match): {posts_skipped_nomatch}, Added: {len(all_posts_data)}")
            
            except Exception as e:
                print(f"  ⚠️  Error in r/{subreddit_name}: {e}")
                continue
        
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
    
    # ========== TWITTER SOURCE ==========
    
    def _fetch_from_twitter(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch sentiment data from Twitter/X"""
        company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
        
        # Build search query (cashtag and company name)
        query = f"(${stock_symbol} OR {company_name}) -is:retweet lang:en"
        
        try:
            # Search recent tweets
            tweets = self.twitter_client.search_recent_tweets(
                query=query,
                max_results=self.twitter_max_results,
                tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
                expansions=['author_id'],
                user_fields=['username']
            )
            
            if not tweets.data:
                return None
            
            # Build user lookup
            users = {}
            if tweets.includes and 'users' in tweets.includes:
                users = {user.id: user.username for user in tweets.includes['users']}
            
            tweets_data = []
            for tweet in tweets.data:
                tweet_id = f"twitter_{tweet.id}"
                
                # Skip if already seen
                if tweet_id in self.seen_posts:
                    continue
                
                # Mark as seen
                self.seen_posts[tweet_id] = datetime.now().timestamp()
                if len(self.seen_posts) > self.seen_posts_max_size:
                    self.seen_posts.popitem(last=False)
                
                # Analyze sentiment
                sentiment_score = self.analyze_sentiment_vader(tweet.text)
                
                tweet_data = {
                    'id': tweet_id,
                    'symbol': stock_symbol,
                    'company_name': company_name,
                    'source': 'Twitter',
                    'platform': 'X',
                    'content_type': 'tweet',
                    'title': tweet.text[:100],
                    'content': tweet.text,
                    'url': f"https://twitter.com/user/status/{tweet.id}",
                    'author': users.get(tweet.author_id, 'unknown'),
                    'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                    'timestamp': datetime.now().isoformat(),
                    'engagement': {
                        'likes': tweet.public_metrics['like_count'] if hasattr(tweet, 'public_metrics') else 0,
                        'retweets': tweet.public_metrics['retweet_count'] if hasattr(tweet, 'public_metrics') else 0,
                        'replies': tweet.public_metrics['reply_count'] if hasattr(tweet, 'public_metrics') else 0,
                    },
                    'sentiment': {
                        'overall': round(sentiment_score, 4),
                        'classification': self.classify_sentiment(sentiment_score)
                    },
                    'data_source': 'Twitter'
                }
                
                tweets_data.append(tweet_data)
            
            return tweets_data if tweets_data else None
            
        except Exception as e:
            raise Exception(f"Twitter API error: {e}")
    
    # ========== HELPER METHODS ==========
    
    def _check_ticker_match(self, text: str, ticker: str, company: str) -> bool:
        """Check if ticker or company name appears in text"""
        text_upper = text.upper()
        return ticker.upper() in text_upper or company.upper() in text_upper


def main():
    """For standalone testing"""
    producer = SentimentProducer()
    producer.run()


if __name__ == '__main__':
    main()