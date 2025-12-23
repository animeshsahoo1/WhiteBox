# Kafka Producers

Production-ready data producers with multi-source fallback and circuit breaker patterns for streaming market data to Kafka.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BaseProducer                                  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • Multi-source fallback (priority-based)                        ││
│  │ • Circuit breaker (3 failures → 15min cooldown)                 ││
│  │ • Rate limit detection (429 → 5min cooldown)                    ││
│  │ • Auto-recovery after cooldown                                  ││
│  │ • APScheduler for interval-based fetching                       ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────┬───────────┼───────────┬───────────┐
        ▼               ▼           ▼           ▼           ▼
   ┌─────────┐    ┌──────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ Market  │    │  News    │ │Sentiment│ │Fundamntl│ │ Candle  │
   │ Data    │    │          │ │         │ │  Data   │ │         │
   └────┬────┘    └────┬─────┘ └────┬────┘ └────┬────┘ └────┬────┘
        │              │            │           │           │
        ▼              ▼            ▼           ▼           ▼
    market-data   news-data   sentiment-data  fundamental  candles
     (Kafka)       (Kafka)       (Kafka)       (Kafka)     (Kafka)
```

## 📁 Structure

```
producers/
├── base_producer.py           # Base class with circuit breaker
├── market_data_producer.py    # Real-time quotes + historical OHLCV
├── news_producer.py           # Multi-source news (NewsAPI, FMP, Alpha Vantage)
├── sentiment_producer.py      # Reddit + Twitter sentiment (VADER)
├── fundamental_data_producer.py # Fundamental analysis (FMP)
├── candle_producer.py         # Multi-interval OHLCV candles
├── demo_market_producer.py    # Demo data (simulated)
├── fundamental_report.py      # LLM-generated fundamental reports
├── pathway_market_source.py   # Alternative market data source
└── pdf_parser.py              # PDF extraction utilities
```

## 🔧 Producers

### Base Producer (`base_producer.py`)

Foundation class providing:
- **Multi-source fallback**: Register multiple data sources with priority
- **Circuit breaker**: Auto-disable failing sources (3 failures → 15min cooldown)
- **Rate limit handling**: Detect 429 responses (5min cooldown)
- **Auto-recovery**: Sources reset after cooldown period
- **Scheduled fetching**: APScheduler for interval-based polling

```python
class DataSource:
    max_failures = 3        # Failures before circuit breaks
    cooldown_period = 300   # 5 min for rate limits
    reset_after = 900       # 15 min before retry

class SourceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
```

### Market Data Producer (`market_data_producer.py`)

Hybrid producer: historical data first, then real-time updates.

| Source | Priority | API |
|--------|----------|-----|
| FMP | 0 (primary) | Financial Modeling Prep |
| Finnhub | 1 (fallback) | Finnhub.io |
| yfinance | historical | Yahoo Finance |

**Kafka Topic**: `market-data`

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2024-01-15T09:30:00",
  "sent_at": "2024-01-15T09:30:05",
  "open": 185.50,
  "high": 186.20,
  "low": 185.10,
  "current_price": 185.80,
  "previous_close": 184.90,
  "change": 0.90,
  "change_percent": 0.49,
  "volume": 15234567,
  "data_source": "FMP"
}
```

**Environment Variables**:
```bash
STOCKS=AAPL,GOOGL,MSFT
MARKET_DATA_INTERVAL=60          # Seconds between updates
MARKET_HISTORICAL_PERIOD=1d      # Historical data to send first
MARKET_HISTORICAL_INTERVAL=1m    # Historical candle interval
FMP_API_KEY=your_key
FINNHUB_API_KEY=your_key
```

### News Producer (`news_producer.py`)

Multi-source news aggregation with deduplication.

| Source | Priority | Coverage |
|--------|----------|----------|
| NewsAPI | 0 | Global news |
| FMP | 1 | Company-specific |
| Alpha Vantage | 2 | Financial news |

**News Types**:
- Company news: Direct mentions of stock symbol
- Sector news: Peer/competitor companies
- Global news: Market-wide macro events

