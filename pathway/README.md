# Pathway Stream Processing & AI Analysis

Real-time stream processing layer that consumes data from Kafka, performs AI-powered analysis using LLMs, and serves reports via FastAPI with Redis caching.

## 📋 Overview

This layer transforms raw streaming data into actionable intelligence using:
- **Pathway**: Real-time data processing with windowing and aggregation
- **OpenAI GPT-4**: LLM-powered analysis and report generation
- **Redis**: High-speed report caching and distribution
- **FastAPI**: REST API for report retrieval

## 🏗️ Architecture

```
┌─────────────┐
│    Kafka    │ (market-data, news-data, sentiment-data, fundamental-data)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              Pathway Consumers                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │   Market    │  │     News     │  │  Sentiment    │ │
│  │  Consumer   │  │   Consumer   │  │   Consumer    │ │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘ │
│         │                │                   │         │
│         ▼                ▼                   ▼         │
│  ┌──────────────────────────────────────────────────┐ │
│  │        Pathway Stream Processing                 │ │
│  │  • Windowing (1-min tumbling windows)           │ │
│  │  • Technical indicators calculation              │ │
│  │  • Aggregation & grouping                        │ │
│  └──────────────────┬───────────────────────────────┘ │
│                     │                                  │
│                     ▼                                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │          LLM Analysis Agents                     │ │
│  │  • Market analysis (technical indicators)        │ │
│  │  • News synthesis & impact analysis              │ │
│  │  • Sentiment interpretation                      │ │
│  │  • Fundamental evaluation                        │ │
│  └──────────────────┬───────────────────────────────┘ │
└─────────────────────┼───────────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │    Redis     │ (pw.io.python observer)
              │    Cache     │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │   FastAPI    │
              │Reports Server│
              └──────────────┘
```

## 📁 Structure

```
pathway/
├── consumers/              # Pathway Kafka consumers
│   ├── base_consumer.py       # Base consumer class
│   ├── market_data_consumer.py    # Market data stream
│   ├── news_consumer.py           # News stream
│   ├── sentiment_consumer.py      # Sentiment stream
│   └── fundamental_data_consumer.py   # Fundamentals stream
│
├── agents/                 # LLM analysis agents
│   ├── market_agent.py        # Market technical analysis
│   ├── news_agent.py          # News synthesis
│   ├── sentiment_agent.py     # Sentiment interpretation
│   └── fundamental_agent.py   # Fundamental evaluation
│
├── api/                    # FastAPI server
│   ├── fastapi_server.py      # REST API endpoints
│   └── __init__.py
│
├── reports/                # Generated reports (mounted volume)
│   ├── market/
│   ├── news/
│   ├── sentiment/
│   └── fundamental/
│
├── main_market.py          # Market pipeline entry point
├── main_news.py            # News pipeline entry point
├── main_sentiment.py       # Sentiment pipeline entry point
├── main_fundamental.py     # Fundamentals pipeline entry point
├── redis_cache.py          # Redis integration utilities
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🚀 Quick Start

### Prerequisites
```bash
OPENAI_API_KEY=your_openai_key
KAFKA_BROKER=kafka:29092
REDIS_HOST=redis
REDIS_PORT=6379
```

### Environment Configuration

Create `pathway/.env`:
```bash
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Kafka
KAFKA_BROKER=kafka:29092

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_REPORT_TTL=3600  # Optional: 1 hour TTL

# Processing
MARKET_WINDOW_DURATION=60  # 1-minute windows
NEWS_WINDOW_DURATION=300   # 5-minute windows
SENTIMENT_WINDOW_DURATION=300
```

### Docker Deployment

```bash
# Start all consumers + API
docker-compose up -d

# View logs
docker-compose logs -f market-consumer
docker-compose logs -f reports-api

# Check health
curl http://localhost:8000/health
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run individual pipelines
python main_market.py
python main_news.py
python main_sentiment.py
python main_fundamental.py

