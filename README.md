# Real-Time AI Investment Assistant# Real-Time AI Investment Assistant



A sophisticated, real-time stock analysis and intelligence system built with microservices architecture, leveraging Pathway for stream processing, LangGraph for multi-agent reasoning, and Kafka for event streaming.A sophisticated, real-time stock analysis and intelligence system built with microservices architecture, leveraging Pathway for stream processing, LangGraph for multi-agent reasoning, and Kafka for event streaming.

Link to Frontend code: https://github.com/animeshsahoo1/WhiteBox-Frontend


## 🎯 Project Overview



This system combines real-time data streaming, AI-powered analysis, and multi-agent reasoning to provide comprehensive stock market intelligence. The architecture consists of four main layers:This system combines real-time data streaming, AI-powered analysis, and multi-agent reasoning to provide comprehensive stock market intelligence for retail traders, small hedge funds, and independent investors. The architecture consists of four main components:



1. **Streaming Layer** - Collects real-time market data from multiple sources1. **Streaming Layer** - Collects real-time market data from multiple sources

2. **Pathway Analysis Layer** - Processes streams and generates AI-powered reports2. **Pathway Analysis Layer** - Processes streams and generates AI-powered reports

3. **Bull-Bear Debate System** - Multi-agent debate for investment thesis generation3. **Backtesting Engine** - O(1) incremental strategy backtesting with real-time metrics

4. **Strategist Agent** - MCP-powered conversational agent with tools access4. **Intelligence Agents Layer** - Multi-agent system for investment analysis and hypothesis generation



## 🏗️ Architecture


```
┌─────────────────────────────────────────────────────────────────┐
│                      STREAMING PRODUCERS                        │
│        (Market, News, Sentiment, Fundamental, Candles)          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                          ┌─────────┐
                          │  KAFKA  │
                          └────┬────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
 ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
 │    PATHWAY    │     │    PATHWAY    │     │    PATHWAY    │
 │   AI AGENTS   │     │  BACKTESTER   │     │  UNIFIED API  │
 │   (Reports)   │     │     O(1)      │     │   (FastAPI)   │
 └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
                          ┌─────────┐
                          │  REDIS  │
                          │ (Cache) │
                          └────┬────┘
                               │
           ┌───────────────────┴───────────────────┐
           ▼                                       ▼
┌─────────────────────────┐             ┌─────────────────────────┐
│    BULL-BEAR DEBATE     │             │    STRATEGIST AGENT     │
│   (LangGraph + Mem0)    │             │  (MCP Server + Tools)   │
│   Asian Parliamentary   │             │    Backtesting, RAG,    │
│  Toulmin Argumentation  │             │    Risk Assessment      │
└──────────┬──────────────┘             └──────────┬──────────────┘
           │                                       │
           └───────────────────┬───────────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  WEBSOCKET  │
                        │   SERVER    │
                        └─────────────┘

```

### AI-Powered Analysis

## 📊 Key Features- **Pathway stream processing**: Real-time windowing and aggregation

- **LLM-based reports**: GPT-4 powered insights for each data category

### Real-Time Data Collection- **Technical indicators**: Moving averages, RSI, volatility metrics

- **Multi-source fallback**: Finnhub, Alpha Vantage, FMP, NewsAPI, Reddit, Twitter- **Sentiment analysis**: VADER and TextBlob for social media

- **Circuit breaker pattern**: Automatic failover on API failures- **Fundamental analysis**: Financial ratios, growth metrics, SEC filings

- **Rate limit handling**: Smart cooldown and retry mechanisms

- **5 data streams**: Market prices, news articles, social sentiment, fundamental data, OHLCV candles### Multi-Agent Intelligence System

- **Research Phase**: Bull vs Bear researcher debate (dynamic rounds)

### AI-Powered Analysis Agents- **Synthesis Phase**: Integrates research into investment hypotheses

- **Market Agent**: Technical analysis with LangGraph multi-agent workflow, TA-Lib indicators- **Risk Analysis**: Aggressive, Neutral, Conservative perspectives

- **News Agent**: Story clustering with centroid-based cosine similarity, LLM synthesis- **Risk Assessment**: Evaluates all inputs and provides risk analysis

