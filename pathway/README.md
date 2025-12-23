# Pathway Stream Processing & AI Analysis

Real-time stream processing layer that consumes data from Kafka, performs AI-powered analysis using LLMs, and serves reports via FastAPI with Redis caching.

## 📋 Overview

This layer transforms raw streaming data into actionable intelligence using:
- **Pathway**: Real-time data processing with windowing and aggregation
- **LangGraph**: Multi-agent workflows for market analysis and debate
- **OpenRouter/OpenAI**: LLM-powered analysis and report generation
- **Redis**: High-speed report caching, pub/sub, and vector store
- **FastAPI**: Unified REST API for all services

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         KAFKA TOPICS                             │
│  (market-data, news-data, sentiment-data, fundamental-data,     │
│   candles)                                                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PATHWAY CONSUMERS                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │ Market   │  │ News     │  │Sentiment │  │ Candle           ││
│  │ Consumer │  │ Consumer │  │Consumer  │  │ Consumer         ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘│
│       │             │             │                  │          │
│       ▼             ▼             ▼                  ▼          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              PATHWAY STREAM PROCESSING                    │  │
│  │  • Windowing (1-min tumbling windows)                     │  │
│  │  • Technical indicators (TA-Lib)                          │  │
│  │  • Clustering (cosine similarity)                         │  │
│  │  • Aggregation & grouping                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   AI AGENTS     │  │  BACKTESTING    │  │   BULL-BEAR         │
│ (Market, News,  │  │   O(1)          │  │   DEBATE            │
│  Sentiment,     │  │  Incremental    │  │  (LangGraph+Mem0)   │
│  Fundamental)   │  │                 │  │                     │
└────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘
         │                    │                      │
         └────────────────────┼──────────────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │    REDIS     │
                      │    CACHE     │
                      └──────┬───────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
      ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
      │ Reports API │ │ RAG API     │ │ Strategist      │
      │ (FastAPI)   │ │ (Pathway    │ │ (MCP Server +   │
      │             │ │  DocStore)  │ │  LangGraph)     │
      └─────────────┘ └─────────────┘ └─────────────────┘
```

## 📁 Structure

```
pathway/
├── consumers/              # Kafka consumers (Pathway tables)
│   ├── base_consumer.py       # Base class with Kafka settings
│   ├── market_data_consumer.py
│   ├── news_consumer.py
│   ├── sentiment_consumer.py
│   ├── fundamental_data_consumer.py
│   ├── candle_consumer.py     # OHLCV for backtesting
│   └── drift_consumer.py      # Model drift detection
│
├── agents/                 # LLM analysis agents
│   ├── market_agent2.py       # LangGraph + TA-Lib technical analysis
│   ├── news_agent.py          # Story clustering + LLM synthesis
│   ├── sentiment_clustering.py # Phase 1: Fast VADER clustering
│   ├── sentiment_reports.py   # Phase 2: LLM report generation
│   ├── fundamental_agent.py   # Agentic RAG reports
│   ├── fundamental_report.py  # RAG report generator
│   └── drift_agent.py         # Model drift detection
│
├── bullbear/               # Bull-Bear Debate System
│   ├── graph.py               # LangGraph workflow definition
│   ├── nodes.py               # Bull, Bear, Facilitator nodes
│   ├── state.py               # DebateState, DebatePoint types
│   ├── config.py              # Debate configuration
│   ├── debate_runner.py       # Orchestrates debate execution
│   ├── cache_manager.py       # Delta detection for report changes
│   ├── memory_manager.py      # Mem0 integration for context
│   ├── llm_utils.py           # Prompts and LLM client
│   ├── debate_points.py       # Point management and deduplication
│   └── clients.py             # Reports and RAG API clients
│
├── orchestrator/           # Strategist Agent + MCP Server
│   ├── server.py              # FastMCP server entry point
│   ├── langgraph_agent.py     # ReAct agent with Mem0 memory
│   ├── config.py              # Agent configuration
│   ├── chat_store.py          # Conversation history
│   ├── web_search.py          # DuckDuckGo integration
│   └── tools/                 # MCP tool implementations
│       ├── risk_tools.py      # 3-tier risk assessment
│       ├── backtesting_tools.py
│       ├── search_tools.py
│       ├── report_tools.py
│       └── api_tools.py
│
├── backtesting_lib/        # O(1) Incremental Backtesting
│   ├── trading_state.py       # Core trading logic (T+1 execution)
│   ├── indicators.py          # Incremental indicator calculations
│   ├── metrics.py             # Performance metrics (Sharpe, Sortino)
│   ├── reducers.py            # Pathway reducers for state
│   └── schemas.py             # Data schemas
│
├── api/                    # FastAPI endpoints
│   ├── fastapi_server.py      # Main server with all routers
│   ├── rag_api.py             # RAG + Pathway MCP endpoints
│   ├── bullbear_api.py        # Debate endpoints
│   ├── backtesting_api.py     # Strategy management + search
│   ├── sentiment_api.py       # Sentiment clusters
│   ├── news_api.py            # News clusters
│   ├── report_fetch_api.py    # Report retrieval
│   ├── historical_analysis_api.py
│   ├── workflow_api.py        # Combined workflow
│   ├── drift_api.py           # Drift detection
│   └── chat_api.py            # Strategist chat interface
│
├── guardrails/             # Input/output validation
├── strategies/             # Trading strategy files (.txt)
├── reports/                # Generated AI reports
├── knowledge_base/         # SEC 10-K documents for RAG
├── pathway_state/          # Pathway checkpointing
│
├── main_market.py          # Market analysis pipeline
├── main_news.py            # News clustering pipeline
├── main_sentiment_phase1.py # Fast sentiment clustering
├── main_sentiment_phase2.py # LLM sentiment reports
├── main_fundamental.py     # Fundamental analysis pipeline
├── main_backtesting.py     # Backtesting pipeline
├── main_drift.py           # Drift detection pipeline
├── main_market_demo_service.py # Demo market service
│
├── redis_cache.py          # Redis utilities
├── event_publisher.py      # Redis pub/sub events
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🚀 Quick Start