# Run API server
uvicorn api.fastapi_server:app --reload --port 8000
```

## 📊 Data Processing Pipelines

### 1. Market Data Pipeline

**Consumer**: `market_data_consumer.py`  
**Agent**: `market_agent.py`  
**Entry Point**: `main_market.py`

**Process Flow**:
```
Kafka → Pathway Table → Calculate Indicators → Window (1-min) → 
Aggregate → LLM Analysis → Redis Cache
```

**Technical Indicators Calculated**:
```python
# Price metrics
price_range = high - low
typical_price = (high + low + close) / 3
price_vs_open = ((close - open) / open) * 100

# Volatility
intraday_volatility = ((high - low) / low) * 100

# Momentum (within window)
max_price = reducers.max(current_price)
min_price = reducers.min(current_price)
avg_price = reducers.avg(current_price)

# Trend
price_direction = "up" if close > open else "down"
```

**LLM Prompt Structure**:
```
You are a market analyst. Analyze these metrics:
- Current Price: $X
- Change: +X%
- High/Low: $X / $X
- Volatility: X%
- Trend: [up/down]

Provide:
1. Technical overview
2. Price action analysis
3. Key support/resistance levels
4. Short-term outlook
```

**Output**: Markdown report cached in Redis under `reports:SYMBOL.market`

### 2. News Pipeline

**Consumer**: `news_consumer.py`  
**Agent**: `news_agent.py`  
**Entry Point**: `main_news.py`

**Process Flow**:
```
Kafka → Pathway Table → Window (5-min) → 
Group by Symbol → Aggregate Articles → LLM Synthesis → Redis
```

**Aggregation**:
```python
# Within each window, combine all news for symbol
news_list = reducers.tuple(
    title=this.title,
    description=this.description,
    source=this.source,
    sentiment=this.sentiment
)
```

**LLM Analysis**:
- Synthesize multiple articles into coherent summary
- Identify key themes and trends
- Assess potential market impact
- Extract actionable insights

**Output**: Comprehensive news report with:
- Executive summary
- Key developments
- Market implications
- Sentiment assessment

### 3. Sentiment Pipeline

**Consumer**: `sentiment_consumer.py`  
**Agent**: `sentiment_agent.py`  
**Entry Point**: `main_sentiment.py`

**Process Flow**:
```
Kafka → Pathway Table → Parse Sentiment Scores → 
Window → Aggregate Metrics → LLM Interpretation → Redis
```

**Metrics Calculated**:
```python
# Aggregate sentiment metrics per window
avg_sentiment = reducers.avg(sentiment_score)
positive_count = reducers.count_if(sentiment_label == 'positive')
negative_count = reducers.count_if(sentiment_label == 'negative')
total_mentions = reducers.count()

# Platform breakdown
reddit_mentions = reducers.count_if(platform == 'reddit')
twitter_mentions = reducers.count_if(platform == 'twitter')
```

**LLM Interpretation**:
- Analyze sentiment trends
- Identify discussion themes
- Gauge retail investor sentiment
- Compare across platforms

**Output**: Sentiment report with:
- Overall sentiment score
- Platform-specific insights
- Key discussion points
- Sentiment trend analysis

### 4. Fundamental Pipeline

**Consumer**: `fundamental_data_consumer.py`  
**Agent**: `fundamental_agent.py`  
**Entry Point**: `main_fundamental.py`

**Process Flow**:
```
Kafka → Pathway Table → Parse Financials → 
Latest Data → LLM Analysis → Redis
```

**Data Parsed**:
```python
# Company profile
company_name, industry, sector, description

# Financial metrics
revenue, net_income, total_assets, total_debt

# Ratios
pe_ratio, pb_ratio, roe, roa, debt_to_equity

# Growth
revenue_growth, earnings_growth
```

**LLM Analysis**:
- Evaluate financial health
- Assess valuation metrics
- Analyze growth trajectory
- Compare to industry standards
- Identify strengths/weaknesses

**Output**: Fundamental report with:
- Company overview
- Financial analysis
- Valuation assessment
- Growth outlook
- Investment thesis

## 🔄 Pathway Windowing

### Tumbling Windows

All pipelines use **tumbling windows** for processing:

```python
# 1-minute tumbling windows
windowed = table.windowby(
    pw.this.sent_at,
    window=pw.temporal.tumbling(duration=timedelta(minutes=1))
)
```

**Key Concepts**:
- **Non-overlapping**: Each data point belongs to exactly one window
- **Time-based**: Windows based on `sent_at` timestamp
- **Aggregation**: Compute metrics over each window
- **Triggers**: New analysis when window closes

**Example Timeline**:
```
10:00:00 - 10:01:00 → Window 1 → Analysis 1
10:01:00 - 10:02:00 → Window 2 → Analysis 2
10:02:00 - 10:03:00 → Window 3 → Analysis 3
```

### Window Configuration

```python
# Market data: 1-minute windows (frequent updates)
market_window = timedelta(minutes=1)