- **Sentiment Agent**: Phase 1 (fast clustering + VADER) → Phase 2 (LLM reports)- **Hypothesis Generation**: Produces ranked investment hypotheses with supporting evidence and risk assessments

- **Fundamental Agent**: Agentic RAG with 10-K document retrieval

### O(1) Incremental Backtesting Engine

### Bull-Bear Debate System- **Real-time Processing**: Backtest strategies as candles stream in (no batch reprocessing)

- **Asian Parliamentary Format**: Bull opens, Bear responds, reversed order in final round- **T+1 Execution**: Proper signal timing - signal at bar close, execute at next bar open

- **Toulmin Argumentation Scoring**: Claims, Evidence, Warrants, Qualifiers, Rebuttals- **Multiple Strategies**: Run 7+ strategies simultaneously

- **Mem0 Memory**: Persistent memory for debate context- **Comprehensive Metrics**: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor

- **RAG Integration**: Evidence retrieval from knowledge base- **LLM Strategy Generation**: Natural language to trading strategy via API

- **Delta Detection**: Analyzes report changes between sessions- **Semantic Search**: Find similar strategies using embeddings



### Strategist Agent (MCP Server)### Production Features

- **Model Context Protocol**: Exposes tools via FastMCP- **Redis caching**: Fast report retrieval and job queuing

- **Tools Available**:- **MongoDB checkpointing**: LangGraph state persistence

  - Risk Assessment (3-tier: no-risk, neutral, aggressive)- **Docker orchestration**: Complete containerized deployment

  - Backtesting API (list, search, create, compare strategies)- **Health monitoring**: Built-in health checks and status endpoints

  - Web Search (query decomposition + DuckDuckGo)- **Graceful shutdown**: Clean resource cleanup

  - Reports (facilitator conclusions, debate summaries)

- **Mem0 Memory**: User preferences and past interactions## 🚀 Quick Start

- **LangGraph ReAct**: Multi-turn conversation with tool calling

### Prerequisites

### O(1) Incremental Backtesting Engine- Docker & Docker Compose

- **Real-time Processing**: Backtest strategies as candles stream in- API Keys:

- **T+1 Execution**: Signal at bar close, execute at next bar open  - OpenAI API Key (for LLM analysis)

- **Multiple Strategies**: Run strategies simultaneously with natural join on interval  - Finnhub, Alpha Vantage, or FMP (market data)

- **Comprehensive Metrics**: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor  - NewsAPI (news data)

- **LLM Strategy Generation**: Natural language to trading strategy  - Reddit/Twitter APIs (optional, for social sentiment)

- **Semantic Search**: Find similar strategies using embeddings

### Environment Setup

### RAG System

- **Pathway DocumentStore**: Vector store with BruteForce KNNCreate `.env` files in each service directory:

- **Contextual Enrichment**: Gemini-powered chunk context injection

- **Cohere Reranking**: Over-retrieve then rerank for precision**streaming/.env**

- **Agentic RAG**: ReAct loop with self-reflection```bash

# Market Data

Here is the properly formatted and detangled "Quick Start" section for your documentation. I separated the markdown text from the `.env` file contents so it is easy for users to copy and paste.

## 🚀 Quick Start

### Prerequisites

* Docker & Docker Compose
* **API Keys:**
* OpenRouter API Key (for LLM analysis) *or* OpenAI API Key
* Finnhub, Alpha Vantage, or FMP (for market data)
* NewsAPI (for news data)
* Reddit/Twitter APIs (optional, for social sentiment)



### Environment Setup

Create the required `.env` files in your project directories.

**1. Root Directory (`.env`)**

```env
# LLM API
OPENROUTER_API_KEY=your_openrouter_key
# OR
OPENAI_API_KEY=your_openai_key

# Market Data (at least one)
FINNHUB_API_KEY=your_finnhub_key
ALPHA_VANTAGE_API_KEY=your_av_key
FMP_API_KEY=your_fmp_key

# News
NEWSAPI_API_KEY=your_newsapi_key