### Environment Configuration

Create `pathway/.env` or use root `.env`:
```bash
# LLM API
OPENROUTER_API_KEY=your_key
# OR
OPENAI_API_KEY=your_key

# Kafka
KAFKA_BROKER=kafka:29092

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
# OR for Upstash:
# REDIS_URL=rediss://...

# Processing windows
MARKET_WINDOW_DURATION=60
NEWS_WINDOW_DURATION=300
SENTIMENT_WINDOW_DURATION=300
```

### Docker Deployment

```bash
# From pathway directory
docker compose up -d

# View logs
docker compose logs -f unified-api
docker compose logs -f market-consumer

# Check health
curl http://localhost:8000/health
```

### Local Development

```bash
pip install -r requirements.txt

# Run individual pipelines
python main_market.py
python main_news.py
python main_sentiment_phase1.py

# Run API server
uvicorn api.fastapi_server:app --reload --port 8000
```

## 📊 AI Agents

### Market Agent (`agents/market_agent2.py`)

LangGraph multi-agent workflow with TA-Lib indicators:
- Technical indicator calculation (SMA, EMA, RSI, MACD, Bollinger Bands)
- Multi-agent state for analysis workflow
- LLM-powered market commentary
- Saves reports to Redis and filesystem

### News Agent (`agents/news_agent.py`)

Story clustering with centroid-based cosine similarity:
- Embedding-based clustering (text-embedding-3-small)
- Cluster merging when similarity > 0.80
- LLM synthesis for cluster summaries
- News impact assessment for alerts

### Sentiment Agent (Two-Phase)

**Phase 1** (`agents/sentiment_clustering.py`):
- Fast VADER sentiment scoring
- Centroid-based post clustering
- Time-decay weighted sentiment
- Real-time Redis updates

**Phase 2** (`agents/sentiment_reports.py`):
- LLM-generated sentiment reports
- Cluster narrative synthesis
- Alert triggering for extreme sentiment

### Fundamental Agent (`agents/fundamental_agent.py`)

Agentic RAG with 10-K document retrieval:
- Pathway DocumentStore for vector search
- Contextual chunk enrichment
- LLM report generation

## 🐂🐻 Bull-Bear Debate System

### Features
- **Asian Parliamentary Format**: Bull opens, order reverses in final round
- **Toulmin Argumentation**: Claim, Evidence, Warrant, Qualifier, Rebuttal scoring
- **Delta Detection**: Only debates on new/changed report information
- **RAG Integration**: Evidence retrieval from knowledge base
- **Mem0 Memory**: Persistent context across debates

### Graph Workflow

```
START → fetch_reports → compute_deltas → validate_previous
                                              │
         ┌────────────────────────────────────┘
         │
         ▼
    bull_point ←→ bear_point (alternating rounds)
         │
         ▼
    facilitator_conclusion → END
```

