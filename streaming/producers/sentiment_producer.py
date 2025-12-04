"""
Enhanced Sentiment Producer with Reddit and Twitter Webhook support
Sources: Reddit, Twitter (via webhook)
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
    """Producer for social media sentiment analysis using Reddit and Twitter"""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,TSLA,NVDA').split(',')
        fetch_interval = int(os.getenv('SENTIMENT_DATA_INTERVAL', '600'))  # Changed to 600 seconds (10 minutes)
        
        super().__init__(
            kafka_topic='sentiment-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # Twitter Webhook Configuration
        self.twitter_api_key = os.getenv('TWITTER_API_KEY', '')
        self.webhook_url = os.getenv('TWITTER_WEBHOOK_URL', 'https://test-something-wp.free.beeceptor.com')
        self.twitter_check_interval = int(os.getenv('TWITTER_CHECK_INTERVAL', '600'))  # Changed to 600 seconds (10 minutes)
        self.twitter_rules = {}  # Store rule IDs for each stock
        self.twitter_cleanup_done = False  # Flag to prevent duplicate cleanup
        
        # Logging configuration
        self.enable_logging = os.getenv('ENABLE_SENTIMENT_LOGGING', 'true').lower() == 'true'
        self.log_dir = os.path.join(os.path.dirname(__file__), '..', 'sentiment_logs')
        if self.enable_logging:
            os.makedirs(self.log_dir, exist_ok=True)
            print(f"  💾 Logging enabled: {self.enable_logging}")
            print(f"  📁 Log directory: {os.path.abspath(self.log_dir)}")
            print(f"  📂 Directory exists: {os.path.exists(self.log_dir)}")
        
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
        client_ids_str = os.getenv('REDDIT_CLIENT_ID', '')
        client_secrets_str = os.getenv('REDDIT_CLIENT_SECRET', '')
        
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
                except Exception:
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
        """Setup Reddit and Twitter as sentiment data sources"""
        
        # Twitter (via webhook - setup rules first)
        print(f"\n🔍 DEBUG: TWITTER_API_KEY = '{self.twitter_api_key[:20] if self.twitter_api_key else 'EMPTY'}...'")
        print(f"🔍 DEBUG: TWITTER_API_KEY length = {len(self.twitter_api_key) if self.twitter_api_key else 0}")
        print(f"🔍 DEBUG: TWITTER_API_KEY is truthy? {bool(self.twitter_api_key)}\n")
        
        if self.twitter_api_key:
            print(f"\n{'='*60}")
            print(f"🐦 Setting up Twitter webhook for {len(self.stocks)} stocks")
            print(f"{'='*60}\n")
            self._setup_twitter_webhooks()
            self.register_source("Twitter", self._fetch_from_twitter, priority=0)
        else:
            print(f"  ⚠️  No Twitter API key configured. Skipping Twitter source.")
        
        # Reddit (rich discussions, good for sentiment)
        if self.reddit_accounts:
            try:
                # Try to initialize first Reddit client
                reddit = self._get_reddit_client()
                if reddit:
                    self.register_source("Reddit", self._fetch_from_reddit, priority=1)
                else:
                    print(f"  ⚠️  Could not initialize any Reddit accounts")
            except Exception as e:
                print(f"  ⚠️  Could not initialize Reddit: {e}")
        else:
            print(f"  ⚠️  No Reddit accounts configured. Skipping Reddit source.")
        
        # Initialize VADER sentiment analyzer
        self.vader_analyzer = SentimentIntensityAnalyzer()
    
    # ========== TWITTER WEBHOOK METHODS ==========
    
    def _setup_twitter_webhooks(self):
        """Setup Twitter filter rules and webhooks for all stocks"""
        # First, check if rules already exist
        existing_rules = self._get_existing_rules()
        
        for stock in self.stocks:
            company_name = self.ticker_to_company.get(stock, stock)
            rule_tag = f"{stock}_sentiment"
            
            # Check if rule already exists
            existing_rule_id = None
            for rule in existing_rules:
                if rule.get('tag') == rule_tag:
                    existing_rule_id = rule.get('rule_id')
                    is_active = rule.get('is_effect', 0)
                    print(f"  ✅ [{stock}] Rule already exists: {existing_rule_id} ({'ACTIVE' if is_active == 1 else 'INACTIVE'})")
                    break
            
            if existing_rule_id:
                # Use existing rule
                self.twitter_rules[stock] = existing_rule_id
                
                # If inactive, try to activate
                is_active = next((r.get('is_effect', 0) for r in existing_rules if r.get('rule_id') == existing_rule_id), 0)
                if is_active == 0 or str(is_active) == "0":
                    print(f"  🔄 [{stock}] Attempting to activate existing rule...")
                    rule_value = next((r.get('value') for r in existing_rules if r.get('rule_id') == existing_rule_id), None)
                    self._activate_twitter_rule(existing_rule_id, stock, rule_value)
            else:
                # Create new rule
                rule_value = f"(${stock} OR {stock}) lang:en"
                print(f"  🔧 [{stock}] Creating new Twitter rule: {rule_value}")
                
                rule_id = self._add_twitter_rule(stock, rule_value)
                
                if rule_id:
                    self.twitter_rules[stock] = rule_id
                    # Try to activate rule
                    self._activate_twitter_rule(rule_id, stock, rule_value)
            
            time.sleep(0.5)
    
    def _get_existing_rules(self) -> List[Dict]:
        """Get all existing Twitter filter rules"""
        url = "https://api.twitterapi.io/oapi/tweet_filter/get_rules"
        
        headers = {
            "X-API-Key": self.twitter_api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rules = data.get('rules', [])
                print(f"  📋 Found {len(rules)} existing Twitter rules")
                return rules
            else:
                print(f"  ⚠️  Failed to get existing rules: {response.status_code}")
                return []
        except Exception as e:
            print(f"  ⚠️  Error getting existing rules: {e}")
            return []
    
    def _add_twitter_rule(self, stock: str, rule_value: str) -> Optional[str]:
        """Add a Twitter filter rule"""
        url = "https://api.twitterapi.io/oapi/tweet_filter/add_rule"
        
        payload = {
            "tag": f"{stock}_sentiment",
            "value": rule_value,
            "interval_seconds": self.twitter_check_interval
        }
        
        headers = {
            "X-API-Key": self.twitter_api_key,
            "Content-Type": "application/json"
        }
        
        print(f"  📡 [{stock}] Sending request to: {url}")
        print(f"  📦 [{stock}] Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            print(f"  📡 [{stock}] Response status: {response.status_code}")
            print(f"  📄 [{stock}] Response body: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                # API returns {"rule_id": "..."} directly, not nested in "data"
                rule_id = result.get('rule_id') or result.get('data', {}).get('id')
                print(f"  ✅ [{stock}] Rule added - ID: {rule_id}")
                return rule_id
            else:
                print(f"  ❌ [{stock}] Failed to add rule: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ❌ [{stock}] Error adding rule: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _activate_twitter_rule(self, rule_id: str, stock: str, rule_value: str = None) -> bool:
        """Activate a Twitter filter rule"""
        url = "https://api.twitterapi.io/oapi/tweet_filter/update_rule"
        
        # Get rule details if not provided
        if not rule_value:
            company_name = self.ticker_to_company.get(stock, stock)
            rule_value = f"(${stock} OR {stock} OR {company_name}) lang:en"
        
        # API requires all fields to update a rule
        payload = {
            "rule_id": rule_id,
            "tag": f"{stock}_sentiment",
            "value": rule_value,
            "interval_seconds": self.twitter_check_interval,
            "is_effect": "1"  # String "1" to activate, "0" to deactivate
        }
        
        headers = {
            "X-API-Key": self.twitter_api_key,
            "Content-Type": "application/json"
        }
        
        print(f"  🔔 [{stock}] Activating rule: {rule_id}")
        print(f"  📦 [{stock}] Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"  📡 [{stock}] Response status: {response.status_code}")
            print(f"  📄 [{stock}] Response body: {response.text}")
            
            # Sometimes 200 or 201 both indicate success
            if response.status_code in [200, 201]:
                print(f"  ✅ [{stock}] Rule activated successfully")
                print(f"  💡 [{stock}] Webhook URL should be set in TwitterAPI.io dashboard")
                return True
            else:
                print(f"  ❌ [{stock}] Failed to activate: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ❌ [{stock}] Error activating: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _activate_rule_alternative(self, rule_id: str, stock: str) -> bool:
        """Alternative activation: activate rule without webhook first, then add webhook"""
        url = "https://api.twitterapi.io/oapi/tweet_filter/update_rule"
        
        # Step 1: Just activate the rule
        payload = {
            "rule_id": rule_id,
            "is_effect": 1
        }
        
        headers = {
            "X-API-Key": self.twitter_api_key,
            "Content-Type": "application/json"
        }
        
        print(f"  📡 [{stock}] Activating rule WITHOUT webhook first...")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            print(f"  📡 [{stock}] Activation response: {response.status_code} - {response.text}")
            
            if response.status_code not in [200, 201]:
                print(f"  ❌ [{stock}] Alternative activation also failed")
                return False
            
            # Step 2: Now try to add webhook separately if there's such endpoint
            print(f"  ✅ [{stock}] Rule activated (without webhook)")
            print(f"  ⚠️  [{stock}] Webhook integration may require manual setup in dashboard")
            return True
            
        except Exception as e:
            print(f"  ❌ [{stock}] Alternative activation error: {e}")
            return False
    
    def _fetch_from_twitter(self, stock_symbol: str) -> Optional[List[Dict]]:
        """
        Fetch tweets from local webhook receiver
        Tweets arrive in real-time via webhook and are buffered locally
        """
        try:
            company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
            
            # Fetch from local webhook receiver instead of TwitterAPI.io
            webhook_receiver_url = os.getenv('WEBHOOK_RECEIVER_URL', 'http://twitter-webhook:5001')
            url = f"{webhook_receiver_url}/tweets/{stock_symbol}"
            
            print(f"\n  {'='*50}")
            print(f"  🐦 [{stock_symbol}] Fetching tweets from webhook buffer")
            print(f"  {'='*50}")
            print(f"  📍 URL: {url}")
            
            response = requests.get(url, timeout=5)
            
            print(f"  📡 Response Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"  ⚠️  [{stock_symbol}] Webhook receiver returned {response.status_code}")
                print(f"  📄 Response body: {response.text[:500]}")
                return None
            
            data = response.json()
            print(f"  📋 Response data keys: {list(data.keys())}")
            
            # Get tweets from webhook receiver response
            tweets = data.get('tweets', [])
            total_tweets = len(tweets)
            
            print(f"  📊 Total tweets received: {total_tweets}")
            
            if not tweets:
                print(f"  ℹ️  [{stock_symbol}] No new tweets in buffer")
                return None
            
            # Process tweets
            processed_tweets = []
            skipped_seen = 0
            
            for i, tweet in enumerate(tweets):
                tweet_id = tweet.get('id')
                post_key = f"twitter_{tweet_id}"  # Consistent key for deduplication
                
                print(f"\n  📧 Tweet {i+1}/{total_tweets}:")
                print(f"     ID: {tweet_id}")
                print(f"     Text: {tweet.get('text', '')[:100]}...")
                
                # Skip if already seen (use same key format for check and store)
                if post_key in self.seen_posts:
                    print(f"     ⏭️  Skipped (already seen)")
                    skipped_seen += 1
                    continue
                
                # Mark as seen
                self.seen_posts[post_key] = datetime.now().timestamp()
                if len(self.seen_posts) > self.seen_posts_max_size:
                    self.seen_posts.popitem(last=False)
                
                # Extract tweet data
                text = tweet.get('text', '')
                author = tweet.get('author', {})
                username = author.get('username', 'unknown') if isinstance(author, dict) else 'unknown'
                created_at = tweet.get('created_at', datetime.now().isoformat())
                
                print(f"     Author: @{username}")
                print(f"     Text: {text[:100]}...")
                print(f"     Created: {created_at}")
                
                # Perform sentiment analysis
                sentiment_score = self.analyze_sentiment_vader(text)
                print(f"     Sentiment: {sentiment_score:.4f}")
                
                # Build URL
                tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
                print(f"     URL: {tweet_url}")
                
                # Format data to match consumer schema
                tweet_data = {
                    'post_id': f"twitter_{tweet_id}",
                    'ticker_symbol': stock_symbol,
                    'company_name': company_name,
                    'subreddit': 'twitter',  # Using same field for source
                    'post_title': text[:100] + '...' if len(text) > 100 else text,
                    'post_content': text,
                    'post_comments': '',
                    'sentiment_post_title': round(sentiment_score, 4),
                    'sentiment_post_content': round(sentiment_score, 4),
                    'sentiment_comments': 0.0,
                    'post_url': tweet_url,
                    'num_comments': tweet.get('reply_count', 0),
                    'score': tweet.get('like_count', 0),
                    'created_utc': created_at,
                    'match_type': 'twitter_webhook',
                    'timestamp': datetime.now().isoformat(),
                }
                
                processed_tweets.append(tweet_data)
                print(f"     ✅ Processed and added")
            
            print(f"\n  {'='*50}")
            print(f"  📊 [{stock_symbol}] Twitter Summary:")
            print(f"     Total received: {total_tweets}")
            print(f"     Skipped (seen): {skipped_seen}")
            print(f"     New tweets: {len(processed_tweets)}")
            print(f"  {'='*50}\n")
            
            if processed_tweets:
                print(f"  ✅ [{stock_symbol}] Fetched {len(processed_tweets)} new tweets")
            
            return processed_tweets if processed_tweets else None
            
        except requests.exceptions.Timeout:
            print(f"  ⚠️  [{stock_symbol}] Twitter API timeout")
            return None
        except Exception as e:
            print(f"  ❌ [{stock_symbol}] Error fetching tweets: {e}")
            import traceback
            print(f"  📋 Traceback:")
            traceback.print_exc()
            return None
    
    def _deactivate_twitter_rules(self):
        """Deactivate all Twitter rules to avoid charges when shutting down"""
        # Check if cleanup already done (prevents duplicate cleanup on Ctrl+C spam)
        if self.twitter_cleanup_done:
            print(f"  ℹ️  Twitter cleanup already completed, skipping...")
            return
        
        if not self.twitter_rules or not self.twitter_api_key:
            self.twitter_cleanup_done = True
            return
        
        print(f"\n{'='*60}")
        print(f"🐦 Deactivating {len(self.twitter_rules)} Twitter rules...")
        print(f"{'='*60}\n")
        
        url = "https://api.twitterapi.io/oapi/tweet_filter/update_rule"
        
        headers = {
            "X-API-Key": self.twitter_api_key,
            "Content-Type": "application/json"
        }
        
        # Get existing rules to get their values
        existing_rules = self._get_existing_rules()
        
        for stock, rule_id in self.twitter_rules.items():
            try:
                # Find the rule value
                rule_value = None
                for rule in existing_rules:
                    if rule.get('rule_id') == rule_id:
                        rule_value = rule.get('value', '')
                        break
                
                if not rule_value:
                    company_name = self.ticker_to_company.get(stock, stock)
                    rule_value = f"(${stock} OR {stock} OR {company_name}) lang:en"
                
                # Deactivate rule with all required fields
                payload = {
                    "rule_id": rule_id,
                    "tag": f"{stock}_sentiment",
                    "value": rule_value,
                    "interval_seconds": self.twitter_check_interval,
                    "is_effect": "0"  # String "0" to deactivate
                }
                
                print(f"  🔄 [{stock}] Deactivating rule {rule_id}...")
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code in [200, 201]:
                    print(f"  ✅ [{stock}] Rule deactivated successfully")
                else:
                    print(f"  ⚠️  [{stock}] Failed to deactivate: {response.status_code}")
                    print(f"      Response: {response.text[:200]}")
                
                time.sleep(0.3)
                
            except Exception as e:
                print(f"  ❌ [{stock}] Error deactivating rule: {e}")
        
        self.twitter_cleanup_done = True
        print(f"\n✅ Twitter rules deactivation complete\n")
    
    def cleanup(self):
        """Override cleanup to deactivate Twitter rules"""
        # Deactivate Twitter rules first
        self._deactivate_twitter_rules()
        
        # Call parent cleanup
        super().cleanup()
    
    # ========== SENTIMENT ANALYSIS METHODS ==========
    
    def analyze_sentiment_vader(self, text: str) -> float:
        """
        Analyze sentiment using VADER (best for social media)
        
        Returns:
            Compound score (-1 to 1)
        """
        if not text or not text.strip():
            return 0.0
        
        # Ensure vader_analyzer is initialized
        if self.vader_analyzer is None:
            self.vader_analyzer = SentimentIntensityAnalyzer()
        
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
        except Exception:
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
        twitter_posts = []
        reddit_posts = []
        
        for stock in self.stocks:
            try:
                data = self.fetch_data_with_fallback(stock)
                
                if data:
                    if isinstance(data, list):
                        all_posts.extend(data)
                        # Separate by source for logging
                        for post in data:
                            if post.get('subreddit') == 'twitter' or post.get('match_type') == 'twitter_webhook':
                                twitter_posts.append(post)
                            else:
                                reddit_posts.append(post)
                    else:
                        all_posts.append(data)
                        if data.get('subreddit') == 'twitter' or data.get('match_type') == 'twitter_webhook':
                            twitter_posts.append(data)
                        else:
                            reddit_posts.append(data)
                
                # Sleep 5 seconds between stocks to respect Twitter API free tier rate limit (1 req/5sec)
                time.sleep(5)
            except Exception as e:
                print(f"  ❌ [{stock}] Processing error: {e}")
        
        # Log the data
        if all_posts and self.enable_logging:
            self._log_fetched_data(all_posts, twitter_posts, reddit_posts)
        
        # Group posts by symbol
        if all_posts:
            grouped_data = self._group_posts_by_symbol(all_posts)
            
            # Send grouped messages
            for symbol, grouped_message in grouped_data.items():
                send_to_kafka(self.producer, self.kafka_topic, grouped_message)
                print(f"  ✅ [{symbol}] Sent {grouped_message['posts_count']} posts to Kafka")
        
        # Print summary with source breakdown
        if twitter_posts or reddit_posts:
            print(f"\n  📊 Source Breakdown:")
            if twitter_posts:
                print(f"     🐦 Twitter: {len(twitter_posts)} tweets")
            if reddit_posts:
                print(f"     🔴 Reddit: {len(reddit_posts)} posts")
        
        self._print_fetch_summary()
    
    def _log_fetched_data(self, all_posts: List[Dict], twitter_posts: List[Dict], reddit_posts: List[Dict]):
        """Log fetched data to files for inspection"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        print(f"\n  {'='*60}")
        print(f"  💾 Starting to log data...")
        print(f"  📁 Log directory: {self.log_dir}")
        print(f"  📂 Directory exists: {os.path.exists(self.log_dir)}")
        print(f"  🔢 Total posts to log: {len(all_posts)}")
        print(f"  {'='*60}")
        
        try:
            # Log all posts
            all_posts_file = os.path.join(self.log_dir, f'all_posts_{timestamp}.json')
            print(f"  📝 Writing all posts to: {all_posts_file}")
            with open(all_posts_file, 'w', encoding='utf-8') as f:
                json.dump(all_posts, f, indent=2, ensure_ascii=False)
            print(f"  ✅ All posts file written successfully")
            
            # Log Twitter posts separately
            if twitter_posts:
                twitter_file = os.path.join(self.log_dir, f'twitter_{timestamp}.json')
                print(f"  📝 Writing {len(twitter_posts)} Twitter posts to: {twitter_file}")
                with open(twitter_file, 'w', encoding='utf-8') as f:
                    json.dump(twitter_posts, f, indent=2, ensure_ascii=False)
                print(f"  ✅ Twitter file written successfully")
            
            # Log Reddit posts separately
            if reddit_posts:
                reddit_file = os.path.join(self.log_dir, f'reddit_{timestamp}.json')
                print(f"  📝 Writing {len(reddit_posts)} Reddit posts to: {reddit_file}")
                with open(reddit_file, 'w', encoding='utf-8') as f:
                    json.dump(reddit_posts, f, indent=2, ensure_ascii=False)
                print(f"  ✅ Reddit file written successfully")
            
            # Create a summary file
            summary_file = os.path.join(self.log_dir, f'summary_{timestamp}.txt')
            print(f"  📝 Writing summary to: {summary_file}")
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"Sentiment Data Fetch Summary\n")
                f.write(f"{'='*60}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Total Posts: {len(all_posts)}\n")
                f.write(f"Twitter Posts: {len(twitter_posts)}\n")
                f.write(f"Reddit Posts: {len(reddit_posts)}\n")
                f.write(f"\nBreakdown by Stock:\n")
                
                stock_counts = {}
                for post in all_posts:
                    symbol = post.get('ticker_symbol', 'UNKNOWN')
                    source = 'Twitter' if (post.get('subreddit') == 'twitter' or post.get('match_type') == 'twitter_webhook') else 'Reddit'
                    key = f"{symbol} ({source})"
                    stock_counts[key] = stock_counts.get(key, 0) + 1
                
                for stock, count in sorted(stock_counts.items()):
                    f.write(f"  {stock}: {count}\n")
            print(f"  ✅ Summary file written successfully")
            
            print(f"\n  ✅ Successfully logged {len(all_posts)} posts to {self.log_dir}/")
            print(f"  📋 Files created:")
            print(f"     - all_posts_{timestamp}.json")
            if twitter_posts:
                print(f"     - twitter_{timestamp}.json")
            if reddit_posts:
                print(f"     - reddit_{timestamp}.json")
            print(f"     - summary_{timestamp}.txt")
            print(f"  {'='*60}\n")
            
        except Exception as e:
            print(f"  ⚠️  Error logging data: {e}")
    
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
        except Exception:
            return []


def main():
    """For standalone testing"""
    producer = SentimentProducer()
    producer.run()


if __name__ == '__main__':
    main()