# Real-Time AI Investment Assistant# Real-Time AI Investment Assistant



A sophisticated, real-time stock analysis and intelligence system built with microservices architecture, leveraging Pathway for stream processing, LangGraph for multi-agent reasoning, and Kafka for event streaming.A sophisticated, real-time stock analysis and intelligence system built with microservices architecture, leveraging Pathway for stream processing, LangGraph for multi-agent reasoning, and Kafka for event streaming.



## 🎯 Project Overview## 🎯 Project Overview



This system combines real-time data streaming, AI-powered analysis, and multi-agent reasoning to provide comprehensive stock market intelligence. The architecture consists of four main layers:This system combines real-time data streaming, AI-powered analysis, and multi-agent reasoning to provide comprehensive stock market intelligence for retail traders, small hedge funds, and independent investors. The architecture consists of four main components:



1. **Streaming Layer** - Collects real-time market data from multiple sources1. **Streaming Layer** - Collects real-time market data from multiple sources

2. **Pathway Analysis Layer** - Processes streams and generates AI-powered reports2. **Pathway Analysis Layer** - Processes streams and generates AI-powered reports

3. **Bull-Bear Debate System** - Multi-agent debate for investment thesis generation3. **Backtesting Engine** - O(1) incremental strategy backtesting with real-time metrics

4. **Strategist Agent** - MCP-powered conversational agent with tools access4. **Intelligence Agents Layer** - Multi-agent system for investment analysis and hypothesis generation



## 🏗️ Architecture## 🏗️ Architecture



``````

┌─────────────────────────────────────────────────────────────────┐┌─────────────────────────────────────────────────────────────────┐

│                    STREAMING PRODUCERS                           ││                    STREAMING PRODUCERS                           │

│  (Market, News, Sentiment, Fundamental, Candles)                 ││  (Market, News, Sentiment, Fundamental, Candles)                 │

└──────────────────────┬──────────────────────────────────────────┘└──────────────────────┬──────────────────────────────────────────┘

                       │                       │

                       ▼                       ▼

                  ┌─────────┐                  ┌─────────┐

                  │  KAFKA  │                  │  KAFKA  │

                  └────┬────┘                  └────┬────┘

                       │                       │

        ┌──────────────┼──────────────┐        ┌──────────────┼──────────────┐

        │              │              │        │              │              │

        ▼              ▼              ▼        ▼              ▼              ▼

┌───────────────┐ ┌─────────────┐ ┌─────────────────┐┌───────────────┐ ┌─────────────┐ ┌─────────────────┐

│   PATHWAY     │ │  PATHWAY    │ │   PATHWAY       ││   PATHWAY     │ │  PATHWAY    │ │   PATHWAY       │

│  AI AGENTS    │ │ BACKTESTER  │ │   UNIFIED API   ││  CONSUMERS    │ │ BACKTESTER  │ │   REPORTS API   │

│  (Reports)    │ │  O(1)       │ │   (FastAPI)     ││  (AI Reports) │ │  O(1)       │ │   (FastAPI)     │

└───────┬───────┘ └──────┬──────┘ └────────┬────────┘└───────┬───────┘ └──────┬──────┘ └────────┬────────┘

        │                │                  │        │                │                  │

        └────────────────┼──────────────────┘        └────────────────┼──────────────────┘

                         │                         │

                         ▼                         ▼

                    ┌─────────┐                    ┌─────────┐

                    │  REDIS  │                    │  REDIS  │

                    │ (Cache) │                    │ (Cache) │

                    └────┬────┘                    └────┬────┘

                         │                         │

        ┌────────────────┼────────────────┐                         ▼

        ▼                                 ▼┌─────────────────────────────────────────────────────────────────┐

┌─────────────────────────┐    ┌─────────────────────────┐│       INTELLIGENCE AGENTS (LangGraph Multi-Agent)                │

│     BULL-BEAR DEBATE    │    │   STRATEGIST AGENT      ││  (Bull/Bear Debate → Hypothesis Generation → Risk Assessment)    │

│  (LangGraph + Mem0)     │    │  (MCP Server + Tools)   │└─────────────────────────────────────────────────────────────────┘

