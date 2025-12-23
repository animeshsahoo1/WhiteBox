# Streaming Data Producers

Real-time data collection layer that fetches market data, news, sentiment, and fundamental information from multiple sources and publishes to Kafka topics.

## 📋 Overview

The streaming layer implements a robust, fault-tolerant data collection system with:
- **Multi-source fallback**: Automatic failover between data providers
- **Circuit breaker pattern**: Intelligent error handling and recovery
- **Rate limit management**: Smart cooldown and retry mechanisms
- **Scheduled execution**: APScheduler for periodic data fetching

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL APIs                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Finnhub  │ │   FMP    │ │ AlphaV   │ │ NewsAPI  │            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘            │
│       │            │            │            │                   │
│  ┌────┴────────────┴────────────┴────────────┴────┐             │
│  │           PRIORITY-BASED FALLBACK              │             │
│  └───────────────────────┬────────────────────────┘             │
│                          │                                       │
│  ┌───────────────────────┴────────────────────────┐             │
│  │              CIRCUIT BREAKER                    │             │
│  │  HEALTHY → DEGRADED → RATE_LIMITED → FAILED   │             │
│  └───────────────────────┬────────────────────────┘             │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   KAFKA     │
                    │   TOPICS    │
                    └─────────────┘
```

## 📁 Structure

```
streaming/
├── producers/              # Kafka producers
│   ├── base_producer.py       # Base class with fallback + circuit breaker
│   ├── market_data_producer.py    # Real-time stock prices
│   ├── news_producer.py           # News articles
│   ├── sentiment_producer.py      # Social media sentiment
│   ├── fundamental_data_producer.py   # Company fundamentals
│   ├── candle_producer.py         # OHLCV candles for backtesting
│   ├── demo_market_producer.py    # Demo market data
│   ├── fundamental_report.py      # Fundamental report generation
│   ├── pdf_parser.py              # SEC filing parser
│   └── pathway_market_source.py   # Pathway market source
│
├── utils/                  # Shared utilities
│   └── kafka_utils.py         # Kafka connection helpers
│
├── data/                   # Data files
│   └── candles.csv            # Historical OHLCV data
│
├── cloudflared/            # Cloudflare tunnel config
├── sentiment_logs/         # Sentiment logging
│
├── webhook_receiver.py     # Twitter webhook endpoint (Flask)
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## 🔌 Data Sources

### Market Data (Priority Order)
| Priority | Source | Rate Limit | Notes |
|----------|--------|------------|-------|
| 0 | Finnhub | 60/min | Real-time quotes, high reliability |
| 1 | FMP | 250/day | Comprehensive data |
| 2 | Alpha Vantage | 25/day | Backup source |

### News (Priority Order)
| Priority | Source | Rate Limit | Notes |
|----------|--------|------------|-------|
| 0 | NewsAPI | 100/day | Curated news articles |
| 1 | FMP | 250/day | Company-specific news |
| 2 | Finnhub | 60/min | Market news |

### Sentiment (Priority Order)
| Priority | Source | Rate Limit | Notes |
|----------|--------|------------|-------|
| 0 | Reddit | 60/min | r/wallstreetbets, r/stocks |
| 1 | Twitter | Webhook | Via TwitterAPI.io webhooks |
| 2 | NewsAPI | 100/day | News-based sentiment |

### Fundamental Data
| Source | Data |
|--------|------|
| FMP | Company profile, financial statements, ratios, growth metrics |

## 🚀 Quick Start

### Environment Configuration

Create `streaming/.env`:
```bash
# Kafka
KAFKA_BROKER=kafka:29092

# Stock Symbols
STOCKS=AAPL,GOOGL,TSLA,NVDA

# Fetch Intervals (seconds)
MARKET_DATA_INTERVAL=60
NEWS_FETCH_INTERVAL=300
SENTIMENT_FETCH_INTERVAL=300
FUNDAMENTAL_INTERVAL=3600

# Market Data APIs
FINNHUB_API_KEY=your_key
ALPHA_VANTAGE_API_KEY=your_key
FMP_API_KEY=your_key

# News APIs
NEWSAPI_API_KEY=your_key

# Social Media APIs
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=StockSentimentBot/1.0
TWITTER_BEARER_TOKEN=your_token
```

### Docker Deployment

```bash
# From streaming directory
docker compose up -d

# View logs
docker compose logs -f market-producer
docker compose logs -f news-producer
```

### Local Development

```bash
pip install -r requirements.txt

# Run individual producers
python producers/market_data_producer.py
python producers/news_producer.py
python producers/sentiment_producer.py
```

## 📊 Producer Implementations

### Base Producer (`producers/base_producer.py`)

Core features:
- **Circuit Breaker States**: HEALTHY → DEGRADED → RATE_LIMITED → FAILED
- **Multi-source Fallback**: Priority-based source selection
- **Auto-recovery**: Sources automatically reset after cooldown
- **APScheduler**: Periodic data fetching

