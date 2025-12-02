# Real-Time AI Investment Assistant

A sophisticated, real-time stock analysis and intelligence system built with microservices architecture, leveraging Pathway for stream processing, LangGraph for multi-agent reasoning, and Kafka for event streaming.

## 🎯 Project Overview

This system combines real-time data streaming, AI-powered analysis, and multi-agent reasoning to provide comprehensive stock market intelligence for retail traders, small hedge funds, and independent investors. The architecture consists of four main components:

1. **Streaming Layer** - Collects real-time market data from multiple sources
2. **Pathway Analysis Layer** - Processes streams and generates AI-powered reports
3. **Backtesting Engine** - O(1) incremental strategy backtesting with real-time metrics
4. **Intelligence Agents Layer** - Multi-agent system for investment analysis and hypothesis generation

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STREAMING PRODUCERS                           │
│  (Market, News, Sentiment, Fundamental, Candles)                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
                  ┌─────────┐
                  │  KAFKA  │
                  └────┬────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌───────────────┐ ┌─────────────┐ ┌─────────────────┐
│   PATHWAY     │ │  PATHWAY    │ │   PATHWAY       │
│  CONSUMERS    │ │ BACKTESTER  │ │   REPORTS API   │
│  (AI Reports) │ │  O(1)       │ │   (FastAPI)     │
└───────┬───────┘ └──────┬──────┘ └────────┬────────┘
        │                │                  │
        └────────────────┼──────────────────┘
                         │
                         ▼
                    ┌─────────┐
                    │  REDIS  │
                    │ (Cache) │
                    └────┬────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│       INTELLIGENCE AGENTS (LangGraph Multi-Agent)                │
│  (Bull/Bear Debate → Hypothesis Generation → Risk Assessment)    │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Key Features

### Real-Time Data Collection
- **Multi-source fallback**: Finnhub, Alpha Vantage, FMP, NewsAPI, Reddit, Twitter
- **Circuit breaker pattern**: Automatic failover on API failures
- **Rate limit handling**: Smart cooldown and retry mechanisms
- **4 data streams**: Market prices, news articles, social sentiment, fundamental data

### AI-Powered Analysis
- **Pathway stream processing**: Real-time windowing and aggregation
- **LLM-based reports**: GPT-4 powered insights for each data category
- **Technical indicators**: Moving averages, RSI, volatility metrics
- **Sentiment analysis**: VADER and TextBlob for social media
- **Fundamental analysis**: Financial ratios, growth metrics, SEC filings

### Multi-Agent Intelligence System
- **Research Phase**: Bull vs Bear researcher debate (dynamic rounds)
- **Synthesis Phase**: Integrates research into investment hypotheses
- **Risk Analysis**: Aggressive, Neutral, Conservative perspectives
- **Risk Assessment**: Evaluates all inputs and provides risk analysis
- **Hypothesis Generation**: Produces ranked investment hypotheses with supporting evidence and risk assessments

### O(1) Incremental Backtesting Engine
- **Real-time Processing**: Backtest strategies as candles stream in (no batch reprocessing)
- **T+1 Execution**: Proper signal timing - signal at bar close, execute at next bar open
- **Multiple Strategies**: Run 7+ strategies simultaneously
- **Comprehensive Metrics**: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
- **LLM Strategy Generation**: Natural language to trading strategy via API
- **Semantic Search**: Find similar strategies using embeddings

### Production Features
- **Redis caching**: Fast report retrieval and job queuing
- **MongoDB checkpointing**: LangGraph state persistence
- **Docker orchestration**: Complete containerized deployment
- **Health monitoring**: Built-in health checks and status endpoints
- **Graceful shutdown**: Clean resource cleanup

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- API Keys:
  - OpenAI API Key (for LLM analysis)
  - Finnhub, Alpha Vantage, or FMP (market data)
  - NewsAPI (news data)
  - Reddit/Twitter APIs (optional, for social sentiment)

### Environment Setup

Create `.env` files in each service directory:

**streaming/.env**
```bash
# Market Data
FINNHUB_API_KEY=your_finnhub_key
ALPHA_VANTAGE_API_KEY=your_av_key
FMP_API_KEY=your_fmp_key

# News
NEWSAPI_API_KEY=your_newsapi_key

# Social Media
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
TWITTER_BEARER_TOKEN=your_twitter_token

# Configuration
STOCKS=AAPL,GOOGL,MSFT,TSLA
MARKET_DATA_INTERVAL=60
NEWS_FETCH_INTERVAL=300
```