# Social Media (optional)
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
TWITTER_BEARER_TOKEN=your_twitter_token

# Configuration
STOCKS=AAPL,GOOGL,MSFT,TSLA,NVDA
MARKET_DATA_INTERVAL=60
NEWS_FETCH_INTERVAL=300

# Redis (optional - uses local if not set)
REDIS_URL=rediss://...  # Upstash Redis URL

# Pathway License (optional)
PATHWAY_LICENSE_KEY=your_license_key

```

**2. Pathway Directory (`pathway/.env`)**

```env
OPENAI_API_KEY=your_openai_key
KAFKA_BROKER=kafka:29092
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

```

**3. Trading Agents Directory (`trading_agents/.env`)**

```env
OPENAI_API_KEY=your_openai_key
PATHWAY_API_URL=http://pathway-unified-api:8000
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

```

---


### Launch the Systemdocker-compose logs -f



```bash# Check service health

# Start all services (from backend directory)curl http://localhost:8000/health  # Pathway Reports API

docker compose up -dcurl http://localhost:8001/health  # Trading Agents API

```

### Services & Ports

```bash
# View logs
docker compose logs -f

# Check service health
curl http://localhost:8000/health  # Unified API
curl http://localhost:8080/health  # WebSocket Server

```

| Service | Port | Description |
| --- | --- | --- |
| Unified API (Pathway Reports) | 8000 | AI-generated analysis reports, Backtesting API, RAG, Bull-Bear, Strategist |
| Intelligence Agents API | 8001 | Investment analysis workflow execution |
| WebSocket Server | 8080 | Real-time event streaming to frontend |
| MCP Server | 9004 | Model Context Protocol tools server |
| Kafka | 9092 | Message streaming (internal: 29092) |
| Redis | 6379 | Caching, pub/sub, vector store & job queue |
| Zookeeper | 2181 | Kafka coordination |

---

## 📁 Project Structure

```text
backend/
│
├── streaming/               # Data collection producers
│   ├── producers/           # Kafka producers for each data type
│   │   ├── base_producer.py           # Circuit breaker + multi-source fallback
│   │   ├── market_data_producer.py
│   │   ├── news_producer.py
│   │   ├── sentiment_producer.py
│   │   ├── fundamental_data_producer.py
│   │   └── candle_producer.py         # OHLCV candle data for backtesting
│   ├── webhook_receiver.py            # Twitter webhook endpoint
│   ├── data/                          # CSV data files (candles.csv)
│   ├── fundamental_utils/             # FMP API client & web scraping
│   └── utils/                         # Kafka utilities
│
├── pathway/                 # Stream processing & AI analysis
│   ├── consumers/           # Kafka consumers (Pathway tables)
│   │   ├── base_consumer.py
│   │   ├── market_data_consumer.py
│   │   ├── news_consumer.py
│   │   ├── sentiment_consumer.py
│   │   └── candle_consumer.py
│   ├── agents/              # LLM analysis agents
│   │   ├── market_agent2.py           # LangGraph + TA-Lib technical analysis
│   │   ├── news_agent.py              # Story clustering + synthesis
│   │   ├── sentiment_clustering.py    # Phase 1: Fast VADER clustering
│   │   ├── sentiment_reports.py       # Phase 2: LLM report generation
│   │   └── fundamental_agent.py       # Agentic RAG reports
│   ├── backtesting_lib/     # O(1) Incremental Backtesting Engine
│   │   ├── trading_state.py           # Core trading logic (T+1 execution)
│   │   ├── indicators.py              # Technical indicators
│   │   ├── metrics.py                 # Performance metrics
│   │   └── reducers.py                # Pathway reducers
│   ├── api/                 # FastAPI server for reports
│   │   ├── fastapi_server.py          # Main server
│   │   ├── rag_api.py                 # RAG + MCP endpoints
│   │   ├── bullbear_api.py            # Debate endpoints
│   │   ├── backtesting_api.py         # Strategy management
│   │   ├── sentiment_api.py           # Sentiment clusters
│   │   └── chat_api.py                # Strategist chat
│   ├── bullbear/            # Bull-Bear Debate System
│   │   ├── graph.py                   # LangGraph workflow
│   │   ├── nodes.py                   # Debate nodes (Bull, Bear, Facilitator)
│   │   ├── state.py                   # DebateState, DebatePoint types
│   │   ├── debate_runner.py           # Orchestrates debate execution
│   │   ├── cache_manager.py           # Delta detection for reports
│   │   ├── memory_manager.py          # Mem0 integration
│   │   └── llm_utils.py               # Prompts and LLM client
│   ├── orchestrator/        # Strategist Agent + MCP Server
│   │   ├── server.py                  # FastMCP server entry point
│   │   ├── langgraph_agent.py         # ReAct agent with Mem0
│   │   ├── tools/                     # MCP tool implementations
│   │   │   ├── risk_tools.py          # 3-tier risk assessment
│   │   │   ├── backtesting_tools.py
│   │   │   ├── search_tools.py        # Web search
│   │   │   └── report_tools.py
│   │   └── web_search.py              # DuckDuckGo integration
│   ├── strategies/          # Trading strategy files (.txt)
│   ├── reports/             # Generated AI reports
│   ├── knowledge_base/      # SEC 10-K documents for RAG
│   └── main_*.py            # Pipeline entry points
│
├── trading_agents/          # Multi-agent intelligence system
│   ├── all_agents/          # Agent implementations
│   │   ├── researchers/     # Bull/Bear researchers
│   │   ├── risk_mngt/       # Risk analysis agents
│   │   ├── managers/        # Risk & Hypothesis managers
│   │   └── trader/          # Synthesis agent
│   ├── graph/               # LangGraph workflow setup
│   ├── redis_queue/         # Job queue system
│   ├── api/                 # Intelligence API endpoints
│   └── utils/               # Helper utilities
│
├── websocket/               # Real-time event server
│   ├── main.py              # FastAPI WebSocket server
│   └── app/
│       ├── websocket_manager.py
│       ├── event_publisher.py
│       └── redis_util.py
│
├── validation/              # Evaluation frameworks
│   ├── RAGAS/               # RAG evaluation with FinQABench
│   ├── galileo_eval/        # Agent tool selection evaluation
│   └── backtesting_validation/ # Strategy validation vs backtesting.py
│
├── kafka/                   # Kafka standalone config (optional)
└── docker-compose.yml       # Root orchestration (includes all services)

