import pathway as pw
from consumers.base_consumer import BaseConsumer

class SentimentConsumer(BaseConsumer):
    """Consumer for Reddit sentiment data from Kafka"""
    
    def __init__(self):
        super().__init__(topic_name="reddit-sentiment")
    
    def get_output_schema(self):
        """
        Define how to extract sentiment data fields.
        
        Note: This keeps the nested structure where posts are arrays.
        If you want to flatten posts into individual rows, override consume() method.
        """
        return {
            "symbol": pw.this.data["symbol"].as_str(),
            "timestamp": pw.this.data["timestamp"].as_str(),
            "posts_count": pw.this.data["posts_count"].as_int(),
            "posts": pw.this.data["posts"],  # Array of posts with all detailed fields
            "sent_at": pw.this.sent_at
        }
    
    def consume(self):
        """
        Consume messages from Kafka and create Pathway table.
        This version creates ONE row per message (posts grouped).
        """
        return super().consume()
    
    def consume_flattened(self):
        """
        Alternative: Flatten posts into individual rows.
        Each post becomes a separate row with all columns.
        
        Returns:
            pw.Table: Flattened table where each row is one post
        """
        # First get the grouped table
        grouped_table = super().consume()
        
        # Flatten the posts array - each post becomes a row
        flattened = grouped_table.flatten(pw.this.posts).select(
            symbol=pw.this.symbol,
            received_at=pw.this.timestamp,
            # Extract individual post fields
            post_id=pw.this.posts["post_id"].as_str(),
            ticker_symbol=pw.this.posts["ticker_symbol"].as_str(),
            company_name=pw.this.posts["company_name"].as_str(),
            subreddit=pw.this.posts["subreddit"].as_str(),
            post_title=pw.this.posts["post_title"].as_str(),
            post_content=pw.this.posts["post_content"].as_str(),
            post_comments=pw.this.posts["post_comments"].as_str(),
            sentiment_post_title=pw.this.posts["sentiment_post_title"].as_float(),
            sentiment_post_content=pw.this.posts["sentiment_post_content"].as_float(),
            sentiment_comments=pw.this.posts["sentiment_comments"].as_float(),
            post_url=pw.this.posts["post_url"].as_str(),
            num_comments=pw.this.posts["num_comments"].as_int(),
            score=pw.this.posts["score"].as_int(),
            created_utc=pw.this.posts["created_utc"].as_str(),
            match_type=pw.this.posts["match_type"].as_str(),
            post_timestamp=pw.this.posts["timestamp"].as_str(),
            sent_at=pw.this.sent_at
        )
        
        self.table = flattened
        print(f"✅ {self.__class__.__name__} initialized (flattened mode)")
        return self.table
