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
External APIs ──────┐
                    │
├── Finnhub         │
├── Alpha Vantage   │      ┌──────────────┐
├── FMP             ├─────►│  Producers   │──────► Kafka Topics
├── NewsAPI         │      │  (Priority   │
├── Reddit          │      │   Fallback)  │
└── Twitter         │      └──────────────┘
                    │
                    ▼
           Circuit Breakers
        (Auto-recovery & Retry)
```

## 📁 Structure

```
streaming/
├── producers/              # Kafka producers
│   ├── base_producer.py       # Base class with fallback logic
│   ├── market_data_producer.py    # Real-time price data
│   ├── news_producer.py           # News articles
│   ├── sentiment_producer.py      # Social media sentiment
│   ├── fundamental_data_producer.py   # Company fundamentals
│   └── candle_producer.py         # OHLCV candles for backtesting
│
├── data/                   # Data files
│   └── candles.csv            # Historical OHLCV data for backtesting
│
├── fundamental_utils/      # Utilities for fundamental data
│   ├── fmp_api_client.py      # FMP API wrapper
│   └── web_scraper.py         # Web scraping utilities
│
├── utils/                  # Shared utilities
│   └── kafka_utils.py         # Kafka connection helpers
│
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## 🔌 Data Sources

### Market Data Sources (Priority Order)
1. **Finnhub** (Priority 0) - Real-time quotes, high reliability
2. **Financial Modeling Prep** (Priority 1) - Comprehensive data
3. **Alpha Vantage** (Priority 2) - Backup source

### News Sources (Priority Order)
1. **NewsAPI** (Priority 0) - Curated news articles
2. **Financial Modeling Prep** (Priority 1) - Company-specific news
3. **Finnhub** (Priority 2) - Market news

### Sentiment Sources (Priority Order)
1. **Reddit** (Priority 0) - WallStreetBets, stocks subreddits
2. **Twitter** (Priority 1) - Financial Twitter
3. **NewsAPI Sentiment** (Priority 2) - News-based sentiment

### Fundamental Sources
1. **Financial Modeling Prep** - Primary source
   - Company profile
   - Financial statements (Income, Balance Sheet, Cash Flow)
   - Financial ratios
   - Growth metrics
   - Dividend history
   - SEC filings

2. **Web Scraping** (Fallback)
   - Yahoo Finance
   - MarketWatch
   - Seeking Alpha

## 🚀 Quick Start

### Prerequisites
```bash
# API Keys required
FINNHUB_API_KEY
ALPHA_VANTAGE_API_KEY
FMP_API_KEY
NEWSAPI_API_KEY
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
TWITTER_BEARER_TOKEN
```

### Environment Configuration

Create `streaming/.env`:
```bash
# Kafka Configuration
KAFKA_BROKER=localhost:9092

# Stock Symbols to Track
STOCKS=AAPL,GOOGL,MSFT,TSLA

# Fetch Intervals (seconds)
MARKET_DATA_INTERVAL=60
NEWS_FETCH_INTERVAL=300
SENTIMENT_FETCH_INTERVAL=300
FUNDAMENTAL_INTERVAL=3600

# Market Data APIs
FINNHUB_API_KEY=your_key_here
ALPHA_VANTAGE_API_KEY=your_key_here
FMP_API_KEY=your_key_here

# News APIs
NEWSAPI_API_KEY=your_key_here

# Social Media APIs
REDDIT_CLIENT_ID=your_id_here
REDDIT_CLIENT_SECRET=your_secret_here
REDDIT_USER_AGENT=StockSentimentBot/1.0
TWITTER_BEARER_TOKEN=your_token_here
```

### Docker Deployment

```bash
# Build and start all producers
docker-compose up -d

# View logs
docker-compose logs -f market-producer
docker-compose logs -f news-producer

# Stop producers
docker-compose down
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run individual producers
python producers/market_data_producer.py
python producers/news_producer.py
python producers/sentiment_producer.py
python producers/fundamental_data_producer.py
```

## 📊 Producers Details

### 1. Market Data Producer

**Purpose**: Fetch real-time stock prices and technical data

**Kafka Topic**: `market-data`

**Data Fields**:
```python
{
    'symbol': str,              # Stock ticker (e.g., 'AAPL')
    'timestamp': str,           # ISO format timestamp
    'current_price': float,     # Current trading price
    'high': float,              # Day high
    'low': float,               # Day low
    'open': float,              # Opening price
    'previous_close': float,    # Previous close
    'change': float,            # Price change ($)
    'change_percent': float,    # Price change (%)
    'data_source': str          # Source name
}
```