```

## 🔄 Data Flow

### 1. Data Collection (Streaming)

```text
External APIs → Producers → Kafka Topics

```

* Producers fetch data every N seconds (configurable)
* Multi-source fallback ensures reliability
* Data published to topic-specific Kafka queues

### 2. Real-Time Analysis (Pathway)

```text
Kafka → Pathway Consumers → LLM Analysis → Redis Cache

```

* Pathway subscribes to Kafka topics
* Applies windowing (1-minute tumbling windows)
* LLM generates comprehensive reports
* Results cached in Redis with pub/sub

### 3. Report Distribution (Pathway API)

```text
Redis Cache → FastAPI → HTTP Endpoints

```

* FastAPI serves cached reports on-demand
* Eliminates need to re-run analysis
* Sub-millisecond response times

### 4. Investment Intelligence (Intelligence Agents)

```text
User Request → Fetch Reports → Multi-Agent Workflow → Ranked Hypotheses

```

* Retrieves latest reports from Pathway API
* LangGraph orchestrates multi-agent debate and analysis
* MongoDB stores conversation checkpoints
* Outputs ranked investment hypotheses with risk assessments

### 5. Backtesting (O(1) Incremental)

```text
Candle Producer → Kafka → Pathway Backtester → Redis Metrics

```

* Stream candles in real-time from CSV or live data
* O(1) per-candle processing (no batch recomputation)
* Multiple strategies evaluated simultaneously
* Metrics cached in Redis for instant retrieval

---

```bash

## 🔄 Data Flow# Get all reports for a symbol

curl http://localhost:8000/reports/AAPL

### 1. Data Collection (Streaming)

```# Get specific report type

External APIs → Producers (circuit breaker) → Kafka Topicscurl http://localhost:8000/reports/AAPL/market

```curl http://localhost:8000/reports/AAPL/sentiment