│  Asian Parliamentary    │    │  Backtesting, RAG,      │```

│  Toulmin Argumentation  │    │  Risk Assessment        │

└─────────────────────────┘    └─────────────────────────┘## 📊 Key Features

                         │

                         ▼### Real-Time Data Collection

                  ┌─────────────┐- **Multi-source fallback**: Finnhub, Alpha Vantage, FMP, NewsAPI, Reddit, Twitter

                  │  WEBSOCKET  │- **Circuit breaker pattern**: Automatic failover on API failures

                  │   SERVER    │- **Rate limit handling**: Smart cooldown and retry mechanisms

                  └─────────────┘- **4 data streams**: Market prices, news articles, social sentiment, fundamental data

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

## 🚀 Quick StartFINNHUB_API_KEY=your_finnhub_key

ALPHA_VANTAGE_API_KEY=your_av_key

### PrerequisitesFMP_API_KEY=your_fmp_key

- Docker & Docker Compose

- API Keys:# News

  - OpenRouter API Key (for LLM analysis) - or OpenAI API KeyNEWSAPI_API_KEY=your_newsapi_key

  - Finnhub, Alpha Vantage, or FMP (market data)

  - NewsAPI (news data)# Social Media

  - Reddit/Twitter APIs (optional, for social sentiment)REDDIT_CLIENT_ID=your_reddit_id

REDDIT_CLIENT_SECRET=your_reddit_secret

### Environment SetupTWITTER_BEARER_TOKEN=your_twitter_token



Create `.env` in the backend root directory:# Configuration

STOCKS=AAPL,GOOGL,MSFT,TSLA

```bashMARKET_DATA_INTERVAL=60

# LLM APINEWS_FETCH_INTERVAL=300

OPENROUTER_API_KEY=your_openrouter_key```

# OR

OPENAI_API_KEY=your_openai_key**pathway/.env**

```bash

# Market Data (at least one)OPENAI_API_KEY=your_openai_key

FINNHUB_API_KEY=your_finnhub_keyKAFKA_BROKER=kafka:29092

ALPHA_VANTAGE_API_KEY=your_av_keyREDIS_HOST=redis

FMP_API_KEY=your_fmp_keyREDIS_PORT=6379

REDIS_DB=0

# News```

NEWSAPI_API_KEY=your_newsapi_key

**trading_agents/.env**

# Social Media (optional)```bash

REDDIT_CLIENT_ID=your_reddit_idOPENAI_API_KEY=your_openai_key

REDDIT_CLIENT_SECRET=your_reddit_secretPATHWAY_API_URL=http://pathway-unified-api:8000

TWITTER_BEARER_TOKEN=your_twitter_tokenREDIS_HOST=redis

REDIS_PORT=6379

# ConfigurationREDIS_DB=1

STOCKS=AAPL,GOOGL,TSLA,NVDAMONGODB_URI=mongodb://mongo:27017

MARKET_DATA_INTERVAL=60DATABASE_URL=postgresql://user:pass@postgres:5432/intelligence_db

NEWS_FETCH_INTERVAL=300```



# Redis (optional - uses local if not set)### Launch the System

REDIS_URL=rediss://...  # Upstash Redis URL

```bash

# Pathway License (optional)# Start all services

PATHWAY_LICENSE_KEY=your_license_keydocker-compose up -d

```

# View logs

### Launch the Systemdocker-compose logs -f



```bash# Check service health

# Start all services (from backend directory)curl http://localhost:8000/health  # Pathway Reports API

docker compose up -dcurl http://localhost:8001/health  # Trading Agents API

```

# View logs

docker compose logs -f### Services & Ports



# Check service health| Service | Port | Description |

curl http://localhost:8000/health  # Unified API|---------|------|-------------|

curl http://localhost:8080/health  # WebSocket Server| Pathway Reports API | 8000 | AI-generated analysis reports + Backtesting API |

```| Intelligence Agents API | 8001 | Investment analysis workflow execution |

| Kafka | 9092 | Message streaming |

### Services & Ports| Redis | 6379 | Caching & job queue |

| Zookeeper | 2181 | Kafka coordination |

| Service | Port | Description |

|---------|------|-------------|## 📁 Project Structure

| Unified API | 8000 | Reports, RAG, Backtesting, Bull-Bear, Strategist |

| WebSocket Server | 8080 | Real-time event streaming to frontend |```

| MCP Server | 9004 | Model Context Protocol tools server |.

| Kafka | 9092 | Message streaming (internal: 29092) |├── streaming/              # Data collection producers

| Redis | 6379 | Caching, pub/sub, vector store |│   ├── producers/          # Kafka producers for each data type

| Zookeeper | 2181 | Kafka coordination |│   │   ├── candle_producer.py  # OHLCV candle data for backtesting

│   │   └── ...

## 📁 Project Structure│   ├── data/              # CSV data files (candles.csv)

│   ├── fundamental_utils/  # FMP API client & web scraping

```│   └── utils/             # Kafka utilities