**pathway/.env**
```bash
OPENAI_API_KEY=your_openai_key
KAFKA_BROKER=kafka:29092
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

**trading_agents/.env**
```bash
OPENAI_API_KEY=your_openai_key
PATHWAY_API_URL=http://pathway-reports-api:8000
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1
MONGODB_URI=mongodb://mongo:27017
DATABASE_URL=postgresql://user:pass@postgres:5432/intelligence_db
```

### Launch the System

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
curl http://localhost:8000/health  # Pathway Reports API
curl http://localhost:8001/health  # Trading Agents API
```

### Services & Ports

| Service | Port | Description |
|---------|------|-------------|
| Pathway Reports API | 8000 | AI-generated analysis reports + Backtesting API |
| Intelligence Agents API | 8001 | Investment analysis workflow execution |
| Kafka | 9092 | Message streaming |
| Redis | 6379 | Caching & job queue |
| Zookeeper | 2181 | Kafka coordination |

## 📁 Project Structure

```
.
├── streaming/              # Data collection producers
│   ├── producers/          # Kafka producers for each data type
│   │   ├── candle_producer.py  # OHLCV candle data for backtesting
│   │   └── ...
│   ├── data/              # CSV data files (candles.csv)
│   ├── fundamental_utils/  # FMP API client & web scraping
│   └── utils/             # Kafka utilities
│
├── pathway/               # Stream processing & AI analysis
│   ├── consumers/         # Kafka consumers (Pathway tables)
│   │   ├── candle_consumer.py  # Candle data consumer for backtesting
│   │   └── ...
│   ├── agents/            # LLM analysis agents
│   ├── backtesting_lib/   # O(1) Incremental Backtesting Engine
│   │   ├── trading_state.py    # Core trading logic (T+1 execution)
│   │   ├── indicators.py       # Technical indicators
│   │   ├── metrics.py          # Performance metrics
│   │   └── reducers.py         # Pathway reducers
│   ├── strategies/        # Trading strategy files (.txt)
│   ├── api/               # FastAPI server for reports
│   │   ├── backtesting_api.py  # Backtesting endpoints
│   │   └── ...
│   └── reports/           # Generated analysis reports
│
├── trading_agents/        # Multi-agent intelligence system
│   ├── all_agents/        # Agent implementations
│   │   ├── researchers/   # Bull/Bear researchers
│   │   ├── risk_mngt/     # Risk analysis agents
│   │   ├── managers/      # Risk & Hypothesis managers
│   │   └── trader/        # Synthesis agent
│   ├── graph/             # LangGraph workflow setup
│   ├── redis_queue/       # Job queue system
│   ├── api/               # Intelligence API endpoints
│   └── utils/             # Helper utilities
│
└── kafka/                 # Kafka standalone config (optional)
```

## 🔄 Data Flow

### 1. Data Collection (Streaming)
```
External APIs → Producers → Kafka Topics
```
- Producers fetch data every N seconds (configurable)
- Multi-source fallback ensures reliability
- Data published to topic-specific Kafka queues

### 2. Real-Time Analysis (Pathway)
```
Kafka → Pathway Consumers → LLM Analysis → Redis Cache
```
- Pathway subscribes to Kafka topics
- Applies windowing (1-minute tumbling windows)
- LLM generates comprehensive reports
- Results cached in Redis with pub/sub

### 3. Report Distribution (Pathway API)
```
Redis Cache → FastAPI → HTTP Endpoints
```
- FastAPI serves cached reports on-demand
- Eliminates need to re-run analysis
- Sub-millisecond response times

### 4. Investment Intelligence (Intelligence Agents)
```
User Request → Fetch Reports → Multi-Agent Workflow → Ranked Hypotheses
```
- Retrieves latest reports from Pathway API
- LangGraph orchestrates multi-agent debate and analysis
- MongoDB stores conversation checkpoints
- Outputs ranked investment hypotheses with risk assessments

### 5. Backtesting (O(1) Incremental)
```
Candle Producer → Kafka → Pathway Backtester → Redis Metrics
```
- Stream candles in real-time from CSV or live data
- O(1) per-candle processing (no batch recomputation)
- Multiple strategies evaluated simultaneously
- Metrics cached in Redis for instant retrieval

## 🎛️ API Usage

### Get Stock Reports (Pathway API)

```bash
# Get all reports for a symbol
curl http://localhost:8000/reports/AAPL

# Get specific report type
curl http://localhost:8000/reports/AAPL/market
curl http://localhost:8000/reports/AAPL/sentiment
curl http://localhost:8000/reports/AAPL/news
curl http://localhost:8000/reports/AAPL/fundamental

# List available symbols
curl http://localhost:8000/symbols
```

