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
            "total_results": pw.this.data["total_results"].as_int(),
            "articles": pw.this.data["articles"],
            "sent_at": pw.this.sent_at
        }