curl http://localhost:8000/reports/AAPL/news

### 2. Real-Time Analysis (Pathway)curl http://localhost:8000/reports/AAPL/fundamental

```

Kafka → Pathway Consumers → Windowing → AI Agents → Redis Cache# List available symbols

```
curl http://localhost:8000/symbols

```

### 3. Bull-Bear Debate

```### Backtesting API

Reports (Redis) → Delta Detection → Bull/Bear Arguments → Facilitator Conclusion

``````bash

# List all strategies with metrics

### 4. Strategist Agentcurl http://localhost:8000/api/backtesting/strategies

```

User Query → MCP Tools → Risk/Backtest/Search/Reports → Response# Get specific strategy metrics

```curl http://localhost:8000/api/backtesting/strategy/sma_crossover



### 5. WebSocket Distribution# Create new strategy (with LLM generation)

```curl -X POST http://localhost:8000/api/backtesting/strategy \

Redis Pub/Sub → WebSocket Server → Frontend Clients  -H "Content-Type: application/json" \

```  -d '{"description": "RSI oversold bounce strategy with 30/70 levels"}'



## 🎛️ API Usage# Search strategies by natural language

curl -X POST http://localhost:8000/api/backtesting/query \

### Get Stock Reports  -H "Content-Type: application/json" \

  -d '{"query": "momentum strategies with stop loss"}'

```bash```

# Get all reports for a symbol

curl http://localhost:8000/reports/AAPL### Execute Intelligence Workflow (Intelligence Agents API)



# Get specific report type```bash

curl http://localhost:8000/reports/AAPL/market# Trigger investment analysis for a symbol

curl http://localhost:8000/reports/AAPL/sentimentcurl -X POST http://localhost:8001/execute/AAPL

curl http://localhost:8000/reports/AAPL/news

curl http://localhost:8000/reports/AAPL/fundamental# Check job status

```curl http://localhost:8001/job/{job_id}



### Bull-Bear Debate# Get latest investment hypotheses

curl http://localhost:8001/hypotheses/AAPL

```bash

# Start debate for a symbol# Get agent reports

curl -X POST http://localhost:8000/bullbear/debate \curl http://localhost:8001/reports/AAPL/all

  -H "Content-Type: application/json" \```

  -d '{"symbol": "AAPL", "max_rounds": 3}'

## 🧪 Development

# Get debate status

curl http://localhost:8000/bullbear/status/AAPL### Running Individual Services

```

```bash

### Strategist Chat# Run streaming producers only

cd streaming

```bashdocker-compose up

# Chat with strategist

curl -X POST http://localhost:8000/strategist/chat \# Run pathway consumers only

  -H "Content-Type: application/json" \cd pathway

  -d '{"message": "What strategies perform best?", "user_id": "user123"}'docker-compose up



# Streaming response# Run trading agents only

curl -X POST http://localhost:8000/strategist/chat/stream \cd trading_agents

  -H "Content-Type: application/json" \docker-compose up

  -d '{"message": "Analyze AAPL risk", "user_id": "user123"}'```

```

### Local Development (without Docker)

### Backtesting API

```bash

```bash# Install dependencies for each service

# List all strategies with metricscd streaming && pip install -r requirements.txt

curl http://localhost:8000/backtesting/strategiescd pathway && pip install -r requirements.txt

cd trading_agents && pip install -r requirements.txt

# Create new strategy from natural language

curl -X POST http://localhost:8000/backtesting/strategies \# Start Kafka & Redis locally (or use Docker)

  -H "Content-Type: application/json" \docker-compose up kafka redis zookeeper

  -d '{"description": "RSI oversold bounce with 30/70 levels"}'

# Run services

# Search strategies semanticallypython streaming/producers/market_data_producer.py

curl -X POST http://localhost:8000/backtesting/strategies/search \python pathway/main_market.py

  -H "Content-Type: application/json" \python trading_agents/run_workflow.py

  -d '{"query": "momentum strategies with stop loss"}'```

```

## 🎛️ API Usage

### RAG Queries

