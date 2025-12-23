# Documentation Index

Quick reference for all documentation in the Pathway InterIIT project.

## 📚 Documentation Structure

### Root Level
| Document | Description |
|----------|-------------|
| [README.md](README.md) | Main project overview, architecture, quick start, and API usage |
| [QUICKSTART.md](QUICKSTART.md) | Detailed setup guide for new developers |
| [WEBSOCKET_EVENT_SCHEMAS.md](WEBSOCKET_EVENT_SCHEMAS.md) | WebSocket event type specifications |

### Streaming Layer
| Document | Description |
|----------|-------------|
| [streaming/README.md](streaming/README.md) | Data collection layer, producers, sources |
| [streaming/producers/README.md](streaming/producers/README.md) | Producer implementations and base class |

### Pathway Layer
| Document | Description |
|----------|-------------|
| [pathway/README.md](pathway/README.md) | Stream processing, AI agents, Redis caching |
| [pathway/consumers/README.md](pathway/consumers/README.md) | Kafka consumers and Pathway tables |
| [pathway/agents/README.md](pathway/agents/README.md) | LLM-powered analysis agents |
| [pathway/orchestrator/README.md](pathway/orchestrator/README.md) | Strategist Agent + MCP Server |
| [pathway/bullbear/evaluation/README.md](pathway/bullbear/evaluation/README.md) | Bull-Bear debate evaluation framework |

### WebSocket Server
| Document | Description |
|----------|-------------|
| [websocket/readme.md](websocket/readme.md) | Real-time WebSocket server with Redis Pub/Sub |

### Validation & Evaluation
| Document | Description |
|----------|-------------|
| [validation/RAGAS/README.md](validation/RAGAS/README.md) | RAG system evaluation using RAGAS benchmark |
| [validation/galileo_eval/README.md](validation/galileo_eval/README.md) | Agent tool selection evaluation |
| [validation/backtesting_validation/README.md](validation/backtesting_validation/README.md) | Backtesting accuracy validation |

### Infrastructure
| Document | Description |
|----------|-------------|
| [kafka/README.md](kafka/README.md) | Standalone Kafka setup for development |

## 🎯 Quick Links by Role

### New Users
1. Start with [README.md](README.md)
2. Follow [QUICKSTART.md](QUICKSTART.md)
3. Test API endpoints from main README

### Backend Developers
1. [streaming/README.md](streaming/README.md) - Data sources
2. [pathway/README.md](pathway/README.md) - Stream processing
3. [pathway/agents/README.md](pathway/agents/README.md) - AI agents

### AI/ML Engineers
1. [pathway/agents/README.md](pathway/agents/README.md) - LLM agents
2. [pathway/orchestrator/README.md](pathway/orchestrator/README.md) - Strategist + MCP
3. [pathway/bullbear/evaluation/README.md](pathway/bullbear/evaluation/README.md) - Debate system

### DevOps/Infrastructure
1. [README.md](README.md) - System architecture
2. [kafka/README.md](kafka/README.md) - Kafka setup
3. Docker compose files in each directory

## 🔍 Quick Reference

### API Endpoints
- Reports: `GET /reports/{symbol}/{type}`
- Bull-Bear: `POST /bullbear/debate`
- Strategist: `POST /strategist/chat`
- Backtesting: `GET /backtesting/strategies`
- RAG: `POST /rag/query`

### WebSocket Channels
- `ws/reports/{symbol}` - Symbol-specific events
- `ws/alerts` - Global alerts
- `ws/backtesting` - Backtesting metrics

### Kafka Topics
- `market-data` - Real-time prices
- `news-data` - News articles
- `sentiment-data` - Social sentiment
- `fundamental-data` - Company fundamentals
- `candles` - OHLCV candle data