backend/│

├── streaming/              # Data collection producers├── pathway/               # Stream processing & AI analysis

│   ├── producers/          # Kafka producers for each data type│   ├── consumers/         # Kafka consumers (Pathway tables)

│   │   ├── base_producer.py       # Circuit breaker + multi-source fallback│   │   ├── candle_consumer.py  # Candle data consumer for backtesting

│   │   ├── market_data_producer.py│   │   └── ...

│   │   ├── news_producer.py│   ├── agents/            # LLM analysis agents

│   │   ├── sentiment_producer.py│   ├── backtesting_lib/   # O(1) Incremental Backtesting Engine

│   │   ├── fundamental_data_producer.py│   │   ├── trading_state.py    # Core trading logic (T+1 execution)

│   │   └── candle_producer.py     # OHLCV for backtesting│   │   ├── indicators.py       # Technical indicators

│   ├── webhook_receiver.py        # Twitter webhook endpoint│   │   ├── metrics.py          # Performance metrics

│   └── data/                      # CSV data files│   │   └── reducers.py         # Pathway reducers

││   ├── strategies/        # Trading strategy files (.txt)

├── pathway/                # Stream processing & AI analysis│   ├── api/               # FastAPI server for reports

│   ├── consumers/          # Kafka consumers (Pathway tables)│   │   ├── backtesting_api.py  # Backtesting endpoints

│   │   ├── base_consumer.py│   │   └── ...

│   │   ├── market_data_consumer.py│   └── reports/           # Generated analysis reports

│   │   ├── news_consumer.py│

│   │   ├── sentiment_consumer.py├── trading_agents/        # Multi-agent intelligence system

│   │   └── candle_consumer.py│   ├── all_agents/        # Agent implementations

│   ││   │   ├── researchers/   # Bull/Bear researchers

│   ├── agents/             # LLM analysis agents│   │   ├── risk_mngt/     # Risk analysis agents

│   │   ├── market_agent2.py       # LangGraph + TA-Lib technical analysis│   │   ├── managers/      # Risk & Hypothesis managers

│   │   ├── news_agent.py          # Story clustering + synthesis│   │   └── trader/        # Synthesis agent

│   │   ├── sentiment_clustering.py # Phase 1: Fast VADER clustering│   ├── graph/             # LangGraph workflow setup

│   │   ├── sentiment_reports.py   # Phase 2: LLM report generation│   ├── redis_queue/       # Job queue system

│   │   └── fundamental_agent.py   # Agentic RAG reports│   ├── api/               # Intelligence API endpoints

│   ││   └── utils/             # Helper utilities

│   ├── bullbear/           # Bull-Bear Debate System│

│   │   ├── graph.py               # LangGraph workflow└── kafka/                 # Kafka standalone config (optional)

│   │   ├── nodes.py               # Debate nodes (Bull, Bear, Facilitator)```

│   │   ├── state.py               # DebateState, DebatePoint types

│   │   ├── debate_runner.py       # Orchestrates debate execution## 🔄 Data Flow

│   │   ├── cache_manager.py       # Delta detection for reports

│   │   ├── memory_manager.py      # Mem0 integration### 1. Data Collection (Streaming)

│   │   └── llm_utils.py           # Prompts and LLM client```

│   │External APIs → Producers → Kafka Topics

│   ├── orchestrator/       # Strategist Agent + MCP Server```

│   │   ├── server.py              # FastMCP server entry point- Producers fetch data every N seconds (configurable)

│   │   ├── langgraph_agent.py     # ReAct agent with Mem0- Multi-source fallback ensures reliability

│   │   ├── tools/                 # MCP tool implementations- Data published to topic-specific Kafka queues

│   │   │   ├── risk_tools.py      # 3-tier risk assessment

│   │   │   ├── backtesting_tools.py### 2. Real-Time Analysis (Pathway)

│   │   │   ├── search_tools.py    # Web search```

│   │   │   └── report_tools.pyKafka → Pathway Consumers → LLM Analysis → Redis Cache

│   │   └── web_search.py          # DuckDuckGo integration```

│   │- Pathway subscribes to Kafka topics

│   ├── backtesting_lib/    # O(1) Incremental Backtesting- Applies windowing (1-minute tumbling windows)