**Kafka Topic**: `news-data`

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "title": "Apple Reports Q4 Earnings",
  "description": "...",
  "url": "https://...",
  "source": "NewsAPI",
  "published_at": "2024-01-15T14:30:00Z",
  "news_type": "company|sector|global",
  "sentiment": 0.75,
  "relevance_score": 0.92
}
```

**Environment Variables**:
```bash
STOCKS=AAPL,GOOGL,MSFT
NEWS_DATA_INTERVAL=1800          # 30 minutes
NEWS_API_KEY=your_key
FMP_API_KEY=your_key
ALPHA_VANTAGE_API_KEY=your_key
```

### Sentiment Producer (`sentiment_producer.py`)

Social media sentiment analysis using VADER and TextBlob.

| Source | Platform | API |
|--------|----------|-----|
| Reddit | PRAW | Reddit API (multiple accounts) |
| Twitter | Webhook | Twitter API v2 |

**Features**:
- Multi-account Reddit rotation (rate limit distribution)
- VADER + TextBlob sentiment scoring
- Company, sector, and global sentiment tracking
- Logging to `sentiment_logs/` directory

**Kafka Topic**: `sentiment-data`

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "text": "Apple stock looking bullish...",
  "source": "reddit|twitter",
  "subreddit": "wallstreetbets",
  "sentiment_vader": 0.75,
  "sentiment_textblob": 0.60,
  "sentiment_type": "company|sector|global",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Environment Variables**:
```bash
STOCKS=AAPL,TSLA,NVDA
SENTIMENT_DATA_INTERVAL=600      # 10 minutes

# Reddit (supports multiple accounts)
REDDIT_CLIENT_ID_1=your_id
REDDIT_CLIENT_SECRET_1=your_secret
REDDIT_USER_AGENT_1=your_agent
REDDIT_RATE_LIMIT=55             # Max calls per minute

# Twitter
TWITTER_API_KEY=your_key
TWITTER_WEBHOOK_URL=https://...
```

### Fundamental Data Producer (`fundamental_data_producer.py`)

Comprehensive fundamental analysis from FMP.

**Data Includes**:
- Company profile
- Financial statements (income, balance sheet, cash flow)
- Key ratios and metrics
- SEC filings
- Analyst estimates
- Optional: Web scraped articles (Serpex)

**Kafka Topic**: `fundamental-data`

**Environment Variables**:
```bash
STOCKS=AAPL,MSFT,GOOG
FUNDAMENTAL_DATA_INTERVAL=3600   # 1 hour
FMP_API_KEY=your_key
SERPEX_API_KEY=your_key          # Optional web scraping
MAX_ARTICLES_PER_STOCK=10
```

### Candle Producer (`candle_producer.py`)

Multi-symbol, multi-interval OHLCV candle streaming.

**Sources**:
1. yfinance (live data)
2. CSV fallback (historical files)

**Supported Intervals**:
```
1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo
```

**Kafka Topic**: `candles`

**Output Schema**:
```json
{
  "symbol": "AAPL",
  "interval": "1h",
  "timestamp": "2024-01-15T10:00:00",
  "open": 185.50,
  "high": 186.20,
  "low": 185.10,
  "close": 185.80,
  "volume": 5234567,
  "source": "yfinance"
}
```

**Environment Variables**:
```bash
STOCKS=AAPL,GOOGL,TSLA
INTERVALS=1h,1d                  # Candle intervals
CANDLE_KAFKA_TOPIC=candles
CANDLE_POLL_INTERVAL=60
REDIS_URL=redis://...            # State persistence
```

## 🚀 Usage

### Run Individual Producer

```bash
cd /backend/streaming

# Market data
python -m producers.market_data_producer

# News
python -m producers.news_producer

# Sentiment
python -m producers.sentiment_producer

# Fundamentals
python -m producers.fundamental_data_producer

# Candles
python -m producers.candle_producer
```

### Docker Compose

All producers run via the streaming service:
```bash
cd /backend/streaming
docker-compose up
```

## 📊 Monitoring

Each producer prints status icons:
- ✅ `HEALTHY` - Source working normally
- ⚠️ `DEGRADED` - Some failures, still usable
- ❌ `FAILED` - Circuit breaker triggered
- ⏳ `RATE_LIMITED` - In cooldown period
- ♻️ Auto-reset - Source recovered

## 📚 Related

- [Consumers](../../pathway/consumers/README.md) - Kafka consumers
- [Kafka Setup](../../kafka/README.md) - Kafka configuration
- [WebSocket Events](../../WEBSOCKET_EVENT_SCHEMAS.md) - Real-time events
