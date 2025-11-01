"""
Enhanced Sentiment Producer with multi-source support
Sources: Reddit, Twitter/X, StockTwits, Web Scraping
Performs sentiment analysis on social media content about stocks
"""

import os
import json
import requests
import praw
import tweepy
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from collections import OrderedDict
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from bs4 import BeautifulSoup
from producers.base_producer import BaseProducer

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
        
        # Priority 2: StockTwits (stock-specific social platform)
        self.register_source("StockTwits", self._fetch_from_stocktwits, priority=2)
        
        # Priority 3: Twitter Web Scraper (fallback for Twitter)
        self.register_source("TwitterScraper", self._fetch_from_twitter_scraper, priority=3)
        
        # Priority 4: Reddit Web Scraper (fallback for Reddit)
        self.register_source("RedditScraper", self._fetch_from_reddit_scraper, priority=4)
        
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
    
    # ========== REDDIT SOURCE ==========
    
    def _fetch_from_reddit(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch sentiment data from Reddit"""
        company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
        all_posts_data = []
        
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
                
                for post in posts:
                    post_id = f"reddit_{post.id}"
                    
                    # Skip if already seen
                    if post_id in self.seen_posts:
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
                        continue
                    
                    # Get comments
                    comments = self._get_post_comments(post, limit=self.comment_limit)
                    
                    # Perform sentiment analysis
                    title_sentiment = self.analyze_sentiment_vader(post.title)
                    content_sentiment = self.analyze_sentiment_vader(post.selftext)
                    
                    # Analyze comments
                    comment_sentiments = [self.analyze_sentiment_vader(c) for c in comments]
                    avg_comment_sentiment = (
                        sum(comment_sentiments) / len(comment_sentiments)
                        if comment_sentiments else 0.0
                    )
                    
                    # Overall sentiment (weighted average)
                    overall_sentiment = (
                        title_sentiment * 0.4 + 
                        content_sentiment * 0.3 + 
                        avg_comment_sentiment * 0.3
                    )
                    
                    post_data = {
                        'id': post_id,
                        'symbol': stock_symbol,
                        'company_name': company_name,
                        'source': 'Reddit',
                        'platform': f'r/{subreddit_name}',
                        'content_type': 'post',
                        'title': post.title,
                        'content': post.selftext[:500],
                        'url': f"https://reddit.com{post.permalink}",
                        'author': str(post.author) if post.author else '[deleted]',
                        'created_at': datetime.fromtimestamp(post.created_utc).isoformat(),
                        'timestamp': datetime.now().isoformat(),
                        'engagement': {
                            'score': post.score,
                            'num_comments': post.num_comments,
                            'upvote_ratio': getattr(post, 'upvote_ratio', 0)
                        },
                        'sentiment': {
                            'title': round(title_sentiment, 4),
                            'content': round(content_sentiment, 4),
                            'comments': round(avg_comment_sentiment, 4),
                            'overall': round(overall_sentiment, 4),
                            'classification': self.classify_sentiment(overall_sentiment)
                        },
                        'data_source': 'Reddit'
                    }
                    
                    all_posts_data.append(post_data)
            
            except Exception as e:
                print(f"  ⚠️  Error in r/{subreddit_name}: {e}")
                continue
        
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
    
    # ========== STOCKTWITS SOURCE ==========
    
    def _fetch_from_stocktwits(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Fetch sentiment data from StockTwits (free API)"""
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{stock_symbol}.json"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'messages' not in data or not data['messages']:
                return None
            
            messages_data = []
            for message in data['messages'][:20]:
                msg_id = f"stocktwits_{message['id']}"
                
                # Skip if already seen
                if msg_id in self.seen_posts:
                    continue
                
                # Mark as seen
                self.seen_posts[msg_id] = datetime.now().timestamp()
                if len(self.seen_posts) > self.seen_posts_max_size:
                    self.seen_posts.popitem(last=False)
                
                # StockTwits provides sentiment labels
                st_sentiment = message.get('entities', {}).get('sentiment')
                
                # Also analyze with VADER
                text = message.get('body', '')
                vader_sentiment = self.analyze_sentiment_vader(text)
                
                # Map StockTwits sentiment to score
                st_score = 0.0
                if st_sentiment:
                    if st_sentiment.get('basic') == 'Bullish':
                        st_score = 0.5
                    elif st_sentiment.get('basic') == 'Bearish':
                        st_score = -0.5
                
                # Average both sentiments
                combined_score = (vader_sentiment + st_score) / 2 if st_score != 0 else vader_sentiment
                
                message_data = {
                    'id': msg_id,
                    'symbol': stock_symbol,
                    'company_name': self.ticker_to_company.get(stock_symbol, stock_symbol),
                    'source': 'StockTwits',
                    'platform': 'StockTwits',
                    'content_type': 'message',
                    'title': text[:100],
                    'content': text,
                    'url': f"https://stocktwits.com/{message['user']['username']}/message/{message['id']}",
                    'author': message['user']['username'],
                    'created_at': message.get('created_at'),
                    'timestamp': datetime.now().isoformat(),
                    'engagement': {
                        'likes': message.get('likes', {}).get('total', 0),
                    },
                    'sentiment': {
                        'vader': round(vader_sentiment, 4),
                        'stocktwits': st_sentiment.get('basic', 'None') if st_sentiment else 'None',
                        'overall': round(combined_score, 4),
                        'classification': self.classify_sentiment(combined_score)
                    },
                    'data_source': 'StockTwits'
                }
                
                messages_data.append(message_data)
            
            return messages_data if messages_data else None
            
        except Exception as e:
            raise Exception(f"StockTwits error: {e}")
    
    # ========== WEB SCRAPING FALLBACKS ==========
    
    def _fetch_from_twitter_scraper(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Web scrape Twitter/X (fallback when API unavailable)"""
        # Note: Twitter heavily restricts scraping now, this is a placeholder
        # You might want to use services like Nitter or similar proxies
        
        url = f"https://nitter.net/search?f=tweets&q=%24{stock_symbol}&since=&until=&near="
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tweets_data = []
            tweet_items = soup.find_all('div', class_='timeline-item')[:10]
            
            for item in tweet_items:
                try:
                    content_div = item.find('div', class_='tweet-content')
                    if not content_div:
                        continue
                    
                    text = content_div.get_text(strip=True)
                    
                    # Generate pseudo-ID
                    tweet_id = f"twitter_scrape_{hash(text)}"
                    
                    if tweet_id in self.seen_posts:
                        continue
                    
                    self.seen_posts[tweet_id] = datetime.now().timestamp()
                    if len(self.seen_posts) > self.seen_posts_max_size:
                        self.seen_posts.popitem(last=False)
                    
                    sentiment_score = self.analyze_sentiment_vader(text)
                    
                    tweets_data.append({
                        'id': tweet_id,
                        'symbol': stock_symbol,
                        'company_name': self.ticker_to_company.get(stock_symbol, stock_symbol),
                        'source': 'TwitterScraper',
                        'platform': 'X',
                        'content_type': 'tweet',
                        'title': text[:100],
                        'content': text,
                        'url': '',
                        'author': 'scraped',
                        'created_at': datetime.now().isoformat(),
                        'timestamp': datetime.now().isoformat(),
                        'engagement': {},
                        'sentiment': {
                            'overall': round(sentiment_score, 4),
                            'classification': self.classify_sentiment(sentiment_score)
                        },
                        'data_source': 'TwitterScraper'
                    })
                except:
                    continue
            
            return tweets_data if tweets_data else None
            
        except Exception as e:
            raise Exception(f"Twitter scraping error: {e}")
    
    def _fetch_from_reddit_scraper(self, stock_symbol: str) -> Optional[List[Dict]]:
        """Web scrape Reddit (fallback when API unavailable)"""
        company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
        
        # Use old.reddit.com for easier scraping
        url = f"https://old.reddit.com/r/wallstreetbets/search?q={stock_symbol}&restrict_sr=on&sort=new&t=day"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            posts_data = []
            post_items = soup.find_all('div', class_='thing')[:10]
            
            for item in post_items:
                try:
                    title_elem = item.find('a', class_='title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    post_url = title_elem.get('href', '')
                    
                    # Make absolute URL
                    if post_url.startswith('/r/'):
                        post_url = f"https://reddit.com{post_url}"
                    
                    post_id = f"reddit_scrape_{hash(title + post_url)}"
                    
                    if post_id in self.seen_posts:
                        continue
                    
                    self.seen_posts[post_id] = datetime.now().timestamp()
                    if len(self.seen_posts) > self.seen_posts_max_size:
                        self.seen_posts.popitem(last=False)
                    
                    sentiment_score = self.analyze_sentiment_vader(title)
                    
                    # Get score
                    score_elem = item.find('div', class_='score')
                    score = score_elem.get_text(strip=True) if score_elem else '0'
                    
                    posts_data.append({
                        'id': post_id,
                        'symbol': stock_symbol,
                        'company_name': company_name,
                        'source': 'RedditScraper',
                        'platform': 'r/wallstreetbets',
                        'content_type': 'post',
                        'title': title,
                        'content': '',
                        'url': post_url,
                        'author': 'scraped',
                        'created_at': datetime.now().isoformat(),
                        'timestamp': datetime.now().isoformat(),
                        'engagement': {
                            'score': score
                        },
                        'sentiment': {
                            'overall': round(sentiment_score, 4),
                            'classification': self.classify_sentiment(sentiment_score)
                        },
                        'data_source': 'RedditScraper'
                    })
                except:
                    continue
            
            return posts_data if posts_data else None
            
        except Exception as e:
            raise Exception(f"Reddit scraping error: {e}")
    
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