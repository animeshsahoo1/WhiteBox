# Pathway Consumers

Pathway-based Kafka consumers that read streaming data and create real-time processing tables.

## 📋 Overview

Each consumer extends `BaseConsumer` to:
- Subscribe to specific Kafka topics
- Parse JSON messages into Pathway tables
- Extract relevant fields for processing
- Enable real-time stream operations

## 🗂️ Files

| File | Description |
|------|-------------|
| `base_consumer.py` | Abstract base class with Kafka settings |
| `market_data_consumer.py` | Market price data consumer |
| `news_consumer.py` | News articles consumer |
| `sentiment_consumer.py` | Social media sentiment consumer |
| `fundamental_data_consumer.py` | Fundamental data consumer |
| `candle_consumer.py` | OHLCV candle data for backtesting |
| `drift_consumer.py` | Model drift detection consumer |

## 🔄 Base Consumer Architecture

### BaseConsumer Class

```python
class BaseConsumer(ABC):
    def __init__(self, topic_name, consumer_group_id=None, from_beginning=True):
        """
        Args:
            topic_name: Kafka topic to consume from
            consumer_group_id: Consumer group ID (auto-generated if None)
            from_beginning: If True, use "earliest" offset
                           If False, use "latest" (for real-time)
        """
```

### Kafka Settings

Optimized rdkafka settings for throughput and low latency:
```python
rdkafka_settings = {
    "bootstrap.servers": "kafka:29092",
    "group.id": "pathway-{topic}-consumer",
    "auto.offset.reset": "earliest" | "latest",
    "enable.auto.commit": "true",
    "auto.commit.interval.ms": "30000",
    # Performance optimizations
    "fetch.min.bytes": "1024",
    "fetch.wait.max.ms": "100",
    "queued.min.messages": "100000",
}
```

### Usage Pattern

```python
from consumers.market_data_consumer import MarketDataConsumer

# 1. Initialize consumer
consumer = MarketDataConsumer()

# 2. Consume from Kafka (creates Pathway table)
table = consumer.consume()

# 3. Use table in stream processing
processed = table.select(
    symbol=pw.this.symbol,
    price=pw.this.current_price
)
```

## 📊 Consumer Implementations

### Market Data Consumer

**Topic**: `market-data`  
**Consumer Group**: `pathway-market-consumer`

**Schema**:
```python
{
    "symbol": str,
    "timestamp": str,
    "open": float,
    "high": float,
    "low": float,
    "current_price": float,
    "previous_close": float,
    "change": float,
    "change_percent": float,
    "sent_at": str
}
```

---

### News Consumer

**Topic**: `news-data`  
**Consumer Group**: `pathway-news-consumer`

**Schema**:
```python
{
    "symbol": str,
    "timestamp": str,
    "title": str,
    "description": str,
    "source": str,
    "url": str,
    "sentiment": float,
    "sent_at": str
}
```

---

### Sentiment Consumer

**Topic**: `sentiment-data`  
**Consumer Group**: `pathway-sentiment-consumer`

**Schema**:
```python
{
    "symbol": str,
    "timestamp": str,
    "source": str,       # "reddit", "twitter"
    "subreddit": str,    # For Reddit posts
    "title": str,
    "body": str,
    "score": int,
    "num_comments": int,
    "created_utc": int,
    "sent_at": str
}
```

---

### Candle Consumer

**Topic**: `candles`  
**Consumer Group**: `pathway-candle-consumer`

**Schema**:
```python
{
    "symbol": str,
    "interval": str,     # "1h", "1d", etc.
    "timestamp": str,
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": float,
    "sent_at": str
}
```

---

### Fundamental Data Consumer

**Topic**: `fundamental-data`  
**Consumer Group**: `pathway-fundamental-consumer`

**Schema**:
```python
{
    "symbol": str,
    "timestamp": str,
    "company_name": str,
    "sector": str,
    "market_cap": float,
    "pe_ratio": float,
    "eps": float,
    "revenue": float,
    # ... additional financial metrics
    "sent_at": str
}
```

## 🔧 Kafka Message Structure

All messages follow this wrapper format:
```json
{
  "data": {
    "symbol": "AAPL",
    "current_price": 195.50,
    ...
  },
  "sent_at": "2025-12-07T10:00:00.000"
}
```

The `BaseConsumer` extracts the `data` field and flattens it.

## ⚡ Offset Configuration

**Important**: Use appropriate offset settings to avoid RAM spikes:

```python
# For backtesting (need historical data)
consumer = CandleConsumer(from_beginning=True)  # "earliest"

# For real-time analysis (skip old messages)
consumer = MarketDataConsumer(from_beginning=False)  # "latest"
```

## 🧪 Testing

```bash
# Verify consumer can connect to Kafka
python -c "
from consumers.market_data_consumer import MarketDataConsumer
consumer = MarketDataConsumer()
table = consumer.consume()
print('Consumer initialized:', consumer.topic_name)
"
```

## 📚 Related

- [Streaming Producers](../../streaming/producers/README.md) - Data sources
- [Pathway README](../README.md) - Full pipeline documentation