```python
class DataSource:
    """Source with circuit breaker pattern"""
    name: str
    fetch_func: Callable
    priority: int  # 0 = highest priority
    
    # Circuit breaker settings
    max_failures: int = 3
    cooldown_period: int = 300  # 5 min for rate limits
    reset_after: int = 900      # 15 min for failed sources
```

### Market Data Producer

**Topic**: `market-data`  
**Interval**: 60 seconds (configurable)

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-12-07T10:00:00",
  "current_price": 195.50,
  "high": 196.20,
  "low": 194.80,
  "open": 195.00,
  "previous_close": 194.00,
  "change": 1.50,
  "change_percent": 0.77,
  "data_source": "Finnhub"
}
```

### News Producer

**Topic**: `news-data`  
**Interval**: 300 seconds (5 min)

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-12-07T10:00:00",
  "title": "Apple announces new product",
  "description": "...",
  "source": "Reuters",
  "url": "https://...",
  "sentiment": 0.5,
  "data_source": "NewsAPI"
}
```

### Sentiment Producer

**Topic**: `sentiment-data`  
**Interval**: 300 seconds (5 min)

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-12-07T10:00:00",
  "source": "reddit",
  "subreddit": "wallstreetbets",
  "title": "AAPL to the moon!",
  "body": "...",
  "score": 150,
  "num_comments": 45,
  "created_utc": 1733569200,
  "data_source": "Reddit"
}
```

### Candle Producer

**Topic**: `candles`  
**Interval**: 60 seconds (configurable)  
**Sources**: yfinance → CSV fallback

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "interval": "1h",
  "timestamp": "2025-12-07 10:00:00",
  "open": 195.00,
  "high": 196.20,
  "low": 194.80,
  "close": 195.50,
  "volume": 45678900,
  "source": "yfinance"
}
```

### Fundamental Data Producer

**Topic**: `fundamental-data`  
**Interval**: 3600 seconds (1 hour)

**Data Collected**:
- Company profile
- Income statement
- Balance sheet
- Cash flow statement
- Financial ratios
- Growth metrics
- Dividend history

## 📡 Twitter Webhook Receiver

`webhook_receiver.py` is a Flask server that receives real-time tweets from TwitterAPI.io:

```bash
# Start webhook receiver
python webhook_receiver.py
```

**Endpoint**: `POST /webhook/twitter`

**Features**:
- In-memory tweet buffer (1000 tweets per stock)
- Deduplication by tweet ID
- Rule tag to stock mapping
- Thread-safe access

## 🔧 Circuit Breaker Details

### States
| State | Description | Action |
|-------|-------------|--------|
| HEALTHY | Normal operation | Use source |
| DEGRADED | Some failures | Use source with caution |
| RATE_LIMITED | Hit rate limit | Cooldown 5 min |
| FAILED | Too many failures | Disabled 15 min |

### Error Handling
```python
# Rate limit detected
if "429" in error or "rate limit" in error:
    source.status = RATE_LIMITED
    source.cooldown_until = now + 5 min

# Auth failure
if "401" in error or "403" in error:
    source.status = FAILED
    source.cooldown_until = now + 15 min

# Circuit breaker triggered
if source.failure_count >= 3:
    source.status = FAILED
```

## 🐳 Docker Services

| Service | Description |
|---------|-------------|
| `market-producer` | Real-time stock prices |
| `news-producer` | News articles |
| `sentiment-producer` | Social media sentiment |
| `fundamental-producer` | Company fundamentals |
| `candle-producer` | OHLCV candles |
| `webhook-receiver` | Twitter webhook endpoint |

## 📈 Kafka Topics

| Topic | Producer | Data |
|-------|----------|------|
| `market-data` | market_data_producer | Stock prices, changes |
| `news-data` | news_producer | News articles |
| `sentiment-data` | sentiment_producer | Reddit/Twitter posts |
| `fundamental-data` | fundamental_data_producer | Financial data |
| `candles` | candle_producer | OHLCV bars |

## 🔍 Troubleshooting

### Producer Not Sending Data

```bash
# Check logs
docker compose logs -f market-producer

# Verify Kafka connection
docker exec kafka kafka-topics --list --bootstrap-server localhost:29092

# Check API keys
echo $FINNHUB_API_KEY
```

### Rate Limit Issues

```bash
# View producer logs for cooldown messages
docker compose logs market-producer | grep "cooldown"

# Increase fetch interval in .env
MARKET_DATA_INTERVAL=120  # 2 minutes
```

### Kafka Connection Failed

```bash
# Ensure Kafka is running
docker compose ps kafka

# Check network
docker network ls | grep stock-network
```

## 📚 Additional Documentation

- [Producers README](producers/README.md) - Detailed producer documentation