**Sources**:
- Finnhub: `quote()` API
- FMP: `/stable/quote` endpoint
- Alpha Vantage: `GLOBAL_QUOTE` function

**Fallback Logic**:
```python
Finnhub → FMP → Alpha Vantage → Continue with available data
```

### 2. News Producer

**Purpose**: Collect news articles about stocks

**Kafka Topic**: `news-data`

**Data Fields**:
```python
{
    'symbol': str,              # Stock ticker
    'timestamp': str,           # ISO format
    'title': str,               # Article title
    'description': str,         # Article summary
    'url': str,                 # Article URL
    'source': str,              # News source name
    'published_at': str,        # Publication time
    'sentiment': str,           # 'positive'/'negative'/'neutral'
    'data_source': str          # API source
}
```

**Sources**:
- NewsAPI: `everything()` endpoint
- FMP: `/stable/news` endpoint
- Finnhub: `company_news()` API

**Features**:
- Deduplication by URL
- Sentiment scoring with VADER
- Time filtering (last 24 hours)

### 3. Sentiment Producer

**Purpose**: Analyze social media sentiment

**Kafka Topic**: `sentiment-data`

**Data Fields**:
```python
{
    'symbol': str,              # Stock ticker
    'timestamp': str,           # ISO format
    'platform': str,            # 'reddit' or 'twitter'
    'post_title': str,          # Post title/tweet text
    'post_body': str,           # Post content
    'score': int,               # Upvotes/likes
    'comments': int,            # Comment count
    'sentiment_score': float,   # -1 to 1 (VADER)
    'sentiment_label': str,     # 'positive'/'negative'/'neutral'
    'url': str,                 # Post URL
    'data_source': str          # 'Reddit' or 'Twitter'
}
```

**Sources**:
- Reddit: WallStreetBets, stocks, investing subreddits
- Twitter: Financial Twitter search

**Sentiment Analysis**:
- VADER (Valence Aware Dictionary)
- TextBlob (backup)
- Compound score mapping:
  - Positive: > 0.05
  - Negative: < -0.05
  - Neutral: -0.05 to 0.05

### 4. Fundamental Data Producer

**Purpose**: Collect company fundamental data

**Kafka Topic**: `fundamental-data`

**Data Fields**:
```python
{
    'symbol': str,
    'timestamp': str,
    'company_profile': {
        'name': str,
        'industry': str,
        'sector': str,
        'description': str,
        'ceo': str,
        'website': str
    },
    'financial_metrics': {
        'revenue': float,
        'net_income': float,
        'total_assets': float,
        'total_debt': float,
        'free_cash_flow': float
    },
    'ratios': {
        'pe_ratio': float,
        'pb_ratio': float,
        'debt_to_equity': float,
        'current_ratio': float,
        'roe': float,
        'roa': float
    },
    'growth_metrics': {
        'revenue_growth': float,
        'earnings_growth': float,
        'ebitda_growth': float
    },
    'data_source': str
}
```

**FMP Endpoints Used**:
- `/profile` - Company profile
- `/income-statement` - Income statements
- `/balance-sheet-statement` - Balance sheets
- `/cash-flow-statement` - Cash flows
- `/ratios-ttm` - Trailing twelve months ratios
- `/financial-growth` - Growth metrics
- `/financial-scores` - Piotroski F-Score, etc.
- `/dividends` - Dividend history
- `/sec-filings` - SEC documents

## 🔄 Base Producer Architecture

### Circuit Breaker Pattern

```python
class DataSource:
    """Represents a data source with circuit breaker"""
    
    # States
    HEALTHY → DEGRADED → FAILED
                ↓
           (Auto-recovery)
                ↓
            HEALTHY
```

**State Transitions**:
- **HEALTHY**: Normal operation
- **DEGRADED**: Some failures but still usable
- **RATE_LIMITED**: Cooldown period (5 min)
- **FAILED**: Too many failures, disabled (15 min)

**Error Handling**:
```python
# Rate limiting
if '429' or 'rate limit' in error:
    → RATE_LIMITED (5 min cooldown)

# Authentication
if '401' or '403' or 'invalid api key' in error:
    → FAILED (15 min disabled)

# Circuit breaker
if failure_count >= 3:
    → FAILED (15 min disabled)
```

### Priority Fallback

```python
# Sources sorted by priority
sources = [
    DataSource("Primary", fetch_fn, priority=0),
    DataSource("Backup", fetch_fn, priority=1),
    DataSource("Fallback", fetch_fn, priority=2)
]

# Try each source in order
for source in sorted_sources:
    if source.can_use():
        data = source.fetch()
        if data:
            return data  # Success!
        
# All sources failed
return None
```