# News/Sentiment: 5-minute windows (less frequent)
news_window = timedelta(minutes=5)
sentiment_window = timedelta(minutes=5)

# Fundamentals: No windowing (latest data only)
```

## 🗄️ Redis Caching

### Architecture

```python
# Pathway observer writes to Redis
observer = RedisReportObserver(report_type="market")
pw.io.python.write(table, observer)

# FastAPI reads from Redis
redis_client = get_redis_client()
reports = get_reports_for_symbol("AAPL", redis_client)
```

### Data Structure

```python
# Redis key structure
reports:symbols          → Set of all symbols
reports:AAPL            → Hash of report types for AAPL

# Hash contents
{
    "market": "{json}",
    "news": "{json}",
    "sentiment": "{json}",
    "fundamental": "{json}"
}

# Each report JSON
{
    "symbol": "AAPL",
    "report_type": "market",
    "content": "markdown content...",
    "last_updated": "2025-11-11T10:01:00",
    "received_at": "2025-11-11T10:01:05",
    "processing_time": 123456789
}
```

### Cache Invalidation

```python
# Optional TTL (expires after N seconds)
REDIS_REPORT_TTL=3600  # 1 hour

# Or no expiration (recommended for real-time updates)
# Reports continuously updated by Pathway streams
```

## 🌐 FastAPI Reports Server

### Endpoints

#### GET `/`
Root endpoint with API information

```bash
curl http://localhost:8000/
```

#### GET `/health`
Health check with cache statistics

```bash
curl http://localhost:8000/health

# Response
{
    "status": "ok",
    "timestamp": "2025-11-11T10:00:00Z",
    "cached_symbols": ["AAPL", "GOOGL", "MSFT"],
    "report_counts": {
        "market": 3,
        "news": 3,
        "sentiment": 2,
        "fundamental": 3
    }
}
```

#### GET `/symbols`
List all symbols with cached reports

```bash
curl http://localhost:8000/symbols

# Response
{
    "symbols": ["AAPL", "GOOGL", "MSFT", "TSLA"],
    "count": 4,
    "timestamp": "2025-11-11T10:00:00Z"
}
```

#### GET `/reports/{symbol}`
Get all reports for a symbol

```bash
curl http://localhost:8000/reports/AAPL

# Response
{
    "symbol": "AAPL",
    "fundamental_report": "markdown content...",
    "market_report": "markdown content...",
    "news_report": "markdown content...",
    "sentiment_report": "markdown content...",
    "timestamp": "2025-11-11T10:00:00Z",
    "status": "complete"
}
```

#### GET `/reports/{symbol}/{report_type}`
Get specific report type

```bash
curl http://localhost:8000/reports/AAPL/market

# Response
{
    "symbol": "AAPL",
    "report_type": "market",
    "content": "markdown content...",
    "last_updated": "2025-11-11T10:01:00Z",
    "timestamp": "2025-11-11T10:01:05Z"
}
```

### Response Codes

- `200 OK` - Report found
- `404 Not Found` - Symbol or report type not found
- `500 Internal Server Error` - Redis connection error

## 📝 Report Examples

### Market Report
```markdown
# AAPL Market Analysis

**Last Updated**: 2025-11-11 10:01:00

## Technical Overview
Current price: $178.50 (+1.2%)
The stock is showing bullish momentum with strong intraday gains.

## Price Action
- High: $179.20
- Low: $176.80
- Opening: $177.00
- Typical Price: $178.17

## Volatility
Intraday volatility: 1.36%
Moderate volatility suggests stable trading conditions.

## Key Levels
- Resistance: $180.00
- Support: $176.50

