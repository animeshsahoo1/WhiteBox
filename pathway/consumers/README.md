# Pathway Consumers

Pathway-based Kafka consumers that read streaming data and create real-time processing tables.

## 📋 Overview

Each consumer extends `BaseConsumer` to:
- Subscribe to specific Kafka topics
- Parse JSON messages into Pathway tables
- Extract relevant fields for processing
- Enable real-time stream operations

## 🗂️ Files

- **base_consumer.py** - Abstract base class for all consumers
- **market_data_consumer.py** - Market price data consumer
- **news_consumer.py** - News articles consumer
- **sentiment_consumer.py** - Social media sentiment consumer
- **fundamental_data_consumer.py** - Fundamental data consumer

## 🔄 Base Consumer Architecture

### Design Pattern

```python
from consumers.base_consumer import BaseConsumer
import pathway as pw

class MyConsumer(BaseConsumer):
    def __init__(self):
        super().__init__(
            topic_name="my-topic",
            consumer_group_id="pathway-my-consumer"
        )
    
    def get_output_schema(self):
        """Define what to extract from Kafka messages"""
        return {
            "symbol": pw.this.data["symbol"],
            "value": pw.this.data["value"],
            "sent_at": pw.this.sent_at
        }
```

### Kafka Message Structure

All messages follow this wrapper format:
```json
{
  "data": {
    "symbol": "AAPL",
    "current_price": 178.50,
    ...
  },
  "sent_at": "2025-11-11T10:00:00.000"
}
```

### Usage Flow

```python
# 1. Initialize consumer
consumer = MyConsumer()

# 2. Consume from Kafka (creates Pathway table)
table = consumer.consume()

# 3. Use table in stream processing
processed = table.select(
    symbol=pw.this.symbol,
    value=pw.this.value * 2
)
```

## 📊 Consumer Implementations

### Market Data Consumer

**Topic**: `market-data`  
**Consumer Group**: `pathway-market-consumer`

**Schema**:
```python
{
    "symbol": str,          # Stock ticker
    "timestamp": str,       # Data timestamp
    "open": float,
    "high": float,
    "low": float,
    "current_price": float,
    "previous_close": float,
    "change": float,
    "change_percent": float,
    "sent_at": str          # Kafka message timestamp
}
```

**Usage**:
```python
from consumers.market_data_consumer import MarketDataConsumer

consumer = MarketDataConsumer()
market_table = consumer.consume()

# Process stream
windowed = market_table.windowby(
    pw.this.sent_at.dt.strptime("%Y-%m-%dT%H:%M:%S.%f"),
    window=pw.temporal.tumbling(duration=timedelta(minutes=1))
)
```

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
    "url": str,
    "source": str,
    "published_at": str,
    "sentiment": str,       # 'positive'/'negative'/'neutral'
    "sent_at": str
}
```

**Usage**:
```python
from consumers.news_consumer import NewsConsumer

consumer = NewsConsumer()
news_table = consumer.consume()

# Group news by symbol
grouped = news_table.groupby(pw.this.symbol).reduce(
    symbol=pw.this.symbol,
    articles=pw.reducers.tuple(pw.this.title)
)
```

### Sentiment Consumer

**Topic**: `sentiment-data`  
**Consumer Group**: `pathway-sentiment-consumer`

**Schema**:
```python
{
    "symbol": str,
    "timestamp": str,
    "platform": str,         # 'reddit' or 'twitter'
    "post_title": str,
    "post_body": str,
    "score": int,            # Upvotes/likes
    "comments": int,
    "sentiment_score": float, # -1 to 1
    "sentiment_label": str,   # 'positive'/'negative'/'neutral'
    "url": str,
    "sent_at": str
}
```

**Usage**:
```python
from consumers.sentiment_consumer import SentimentConsumer

consumer = SentimentConsumer()
sentiment_table = consumer.consume()

# Calculate average sentiment
avg_sentiment = sentiment_table.groupby(pw.this.symbol).reduce(
    symbol=pw.this.symbol,
    avg_score=pw.reducers.avg(pw.this.sentiment_score),
    mentions=pw.reducers.count()
)
```

### Fundamental Data Consumer

**Topic**: `fundamental-data`  
**Consumer Group**: `pathway-fundamental-consumer`

**Schema**:
```python
{
    "symbol": str,
    "timestamp": str,
    "company_profile": dict,     # Name, industry, sector
    "financial_metrics": dict,   # Revenue, income, assets
    "ratios": dict,              # P/E, P/B, ROE, etc.
    "growth_metrics": dict,      # Revenue/earnings growth
    "sent_at": str
}
```

**Usage**:
```python
from consumers.fundamental_data_consumer import FundamentalDataConsumer

