import pathway as pw
from consumers.base_consumer import BaseConsumer

class NewsConsumer(BaseConsumer):
    """Consumer for news data from Kafka"""
    
    def __init__(self):
        super().__init__(topic_name="news-data")
    
    def get_output_schema(self):
        """Define how to extract news data fields"""
        return {
            "symbol": pw.this.data["symbol"].as_str(),
            "timestamp": pw.this.data["timestamp"].as_str(),
            "title": pw.this.data["title"].as_str(),
            "description": pw.this.data["description"].as_str(),
            "source": pw.this.data["source"].as_str(),
            "url": pw.this.data["url"].as_str(),
            "published_at":  pw.this.data["published_at"].as_str(),
            "sent_at": pw.this.sent_at
        }