## Short-term Outlook
The upward trend is likely to continue if price holds above $177 support...
```

### News Report
```markdown
# AAPL News Summary

**Period**: 2025-11-11 09:55 - 10:00

## Executive Summary
Apple announced strong quarterly earnings, beating analyst expectations...

## Key Developments
1. Q4 earnings beat estimates by 15%
2. New product launch scheduled for next month
3. Expansion into emerging markets announced

## Market Implications
The positive earnings report is likely to drive continued investor interest...

## Sentiment Assessment
Overall media sentiment: Positive (8/10)
```

## 🔧 Configuration

### LLM Model Selection

```python
# In agent files (e.g., market_agent.py)
chat = llms.OpenAIChat(
    model="gpt-4o-mini",      # Model selection
    api_key=openai_api_key,
    temperature=0.0,          # Deterministic output
    cache_strategy=pw.udfs.DefaultCache()
)
```

**Available Models**:
- `gpt-4o-mini` - Fast, cost-effective
- `gpt-4o` - Most capable
- `gpt-4-turbo` - Balance of speed/quality
- `gpt-3.5-turbo` - Budget option

### Window Durations

```python
# Adjust in main_*.py files
window=pw.temporal.tumbling(
    duration=timedelta(minutes=5)  # Change duration
)
```

### Report Output

```python
# CSV output (optional)
pw.io.csv.write(table, "reports/market/stream.csv")

# File output per symbol (optional)
table.subscribe(lambda row: write_report_file(row))
```

## 🧪 Testing

### Test Individual Pipeline

```bash
# Start dependencies
docker-compose up kafka redis -d

# Run pipeline
python main_market.py

# Check logs for processing
# Expected: "✅ Market pipeline initialized"
```

### Verify Redis Cache

```bash
# Connect to Redis
docker exec -it redis redis-cli

# List symbols
SMEMBERS reports:symbols

# Get reports for symbol
HGETALL reports:AAPL

# Check specific report
HGET reports:AAPL market
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health | jq

# Get report
curl http://localhost:8000/reports/AAPL | jq .market_report
```

## 📈 Performance

### Throughput
- Market pipeline: ~60 analyses/hour (per symbol)
- News pipeline: ~12 analyses/hour
- Sentiment pipeline: ~12 analyses/hour
- Fundamentals: ~1 update/hour

### Latency
- Kafka → Pathway: <100ms
- Pathway → LLM: 2-5 seconds
- LLM → Redis: <50ms
- Redis → API: <10ms

### Resource Usage
- CPU: ~20-30% per pipeline
- Memory: ~500MB per pipeline
- Redis: ~10MB per 100 reports

## 🛡️ Error Handling

### Kafka Connection Issues
```python
# Automatic reconnection with backoff
rdkafka_settings = {
    "auto.offset.reset": "earliest",
    "enable.auto.commit": "true",
}
```

### LLM API Failures
```python
# Caching strategy prevents repeated calls
cache_strategy=pw.udfs.DefaultCache()

# Errors logged but don't crash pipeline
try:
    response = chat(messages)
except Exception as e:
    logger.error(f"LLM error: {e}")
    response = "Analysis unavailable"
```

### Redis Connection Failures
```python
# Graceful degradation
try:
    redis.set(key, value)
except redis.ConnectionError:
    logger.warning("Redis unavailable, report not cached")
    # Pipeline continues, just won't cache
```

## 🔗 Integration

### Consumed From
- [streaming/producers](../streaming/README.md) - Kafka topics

### Consumed By
- [trading_agents](../trading_agents/README.md) - FastAPI endpoints

## 📚 Dependencies

See `requirements.txt`:
- `pathway[xpack-llm-docs]` - Stream processing
- `openai` - LLM integration
- `redis` - Caching
- `fastapi` - API server
- `uvicorn` - ASGI server
- `langgraph` - Agent orchestration
- `langchain` - LLM utilities

## 🤝 Contributing

To add a new report type:

1. Create consumer in `consumers/`
2. Create agent in `agents/`
3. Create main entry point `main_new.py`
4. Update Redis observer
5. Add API endpoint
6. Update docker-compose.yml