## 📈 Monitoring

### Producer Logs

```bash
# View producer status
docker-compose logs -f market-producer

# Example output:
[2025-11-11 10:00:00] Market Producer Started
[2025-11-11 10:00:00] Registering sources: Finnhub, FMP, AlphaVantage
[2025-11-11 10:00:15] ✅ Fetched AAPL from Finnhub
[2025-11-11 10:00:16] ✅ Fetched GOOGL from Finnhub
[2025-11-11 10:00:17] ⚠️  Finnhub rate limited - cooldown until 10:05:00
[2025-11-11 10:00:18] ✅ Fetched MSFT from FMP (fallback)
```

### Source Status Tracking

```python
# Check source health
GET /health

# Response
{
    "market_producer": {
        "sources": {
            "Finnhub": {"status": "healthy", "last_success": "2025-11-11T10:00:15Z"},
            "FMP": {"status": "healthy", "last_success": "2025-11-11T10:00:18Z"},
            "AlphaVantage": {"status": "failed", "last_failure": "2025-11-11T09:45:00Z"}
        }
    }
}
```

## 🔧 Configuration

### Adjust Fetch Intervals

```bash
# Fast updates (every 30 seconds)
MARKET_DATA_INTERVAL=30

# Moderate updates (every 5 minutes)
NEWS_FETCH_INTERVAL=300
SENTIMENT_FETCH_INTERVAL=300

# Slow updates (every hour)
FUNDAMENTAL_INTERVAL=3600
```

### Add/Remove Stocks

```bash
# Edit .env
STOCKS=AAPL,GOOGL,MSFT,TSLA,AMZN,NVDA,META

# Restart producers
docker-compose restart
```

### Enable/Disable Sources

Comment out API keys in `.env` to disable sources:
```bash
# Disable Finnhub
# FINNHUB_API_KEY=your_key

# FMP will become primary source
```

## 🧪 Testing

### Manual Testing

```python
# Test individual producer
cd streaming
python -c "
from producers.market_data_producer import MarketDataProducer
producer = MarketDataProducer()
producer.setup_sources()
data = producer.fetch_data('AAPL')
print(data)
"
```

### Kafka Message Verification

```bash
# View messages in topic
docker exec -it kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic market-data \
    --from-beginning

# Expected output:
{"data": {"symbol": "AAPL", "current_price": 178.50, ...}, "sent_at": "2025-11-11T10:00:00.000"}
```

## 🛡️ Error Handling

### Common Issues

**1. API Rate Limits**
```
Solution: Circuit breaker automatically switches to backup sources
Check: Source will auto-recover after cooldown period
```

**2. Invalid API Keys**
```
Solution: Verify .env file has correct keys
Check: Producer logs show authentication errors
Fix: Update API keys and restart
```

**3. Kafka Connection Failed**
```
Solution: Ensure Kafka is running
Check: docker-compose ps | grep kafka
Fix: docker-compose up kafka
```

**4. No Data Returned**
```
Solution: All sources might be rate limited
Check: Producer logs for source status
Wait: Sources will auto-recover
```

## 📊 Performance

### Throughput
- Market Data: ~4 symbols/sec (per source)
- News: ~10 articles/min
- Sentiment: ~20 posts/min
- Fundamentals: ~1 symbol/5min

### Resource Usage
- CPU: ~5-10% per producer
- Memory: ~100-200 MB per producer
- Network: ~1-5 KB/sec per symbol

## 🔗 Integration

Produced messages are consumed by:
- `pathway/consumers/market_data_consumer.py`
- `pathway/consumers/news_consumer.py`
- `pathway/consumers/sentiment_consumer.py`
- `pathway/consumers/fundamental_data_consumer.py`

See [pathway/README.md](../pathway/README.md) for consumer details.

## 📚 Dependencies

See `requirements.txt`:
- `kafka-python-ng` - Kafka client
- `requests` - HTTP requests
- `finnhub-python` - Finnhub SDK
- `alpha-vantage` - Alpha Vantage SDK
- `newsapi-python` - NewsAPI SDK
- `praw` - Reddit API
- `tweepy` - Twitter API
- `vaderSentiment` - Sentiment analysis
- `apscheduler` - Job scheduling
- `beautifulsoup4` - Web scraping

## 🤝 Contributing

To add a new data source:

1. Create source in base producer:
```python
def _fetch_from_new_source(self, symbol: str) -> Optional[Dict]:
    # Your fetch logic
    return data

# Register in setup_sources()
self.register_source("NewSource", self._fetch_from_new_source, priority=N)
```

2. Handle errors appropriately
3. Add to documentation
4. Test fallback behavior