### Backtesting API

```bash
# List all strategies with metrics
curl http://localhost:8000/api/backtesting/strategies

# Get specific strategy metrics
curl http://localhost:8000/api/backtesting/strategy/sma_crossover

# Create new strategy (with LLM generation)
curl -X POST http://localhost:8000/api/backtesting/strategy \
  -H "Content-Type: application/json" \
  -d '{"description": "RSI oversold bounce strategy with 30/70 levels"}'

# Search strategies by natural language
curl -X POST http://localhost:8000/api/backtesting/query \
  -H "Content-Type: application/json" \
  -d '{"query": "momentum strategies with stop loss"}'
```

### Execute Intelligence Workflow (Intelligence Agents API)

```bash
# Trigger investment analysis for a symbol
curl -X POST http://localhost:8001/execute/AAPL

# Check job status
curl http://localhost:8001/job/{job_id}

# Get latest investment hypotheses
curl http://localhost:8001/hypotheses/AAPL

# Get agent reports
curl http://localhost:8001/reports/AAPL/all
```

## 🧪 Development

### Running Individual Services

```bash
# Run streaming producers only
cd streaming
docker-compose up

# Run pathway consumers only
cd pathway
docker-compose up

# Run trading agents only
cd trading_agents
docker-compose up
```

### Local Development (without Docker)

```bash
# Install dependencies for each service
cd streaming && pip install -r requirements.txt
cd pathway && pip install -r requirements.txt
cd trading_agents && pip install -r requirements.txt

# Start Kafka & Redis locally (or use Docker)
docker-compose up kafka redis zookeeper

# Run services
python streaming/producers/market_data_producer.py
python pathway/main_market.py
python trading_agents/run_workflow.py
```

## 📈 Monitoring & Logs

### View Service Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f market-consumer
docker-compose logs -f intelligence-agents-worker
```

### Check Reports
```bash
# View generated reports
ls -la pathway/reports/market/
ls -la pathway/reports/news/
ls -la pathway/reports/sentiment/
ls -la pathway/reports/fundamental/
```

### Redis Monitoring
```bash
# Connect to Redis CLI
docker exec -it redis redis-cli

# View cached symbols
SMEMBERS reports:symbols

# View report for symbol
HGETALL reports:AAPL
```

## 🔧 Configuration

### Stock Symbols
Configure which stocks to track in `streaming/.env`:
```bash
STOCKS=AAPL,GOOGL,MSFT,TSLA,AMZN,NVDA
```

### Fetch Intervals
```bash
MARKET_DATA_INTERVAL=60        # Market data every 60 seconds
NEWS_FETCH_INTERVAL=300        # News every 5 minutes
SENTIMENT_FETCH_INTERVAL=300   # Sentiment every 5 minutes
FUNDAMENTAL_INTERVAL=3600      # Fundamentals every hour
```

### LLM Models
Edit in respective agent files:
```python
# pathway/agents/market_agent.py
chat = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.0)

# trading_agents/all_agents/utils/llm.py
chat_model = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.7)
```

## 🛡️ Error Handling

The system includes comprehensive error handling:
- **Circuit breakers** for API failures
- **Graceful degradation** with fallback data sources
- **Automatic retries** with exponential backoff
- **Rate limit detection** and cooldown periods
- **Health checks** for all services

## 📝 Output Format

### Investment Hypothesis Example
```json
{
  "symbol": "AAPL",
  "hypothesis": "Strong bullish case based on positive earnings and technical strength",
  "evidence": {
    "bull_points": ["Revenue growth exceeds expectations", "Positive market sentiment"],
    "bear_points": ["High valuation concerns", "Competitive pressure"],
    "synthesis": "Balance of evidence suggests growth potential despite risks"
  },
  "risk_assessment": {
    "aggressive": "High conviction entry opportunity",
    "neutral": "Moderate position with defined risk",
    "conservative": "Wait for better entry or reduced position"
  },
  "confidence": 0.78,
  "timestamp": "2025-11-11T10:30:00Z"
}
```

## 🤝 Contributing

Each subdirectory contains its own detailed README:
- [streaming/README.md](streaming/README.md) - Data collection layer
- [pathway/README.md](pathway/README.md) - Stream processing layer
- [trading_agents/README.md](trading_agents/README.md) - Intelligence and analysis layer

## 📄 License

This project is part of the Pathway InterIIT initiative.

## 🙏 Acknowledgments

- **Pathway** - Real-time data processing framework
- **LangGraph** - Multi-agent orchestration
- **OpenAI** - Language model APIs
- **Kafka** - Distributed streaming platform