### API Usage

```bash
# Start debate
curl -X POST http://localhost:8000/bullbear/debate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "max_rounds": 3}'

# Get status
curl http://localhost:8000/bullbear/status/AAPL

# Get facilitator conclusion
curl http://localhost:8000/bullbear/facilitator/AAPL
```

## 🤖 Strategist Agent (MCP Server)

### Features
- **Model Context Protocol**: Standardized tool interface
- **LangGraph ReAct**: Multi-turn reasoning with tool calling
- **Mem0 Memory**: User preferences and past interactions
- **27 MCP Tools**: Risk, backtesting, search, reports

### Available Tools

| Category | Tools |
|----------|-------|
| Risk | `assess_risk` (3-tier: no-risk, neutral, aggressive) |
| Backtesting | `list_strategies`, `search_strategies`, `create_strategy`, `compare_strategies` |
| Search | `web_search` (DuckDuckGo with query decomposition) |
| Reports | `get_facilitator_report`, `get_debate_summary` |

### API Usage

```bash
# Chat
curl -X POST http://localhost:8000/strategist/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find momentum strategies", "user_id": "user123"}'

# Streaming
curl -X POST http://localhost:8000/strategist/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Analyze AAPL risk", "user_id": "user123"}'

# Memory
curl http://localhost:8000/strategist/memory/user123
```

## 📈 O(1) Backtesting Engine

### Features
- **Incremental Processing**: O(1) per candle, no batch recomputation
- **T+1 Execution**: Signal at bar close, execute at next bar open
- **Multi-Strategy**: Natural join on interval for parallel evaluation
- **LLM Generation**: Create strategies from natural language
- **Semantic Search**: Find similar strategies using embeddings

### Metrics Calculated
- Total Trades, Win Rate
- Sharpe Ratio (equity-curve based)
- Sortino Ratio
- Max Drawdown
- Profit Factor
- Expectancy

### API Usage

```bash
# List strategies
curl http://localhost:8000/backtesting/strategies

# Get metrics
curl http://localhost:8000/backtesting/metrics/sma_crossover

# Create from natural language
curl -X POST http://localhost:8000/backtesting/strategies \
  -H "Content-Type: application/json" \
  -d '{"description": "RSI oversold bounce with 30/70 levels"}'

# Semantic search
curl -X POST http://localhost:8000/backtesting/strategies/search \
  -H "Content-Type: application/json" \
  -d '{"query": "momentum with stop loss"}'
```

## 🔍 RAG System

### Features
- **Pathway DocumentStore**: Vector store with BruteForce KNN
- **Contextual Enrichment**: Gemini-powered chunk context injection
- **Cohere Reranking**: Over-retrieve 2x, rerank to top-k
- **Agentic RAG**: ReAct loop with self-reflection
- **Pathway MCP Server**: Expose RAG via Model Context Protocol

### API Usage

```bash
# Query
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Apple revenue?", "symbol": "AAPL"}'

# Upload document
curl -X POST http://localhost:8000/rag/upload \
  -F "file=@document.pdf" \
  -F "symbol=AAPL"
```

## 📡 Event Publishing

Events are published to Redis Pub/Sub for WebSocket forwarding:

```python
from event_publisher import publish_agent_status, publish_report, publish_alert

# Agent status
publish_agent_status("symbol:AAPL", "Market Agent", "RUNNING")

# Report ready
publish_report("symbol:AAPL", "Market Agent", report_data)

# Alert
publish_alert("AAPL", "sentiment", "Extreme bearish sentiment", "high")
```

## 🔧 Services (docker-compose.yml)

| Service | Description |
|---------|-------------|
| `redis` | Redis Stack (with RediSearch for Mem0) |
| `unified-api` | FastAPI server on port 8000 |
| `mcp-server` | MCP tools server on port 9004 |
| `market-consumer` | Market data processing |
| `news-consumer` | News clustering and reports |
| `sentiment-phase1` | Fast sentiment clustering |
| `sentiment-phase2` | LLM sentiment reports |
| `fundamental-consumer` | Fundamental analysis |
| `backtesting` | Strategy backtesting pipeline |

## 📚 Additional Documentation

- [Consumers README](consumers/README.md)
- [Agents README](agents/README.md)
- [Orchestrator README](orchestrator/README.md)
- [Bull-Bear Evaluation](bullbear/evaluation/README.md)
