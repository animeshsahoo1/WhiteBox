import pathway as pw
from consumers.base_consumer import BaseConsumer


class CandleConsumer(BaseConsumer):
    """
    Consumer for OHLCV candle data from Kafka.
    
    Consumes candles produced by candle_producer in streaming folder.
    Used by the backtesting pipeline.
    
    Message format from producer:
    {
        "data": {
            "timestamp": "2025-11-28 10:30:00-05:00",
            "open": 269.5,
            "high": 270.0,
            "low": 269.0,
            "close": 269.8,
            "volume": 1234567.0,
            "symbol": "AAPL",
            "interval": "1h",
            "source": "yfinance"
        },
        "sent_at": "2025-11-28T15:30:00.123456"
    }
    """
    
    def __init__(self, topic_name: str = "candles"):
        super().__init__(topic_name=topic_name, consumer_group_id="pathway-backtester")
    
    def get_output_schema(self):
        """Extract candle fields from the wrapped data structure."""
        return {
            "timestamp": pw.this.data["timestamp"].as_str(),
            "open": pw.this.data["open"].as_float(),
            "high": pw.this.data["high"].as_float(),
            "low": pw.this.data["low"].as_float(),
            "close": pw.this.data["close"].as_float(),
            "volume": pw.this.data["volume"].as_float(),
        }