consumer = FundamentalDataConsumer()
fundamental_table = consumer.consume()

# Extract specific metrics
metrics = fundamental_table.select(
    symbol=pw.this.symbol,
    pe_ratio=pw.this.ratios["pe_ratio"],
    revenue=pw.this.financial_metrics["revenue"]
)
```

## 🔧 Configuration

### Kafka Settings

Default rdkafka settings in `BaseConsumer`:
```python
rdkafka_settings = {
    "bootstrap.servers": "kafka:29092",
    "group.id": "pathway-{topic}-consumer",
    "auto.offset.reset": "earliest",      # Start from beginning
    "enable.auto.commit": "true",         # Auto-commit offsets
    "auto.commit.interval.ms": "60000",   # Commit every 60 seconds
}
```

### Environment Variables

```bash
# In pathway/.env
KAFKA_BROKER=kafka:29092

# Override in docker-compose.yml
environment:
  KAFKA_BROKER: kafka:29092
```

### Consumer Groups

Each consumer has its own group to track offsets independently:
- `pathway-market-consumer`
- `pathway-news-consumer`
- `pathway-sentiment-consumer`
- `pathway-fundamental-consumer`

## 🧪 Testing

### Test Consumer Locally

```python
from consumers.market_data_consumer import MarketDataConsumer
import pathway as pw

# Initialize
consumer = MarketDataConsumer()
table = consumer.consume()

# Debug: Print table content
pw.debug.compute_and_print(table)

# Run processing
pw.run()
```

### Verify Consumer Group

```bash
# Check consumer group status
docker exec kafka kafka-consumer-groups \
    --describe \
    --group pathway-market-consumer \
    --bootstrap-server localhost:9092

# Expected output:
# TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# market-data     0          150             150             0
```

### Monitor Lag

```bash
# Check lag for all consumer groups
docker exec kafka kafka-consumer-groups \
    --describe \
    --all-groups \
    --bootstrap-server localhost:9092
```

## 📝 Creating New Consumer

```python
from consumers.base_consumer import BaseConsumer
import pathway as pw

class CustomConsumer(BaseConsumer):
    def __init__(self):
        super().__init__(
            topic_name="custom-topic",
            consumer_group_id="pathway-custom-consumer"
        )
    
    def get_output_schema(self):
        """Extract fields from Kafka messages"""
        return {
            "symbol": pw.this.data["symbol"],
            "value": pw.this.data["value"],
            "timestamp": pw.this.data["timestamp"],
            "sent_at": pw.this.sent_at
        }

# Usage
consumer = CustomConsumer()
table = consumer.consume()
```

## 🔄 Offset Management

### Auto Commit (Default)
```python
# Offsets committed automatically every 60 seconds
"enable.auto.commit": "true"
"auto.commit.interval.ms": "60000"
```

### Manual Commit
```python
# Disable auto-commit for manual control
rdkafka_settings = {
    "enable.auto.commit": "false"
}
# Then commit manually in processing logic
```

### Reset Offsets
```bash
# Reset to earliest (reprocess all data)
docker exec kafka kafka-consumer-groups \
    --reset-offsets \
    --to-earliest \
    --group pathway-market-consumer \
    --topic market-data \
    --execute

# Reset to latest (skip existing data)
docker exec kafka kafka-consumer-groups \
    --reset-offsets \
    --to-latest \
    --group pathway-market-consumer \
    --topic market-data \
    --execute
```

## 🛡️ Error Handling

### Kafka Connection Issues
```python
# Pathway automatically handles reconnection
# Consumer will resume from last committed offset
```

### Malformed Messages
```python
# Handle in get_output_schema()
def get_output_schema(self):
    return {
        "symbol": pw.coalesce(
            pw.this.data["symbol"],
            "UNKNOWN"  # Default value
        ),
        "value": pw.coalesce(
            pw.this.data["value"],
            0.0
        )
    }
```

### Missing Fields
```python
# Use pw.coalesce for safe extraction
"price": pw.coalesce(pw.this.data["current_price"], 0.0)
```

## 📊 Performance

### Throughput
- Market data: ~1000 messages/sec
- News: ~100 messages/sec
- Sentiment: ~200 messages/sec
- Fundamentals: ~10 messages/sec

### Resource Usage
- CPU: 5-10% per consumer
- Memory: 200-400 MB per consumer
- Network: Depends on message size

## 🔗 Related

- [base_consumer.py](base_consumer.py) - Base class implementation
- [../agents/](../agents/) - Agents that process these tables
- [../main_*.py](../) - Pipeline entry points using these consumers