│   │   ├── trading_state.py       # Core trading logic (T+1 execution)- LLM generates comprehensive reports

│   │   ├── indicators.py          # Incremental indicator calculations- Results cached in Redis with pub/sub

│   │   ├── metrics.py             # Performance metrics

│   │   └── reducers.py            # Pathway reducers### 3. Report Distribution (Pathway API)

│   │```

│   ├── api/                # FastAPI endpointsRedis Cache → FastAPI → HTTP Endpoints

│   │   ├── fastapi_server.py      # Main server```

│   │   ├── rag_api.py             # RAG + MCP endpoints- FastAPI serves cached reports on-demand

│   │   ├── bullbear_api.py        # Debate endpoints- Eliminates need to re-run analysis

│   │   ├── backtesting_api.py     # Strategy management- Sub-millisecond response times

│   │   ├── sentiment_api.py       # Sentiment clusters

│   │   └── chat_api.py            # Strategist chat### 4. Investment Intelligence (Intelligence Agents)

│   │```

│   ├── strategies/         # Trading strategy files (.txt)User Request → Fetch Reports → Multi-Agent Workflow → Ranked Hypotheses

│   ├── reports/            # Generated AI reports```

│   ├── knowledge_base/     # SEC 10-K documents for RAG- Retrieves latest reports from Pathway API

│   └── main_*.py           # Pipeline entry points- LangGraph orchestrates multi-agent debate and analysis

│- MongoDB stores conversation checkpoints

├── websocket/              # Real-time event server- Outputs ranked investment hypotheses with risk assessments

│   ├── main.py             # FastAPI WebSocket server

│   └── app/### 5. Backtesting (O(1) Incremental)

│       ├── websocket_manager.py```

│       ├── event_publisher.pyCandle Producer → Kafka → Pathway Backtester → Redis Metrics

│       └── redis_util.py```

│- Stream candles in real-time from CSV or live data

├── kafka/                  # Kafka standalone config- O(1) per-candle processing (no batch recomputation)

├── validation/             # Evaluation frameworks- Multiple strategies evaluated simultaneously

│   ├── RAGAS/              # RAG evaluation with FinQABench- Metrics cached in Redis for instant retrieval

│   ├── galileo_eval/       # Agent tool selection evaluation

│   └── backtesting_validation/  # Strategy validation vs backtesting.py## 🎛️ API Usage

│

└── docker-compose.yml      # Root orchestration (includes all services)### Get Stock Reports (Pathway API)

```

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

```curl http://localhost:8000/symbols

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

## 📈 Monitoring & Logs

### RAG Queries

### View Service Logs

```bash```bash

# Query the knowledge base# All services

curl -X POST http://localhost:8000/rag/query \docker-compose logs -f

  -H "Content-Type: application/json" \

  -d '{"question": "What is Apple revenue for 2024?", "symbol": "AAPL"}'# Specific service

```docker-compose logs -f market-consumer

docker-compose logs -f intelligence-agents-worker

## 🧪 Development```



### Running Individual Services### Check Reports

```bash

```bash# View generated reports

# Start Kafka first (creates network)ls -la pathway/reports/market/

cd kafka && docker compose up -dls -la pathway/reports/news/

ls -la pathway/reports/sentiment/

# Start streaming producersls -la pathway/reports/fundamental/

cd streaming && docker compose up -d```



# Start pathway consumers & API### Redis Monitoring

cd pathway && docker compose up -d```bash

# Connect to Redis CLI

# Start websocket serverdocker exec -it redis redis-cli

cd websocket && docker compose up -d

```# View cached symbols

SMEMBERS reports:symbols

### Local Development (without Docker)

# View report for symbol

```bashHGETALL reports:AAPL

# Install dependencies```

pip install -r pathway/requirements.txt

pip install -r streaming/requirements.txt## 🔧 Configuration



# Start Kafka & Redis via Docker### Stock Symbols

docker compose up kafka redis zookeeper -dConfigure which stocks to track in `streaming/.env`:

```bash

# Run services locallySTOCKS=AAPL,GOOGL,MSFT,TSLA,AMZN,NVDA

python streaming/producers/market_data_producer.py```

python pathway/main_market.py

uvicorn pathway.api.fastapi_server:app --reload --port 8000### Fetch Intervals

``````bash

MARKET_DATA_INTERVAL=60        # Market data every 60 seconds

## 📈 MonitoringNEWS_FETCH_INTERVAL=300        # News every 5 minutes

