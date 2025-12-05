# Streaming Producers

Kafka producers that fetch data from external APIs and publish to Kafka topics.

## 📋 Overview

Each producer implements multi-source fallback with circuit breaker pattern for robust data collection.

## 🗂️ Files

- **base_producer.py** - Abstract base class with fallback logic and circuit breaker
- **candle_producer.py** - OHLCV candle data from yfinance with CSV fallback
- **market_data_producer.py** - Real-time stock prices from Finnhub/FMP/AlphaVantage
- **news_producer.py** - News articles from NewsAPI/FMP/Finnhub
- **sentiment_producer.py** - Social media sentiment from Reddit/Twitter
- **fundamental_data_producer.py** - Company fundamentals from FMP

## 🔄 Base Producer Features

### Circuit Breaker Pattern
- **HEALTHY** → Normal operation
- **DEGRADED** → Some failures but operational
- **RATE_LIMITED** → Cooldown period (5 min)
- **FAILED** → Disabled temporarily (15 min)

### Multi-Source Fallback
```python
# Priority-based source selection
sources = [
    DataSource("Primary", priority=0),
    DataSource("Backup", priority=1),
    DataSource("Fallback", priority=2)
]

# Automatic failover
for source in sorted(sources, key=lambda x: x.priority):
    if source.can_use():
        data = source.fetch()
        if data:
            return data
```

### Error Handling
- Rate limit detection → Auto cooldown
- Auth failures → Disable source
- Connection errors → Retry with backoff
- Circuit breaker → Prevent cascade failures

## 📊 Producer Implementations

### Candle Producer (NEW)
**Topic**: `candles`  
**Interval**: 60 seconds (configurable)  
**Sources**: yfinance → CSV fallback

Streams OHLCV candle data for backtesting. Supports historical backfill and live polling.

**Output**:
```json
{
  "timestamp": "2025-11-11 10:00:00",
  "open": 177.00,
  "high": 179.20,
  "low": 176.80,
  "close": 178.50,
  "volume": 45678900,
  "symbol": "AAPL",
  "interval": "1h",
  "source": "yfinance"
}
```

**Usage**:
```bash
python producers/candle_producer.py --symbol AAPL --interval 1h --period 1mo
```

### Market Data Producer
**Topic**: `market-data`  
**Interval**: 60 seconds (configurable)  
**Sources**: Finnhub → FMP → Alpha Vantage

**Output**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-11-11T10:00:00",
  "current_price": 178.50,
  "high": 179.20,
  "low": 176.80,
  "open": 177.00,
  "previous_close": 176.00,
  "change": 2.50,
  "change_percent": 1.42,
  "data_source": "Finnhub"
}
```

### News Producer
**Topic**: `news-data`  
**Interval**: 300 seconds  
**Sources**: NewsAPI → FMP → Finnhub

**Output**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-11-11T10:00:00",
  "title": "Apple Reports Strong Earnings",
  "description": "Apple Inc. exceeded...",
  "url": "https://...",
  "source": "CNBC",
  "published_at": "2025-11-11T09:30:00",
  "sentiment": "positive",
  "data_source": "NewsAPI"
}
```

### Sentiment Producer
**Topic**: `sentiment-data`  
**Interval**: 300 seconds  
**Sources**: Reddit → Twitter → NewsAPI

**Output**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-11-11T10:00:00",
  "platform": "reddit",
  "post_title": "AAPL earnings beat!",
  "post_body": "Great quarter for Apple...",
  "score": 1250,
  "comments": 340,
  "sentiment_score": 0.85,
  "sentiment_label": "positive",
  "url": "https://reddit.com/...",
  "data_source": "Reddit"
}
```

### Fundamental Producer
**Topic**: `fundamental-data`  
**Interval**: 3600 seconds  
**Sources**: FMP (primary)

**Output**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-11-11T10:00:00",
  "company_profile": {
    "name": "Apple Inc.",
    "industry": "Consumer Electronics",
    "sector": "Technology"
  },
  "financial_metrics": {
    "revenue": 394328000000,
    "net_income": 99803000000
  },
  "ratios": {
    "pe_ratio": 28.5,
    "pb_ratio": 45.2,
    "debt_to_equity": 1.72
  },
  "data_source": "FMP"
}
```

## 🚀 Usage

### Run Individual Producer
```bash
python producers/market_data_producer.py
python producers/news_producer.py
python producers/sentiment_producer.py
python producers/fundamental_data_producer.py
```

### Environment Variables
See main streaming README for complete `.env` setup.

## 🧪 Testing

### Test Producer Locally
```python
from producers.market_data_producer import MarketDataProducer

producer = MarketDataProducer()
producer.setup_sources()
data = producer.fetch_data('AAPL')
print(data)
```

### Verify Kafka Messages
```bash
# Use localhost:29092 inside kafka container via docker exec
docker exec kafka kafka-console-consumer \
    --topic market-data \
    --bootstrap-server localhost:29092 \
    --from-beginning
```

## 📝 Creating New Producer

```python
from producers.base_producer import BaseProducer

class MyProducer(BaseProducer):
    def __init__(self):
        super().__init__(
            kafka_topic='my-topic',
            fetch_interval=60,
            stocks=['AAPL', 'GOOGL']
        )
    
    def setup_sources(self):
        self.register_source("Primary", self._fetch_primary, priority=0)
        self.register_source("Backup", self._fetch_backup, priority=1)
    
    def _fetch_primary(self, symbol):
        # Fetch logic
        return {"symbol": symbol, "data": "..."}
    
    def _fetch_backup(self, symbol):
        # Fallback logic
        return {"symbol": symbol, "data": "..."}
```

## 🔗 Related
- [streaming/README.md](../README.md) - Full streaming documentation
- [utils/](../utils/) - Kafka utilities
- [fundamental_utils/](../fundamental_utils/) - FMP client and scraping