Query the knowledge base using the RAG pipeline.

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Apple revenue for 2024?", "symbol": "AAPL"}'

```

### Get Stock Reports (Pathway API)

```bash
curl http://localhost:8000/reports/AAPL/market

```

---

## 📈 Monitoring & Logs

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific services
docker-compose logs -f unified-api
docker-compose logs -f market-consumer
docker-compose logs -f intelligence-agents-worker

```

### Health Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8080/health

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
docker exec -it pathway-redis redis-cli

# View cached symbols
SMEMBERS reports:symbols

# View report for symbol
HGETALL reports:AAPL

# View sentiment clusters
GET sentiment_clusters:AAPL

```

---

## 🧪 Development

### Running Individual Services

```bash
# Start Kafka first (creates network)
cd kafka && docker compose up -d

# Start streaming producers
cd streaming && docker compose up -d

# Start pathway consumers & API
cd pathway && docker compose up -d

# Start websocket server
cd websocket && docker compose up -d

```

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r pathway/requirements.txt
pip install -r streaming/requirements.txt

# Start Kafka & Redis via Docker
docker compose up kafka redis zookeeper -d

# Run services locally
python streaming/producers/market_data_producer.py
python pathway/main_market.py
uvicorn pathway.api.fastapi_server:app --reload --port 8000

```

---

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

```bash
OPENAI_MODEL=openai/gpt-4o-mini  # Model for OpenRouter
OPENAI_MODEL_AGENT=openai/gpt-4o-mini  # Model for Strategist

```

*To edit directly in the agent files:*

```python
# pathway/agents/market_agent.py
chat = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.0)

# trading_agents/all_agents/utils/llm.py
chat_model = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.7)

```

The system includes comprehensive error handling:

* **Circuit breakers** for API failures
* **Graceful degradation** with fallback data sources
* **Automatic retries** with exponential backoff
* **Rate limit detection** and cooldown periods
* **Health checks** for all services

---

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

---

## 📝 Validation Results

### RAGAS Evaluation (RAG System)

| Method | Precision | Recall | Faithfulness | Relevancy | Factuality |
| --- | --- | --- | --- | --- | --- |
| Baseline | 0.722 | 0.827 | 0.777 | 0.791 | 0.399 |
| **Ours (Reranking + Context)** | **0.875** | **0.896** | **0.846** | **0.844** | **0.455** |
| <br>Source: WhiteBox Pathway End Report 

 |  |  |  |  |  |

### Backtesting Validation

* ✅ 7/7 metrics match for SMA Crossover strategy 


* ✅ Equity-curve based Sharpe ratio (industry standard)
* ✅ Proper T+1 execution timing

### Agent Evaluation (Galileo)

* 64 test queries across 27 MCP tools 


* Tool selection accuracy: 88.3% 



---

## 🤝 Contributing

Each subdirectory contains its own detailed README:

* [streaming/README.md](https://www.google.com/search?q=streaming/README.md) - Data collection layer
* [pathway/README.md](https://www.google.com/search?q=pathway/README.md) - Stream processing layer
* [trading_agents/README.md](https://www.google.com/search?q=trading_agents/README.md) - Intelligence and analysis layer

## 📚 Documentation

* [Streaming Layer](https://www.google.com/search?q=streaming/README.md) - Data collection producers
* [Pathway Layer](https://www.google.com/search?q=pathway/README.md) - Stream processing & AI agents
* [WebSocket Server](https://www.google.com/search?q=websocket/readme.md) - Real-time event distribution
* [WebSocket Event Schemas](https://www.google.com/search?q=WEBSOCKET_EVENT_SCHEMAS.md) - Event type reference
* [Quick Start Guide](QUICKSTART.md) - Detailed setup instructions

## 📄 License

This project is part of the Pathway InterIIT initiative.

## 🙏 Acknowledgments

* **Pathway** - Real-time data processing framework
* **LangGraph** - Multi-agent orchestration
* **FastMCP** - Model Context Protocol server
* **Mem0** - Persistent memory for AI agents
* **OpenRouter** - LLM API gateway
* **Kafka** - Distributed streaming platform
* **OpenAI** - Language model APIs

---