SENTIMENT_FETCH_INTERVAL=300   # Sentiment every 5 minutes

### View LogsFUNDAMENTAL_INTERVAL=3600      # Fundamentals every hour

```bash```

docker compose logs -f unified-api

docker compose logs -f market-consumer### LLM Models

```Edit in respective agent files:

```python

### Redis Monitoring# pathway/agents/market_agent.py

```bashchat = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.0)

docker exec -it pathway-redis redis-cli

# trading_agents/all_agents/utils/llm.py

# View cached symbolschat_model = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.7)

SMEMBERS reports:symbols```



# View sentiment clusters## 🛡️ Error Handling

GET sentiment_clusters:AAPL

```The system includes comprehensive error handling:

- **Circuit breakers** for API failures

### Health Checks- **Graceful degradation** with fallback data sources

```bash- **Automatic retries** with exponential backoff

curl http://localhost:8000/health- **Rate limit detection** and cooldown periods

curl http://localhost:8080/health- **Health checks** for all services

```

## 📝 Output Format

## 🔧 Configuration

### Investment Hypothesis Example

### Stock Symbols```json

```bash{

STOCKS=AAPL,GOOGL,MSFT,TSLA,NVDA  "symbol": "AAPL",

```  "hypothesis": "Strong bullish case based on positive earnings and technical strength",

  "evidence": {

### Fetch Intervals    "bull_points": ["Revenue growth exceeds expectations", "Positive market sentiment"],

```bash    "bear_points": ["High valuation concerns", "Competitive pressure"],

MARKET_DATA_INTERVAL=60        # Market data every 60 seconds    "synthesis": "Balance of evidence suggests growth potential despite risks"

NEWS_FETCH_INTERVAL=300        # News every 5 minutes  },

SENTIMENT_FETCH_INTERVAL=300   # Sentiment every 5 minutes  "risk_assessment": {

FUNDAMENTAL_INTERVAL=3600      # Fundamentals every hour    "aggressive": "High conviction entry opportunity",

```    "neutral": "Moderate position with defined risk",

    "conservative": "Wait for better entry or reduced position"

### LLM Configuration  },

```bash  "confidence": 0.78,

OPENAI_MODEL=openai/gpt-4o-mini  # Model for OpenRouter  "timestamp": "2025-11-11T10:30:00Z"

OPENAI_MODEL_AGENT=openai/gpt-4o-mini  # Model for Strategist}

``````



## 📝 Validation Results## 🤝 Contributing



### RAGAS Evaluation (RAG System)Each subdirectory contains its own detailed README:

| Method | Precision | Recall | Faithfulness | Relevancy |- [streaming/README.md](streaming/README.md) - Data collection layer

|--------|-----------|--------|--------------|-----------|- [pathway/README.md](pathway/README.md) - Stream processing layer

| Baseline | 0.722 | 0.827 | 0.777 | 0.791 |- [trading_agents/README.md](trading_agents/README.md) - Intelligence and analysis layer

| **Ours (Reranking + Context)** | **0.875** | **0.896** | **0.846** | **0.844** |

## 📄 License

### Backtesting Validation

- ✅ 7/7 metrics match for SMA Crossover strategyThis project is part of the Pathway InterIIT initiative.

- ✅ Equity-curve based Sharpe ratio (industry standard)

- ✅ Proper T+1 execution timing## 🙏 Acknowledgments



### Agent Evaluation (Galileo)- **Pathway** - Real-time data processing framework

- 64 test queries across 27 MCP tools- **LangGraph** - Multi-agent orchestration

- Tool selection accuracy: 88%- **OpenAI** - Language model APIs

- **Kafka** - Distributed streaming platform

## 📚 Documentation

- [Streaming Layer](streaming/README.md) - Data collection producers
- [Pathway Layer](pathway/README.md) - Stream processing & AI agents
- [WebSocket Server](websocket/readme.md) - Real-time event distribution
- [WebSocket Event Schemas](WEBSOCKET_EVENT_SCHEMAS.md) - Event type reference
- [Quick Start Guide](QUICKSTART.md) - Detailed setup instructions

## 📄 License

This project is part of the Pathway InterIIT initiative.

## 🙏 Acknowledgments

- **Pathway** - Real-time data processing framework
- **LangGraph** - Multi-agent orchestration
- **FastMCP** - Model Context Protocol server
- **Mem0** - Persistent memory for AI agents
- **OpenRouter** - LLM API gateway
