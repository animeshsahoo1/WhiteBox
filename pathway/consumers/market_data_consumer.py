import pathway as pw
from consumers.base_consumer import BaseConsumer

class MarketDataConsumer(BaseConsumer):
    """Consumer for market data from Kafka"""
    
    def __init__(self):
        super().__init__(topic_name="market-data")
    
    def get_output_schema(self):
        """Define how to extract market data fields"""
        return {
            "symbol": pw.this.data["symbol"].as_str(),
            "timestamp": pw.this.data["timestamp"].as_str(),
            "current_price": pw.this.data["current_price"].as_float(),
            "high": pw.this.data["high"].as_float(),
            "low": pw.this.data["low"].as_float(),
            "open": pw.this.data["open"].as_float(),
            "previous_close": pw.this.data["previous_close"].as_float(),
            "change": pw.this.data["change"].as_float(),
            "change_percent": pw.this.data["change_percent"].as_float(),
            "sent_at": pw.this.sent_at
        }