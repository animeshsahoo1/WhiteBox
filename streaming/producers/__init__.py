"""
Kafka Producers for streaming data to Pathway pipelines.

Available producers:
- BaseProducer: Abstract base with multi-source fallback support
- CandleProducer: OHLCV market data (yfinance + CSV fallback)
- MarketDataProducer: Real-time market quotes
- NewsProducer: Financial news articles
- SentimentProducer: Market sentiment data
- FundamentalDataProducer: Company fundamentals
"""

from producers.base_producer import BaseProducer, DataSource, SourceStatus
from producers.candle_producer import CandleProducer
from producers.market_data_producer import MarketDataProducer
from producers.news_producer import NewsProducer
from producers.sentiment_producer import SentimentProducer
from producers.fundamental_data_producer import FundamentalDataProducer

__all__ = [
    "BaseProducer",
    "DataSource", 
    "SourceStatus",
    "CandleProducer",
    "MarketDataProducer",
    "NewsProducer",
    "SentimentProducer",
    "FundamentalDataProducer",
]
