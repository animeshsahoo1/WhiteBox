import pathway as pw
from consumers.base_consumer import BaseConsumer
from typing import Optional

def _safe_str(val: Optional[str]) -> str:
    """Convert optional string to string, defaulting to empty string if None"""
    return val if val is not None else ""

class NewsConsumer(BaseConsumer):
    """Consumer for news data from Kafka
    
    Handles three types of news:
    - company: Direct news about a specific stock
    - sector: News about peer/competitor companies  
    - global: Macro/market-wide news
    """
    
    def __init__(self):
        super().__init__(topic_name="news-data")
    
    def get_output_schema(self):
        """Define how to extract news data fields"""
        return {
            "symbol": pw.this.data["symbol"].as_str(),
            "news_type": pw.this.data["news_type"].as_str(),  # company, sector, global
            "timestamp": pw.this.data["timestamp"].as_str(),
            "title": pw.this.data["title"].as_str(),
            "description": pw.this.data["description"].as_str(),
            "source": pw.this.data["source"].as_str(),
            "url": pw.this.data["url"].as_str(),
            "published_at": pw.this.data["published_at"].as_str(),
            "data_source": pw.this.data["data_source"].as_str(),
            # related_to can be null for company news, use apply with safe_str
            "related_to": pw.apply(_safe_str, pw.this.data["related_to"].as_str()),
            "sent_at": pw.this.sent_at
        }