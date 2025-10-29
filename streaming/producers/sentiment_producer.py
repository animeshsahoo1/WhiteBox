"""
Sentiment Producer for Reddit Posts
Fetches Reddit posts about stock tickers and performs sentiment analysis using VADER.
"""

import os
import praw
from datetime import datetime
from typing import Set, List, Dict
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from producers.base_producer import BaseProducer

load_dotenv()


class SentimentProducer(BaseProducer):
    """Producer for Reddit sentiment analysis on stock tickers"""
    
    def __init__(self):
        # Load configuration from environment
        stocks = os.getenv('STOCKS', 'AAPL,TSLA,NVDA').split(',')
        fetch_interval = int(os.getenv('SENTIMENT_DATA_INTERVAL', '30'))  # 30 seconds
        
        super().__init__(
            kafka_topic='reddit-sentiment',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # Reddit API credentials
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.reddit_username = os.getenv('REDDIT_USERNAME')
        self.reddit_password = os.getenv('REDDIT_PASSWORD')
        self.reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'pathway-news-agent:v1.0')
        
        # Reddit configuration
        self.subreddits = os.getenv('REDDIT_SUBREDDITS', 'wallstreetbets,stocks').split(',')
        self.reddit_search_limit = int(os.getenv('REDDIT_SEARCH_LIMIT', '20'))  # Default to 20
        
        # Ticker to company name mapping
        self.ticker_to_company = {
            'AAPL': 'Apple',
            'TSLA': 'Tesla',
            'NVDA': 'Nvidia',
            'GME': 'GameStop',
            'AMC': 'AMC Entertainment',
            'MSFT': 'Microsoft',
            'GOOGL': 'Google',
            'AMZN': 'Amazon',
            'META': 'Meta',
            'NFLX': 'Netflix',
            'AMD': 'AMD',
            'INTC': 'Intel',
            'PLTR': 'Palantir',
            'BABA': 'Alibaba',
            'BB': 'BlackBerry',
            'NIO': 'Nio',
            'COIN': 'Coinbase',
            'RIVN': 'Rivian',
            'LCID': 'Lucid',
            'SOFI': 'SoFi'
        }
        
        # Track seen posts to avoid duplicates, with LRU eviction
        from collections import OrderedDict
        self.seen_posts = OrderedDict()
        self.seen_posts_max_size = 1000  # Adjust size limit as needed
        # VADER sentiment analyzer
        self.analyzer = None
        self.reddit = None

        # Comment limit configuration
        self.comment_limit = int(os.getenv('REDDIT_COMMENT_LIMIT', '10'))
        self.reddit = None
    
    def setup(self):
        """Setup Reddit client and VADER analyzer"""
        # Validate Reddit credentials
        if not all([self.reddit_client_id, self.reddit_client_secret, 
                   self.reddit_username, self.reddit_password]):
            print("ERROR: Reddit API credentials not found in .env")
            print("Required: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD")
            return False
        
        # Initialize Reddit client
        try:
            self.reddit = praw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                username=self.reddit_username,
                password=self.reddit_password,
                user_agent=self.reddit_user_agent
            )
            print("✓ Connected to Reddit API")
        except Exception as e:
            print(f"ERROR: Failed to connect to Reddit API: {e}")
            return False
        
        # Initialize VADER sentiment analyzer
        self.analyzer = SentimentIntensityAnalyzer()
        print("✓ VADER sentiment analyzer initialized")
        
        return True
    
    def analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text using VADER.
        
        Args:
            text: Text to analyze
            
        Returns:
            Compound score (-1 to 1)
        """
        if not text or text.strip() == "":
            return 0.0
        
        scores = self.analyzer.polarity_scores(text)
        return scores['compound']
    
    def get_post_comments(self, post, limit=10) -> List[str]:
        """Fetch top-level comments from a Reddit post"""
        try:
            post.comments.replace_more(limit=0)
            comments = post.comments.list()
            
            comment_texts = []
            for comment in comments[:limit]:
                if hasattr(comment, 'body'):
                    comment_texts.append(comment.body)
            
            return comment_texts
        except Exception as e:
            print(f"  ⚠ Error fetching comments: {str(e)}")
            return []
    
    def check_ticker_match(self, post, ticker: str, company_name: str) -> Dict[str, bool]:
        """Check if ticker or company name is mentioned in post"""
        title_upper = post.title.upper()
        selftext_upper = post.selftext.upper()
        ticker_upper = ticker.upper()
        company_upper = company_name.upper()
        
        return {
            'ticker_in_title': ticker_upper in title_upper,
            'ticker_in_body': ticker_upper in selftext_upper,
            'company_in_title': company_upper in title_upper,
            'company_in_body': company_upper in selftext_upper
        }
    
    def fetch_data(self, stock_symbol):
        """
        Fetch Reddit posts and perform sentiment analysis for a stock ticker.
        
        Args:
            stock_symbol: Stock ticker symbol
            
        Returns:
            dict: Post data with sentiment scores, or None if no new posts
        """
        # If ticker not in mapping, use ticker symbol as company name
        company_name = self.ticker_to_company.get(stock_symbol, stock_symbol)
        
        try:
            # Search across all configured subreddits
            all_posts_data = []
            
            for subreddit_name in self.subreddits:
                subreddit = self.reddit.subreddit(subreddit_name)
                # Search for recent posts mentioning ticker or company name
                search_query = f"{stock_symbol} OR {company_name}"
                posts = subreddit.search(
                    search_query,
                    limit=self.reddit_search_limit,
                    time_filter='day',
                    sort='new'
                )
                
                for post in posts:
                    # Skip if already seen
                    if post.id in self.seen_posts:
                        continue
                    if post.id in self.seen_posts:
                        continue

                    # Mark as seen with LRU eviction
                    self.seen_posts[post.id] = datetime.now().timestamp()
                    if len(self.seen_posts) > self.seen_posts_max_size:
                        self.seen_posts.popitem(last=False)

                    # Check if ticker or company name is actually mentioned
                    matches = self.check_ticker_match(post, stock_symbol, company_name)
                    
                    # Get comments
                    comments = self.get_post_comments(post, limit=self.comment_limit)
                    
                    # Perform sentiment analysis
                    sentiment_title = self.analyze_sentiment(post.title)
                    
                    # Get comments
                    comments = self.get_post_comments(post, limit=10)
                    
                    # Perform sentiment analysis
                    sentiment_title = self.analyze_sentiment(post.title)
                    sentiment_content = self.analyze_sentiment(post.selftext)
                    
                    # Analyze comments
                    comment_sentiments = [self.analyze_sentiment(comment) for comment in comments]
                    if comment_sentiments:
                        sentiment_comments = sum(comment_sentiments) / len(comment_sentiments)
                    else:
                        sentiment_comments = 0.0
                    
                    # Combine comments
                    combined_comments = " | ".join(comments) if comments else ""
                    
                    # Determine match type
                    match_type = []
                    if matches['ticker_in_title'] or matches['ticker_in_body']:
                        match_type.append(f"ticker:{stock_symbol}")
                    if matches['company_in_title'] or matches['company_in_body']:
                        match_type.append(f"company:{company_name}")
                    
                    # Create post data
                    post_data = {
                        'post_id': post.id,
                        'ticker_symbol': stock_symbol,
                        'company_name': company_name,
                        'subreddit': subreddit_name,
                        'sentiment_post_title': round(sentiment_title, 4),
                        'sentiment_post_content': round(sentiment_content, 4),
                        'sentiment_comments': round(sentiment_comments, 4),
                        # 'sentiment_news_title': round(sentiment_title, 4),
                        # 'sentiment_news_content': round(sentiment_content, 4),
                        # 'sentiment_news_top_comments': round(sentiment_comments, 4),
                        'post_url': f"https://reddit.com{post.permalink}",
                        'num_comments': post.num_comments,
                        'score': post.score,
                        'created_utc': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        'match_type': ', '.join(match_type),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    all_posts_data.append(post_data)
                    print(f"  ✓ {stock_symbol}/{company_name} - {post.title[:50]}...")
            
            # Return aggregated data if any posts found
            if all_posts_data:
                return {
                    'symbol': stock_symbol,
                    'timestamp': datetime.now().isoformat(),
                    'posts_count': len(all_posts_data),
                    'posts': all_posts_data
                }
            
            return None
            
        except Exception as e:
            print(f"  ✗ Error fetching posts for {stock_symbol}: {str(e)}")
            return None


def main():
    """For standalone testing"""
    producer = SentimentProducer()
    if producer.initialize():
        producer.fetch_and_send()
        producer.cleanup()


if __name__ == '__main__':
    main()