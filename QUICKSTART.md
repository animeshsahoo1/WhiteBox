# 🚀 Quick Start Guide

**Last Updated**: December 7, 2025  
**Estimated Setup Time**: 15-20 minutes

---

## ⚡ TL;DR - Quick Commands

```bash
# From the backend directory
cd backend

# Start all services
docker compose up -d

# Wait for services to initialize (30-60 seconds)
sleep 30

# Verify health
curl http://localhost:8000/health
curl http://localhost:8080/health
```

---

## 📋 What You're Building

A real-time stock analysis system with:
- **Kafka** streaming market data from multiple sources
- **Pathway** processing streams and generating AI reports
- **Redis** caching reports, pub/sub, and vector store
- **FastAPI** serving data to frontend via REST and WebSocket
- **Bull-Bear Debate** multi-agent investment analysis
- **Strategist Agent** conversational AI with MCP tools
- **O(1) Backtesting** incremental strategy evaluation

---

## ✅ Prerequisites

### Required Software
- **Docker Desktop** (version 20.10+) with Docker Compose
- **Git** (for cloning the repository)

### Required API Keys

#### 🔑 Essential (Required)
1. **OpenRouter API Key** (for LLM analysis)
   - Get it at: https://openrouter.ai/
   - Cost: ~$0.02 per 1000 requests
   - OR use **OpenAI API Key** directly

#### 📊 Market Data (Choose at least one)
2. **Finnhub API Key** (Recommended)
   - Get it at: https://finnhub.io/register
   - Free tier: 60 API calls/minute

3. **Financial Modeling Prep (FMP) API Key**
   - Get it at: https://site.financialmodelingprep.com/developer/docs
   - Free tier: 250 requests/day

4. **Alpha Vantage API Key**
   - Get it at: https://www.alphavantage.co/support/#api-key
   - Free tier: 25 requests/day

#### 📰 News Data
5. **NewsAPI Key**
   - Get it at: https://newsapi.org/register
   - Free tier: 100 requests/day

#### 🗨️ Social Media (Optional)
6. **Reddit API Credentials**
   - Create app at: https://www.reddit.com/prefs/apps
   - Free tier: 60 requests/minute

7. **Twitter API Key** (Optional)
   - Get it at: https://developer.twitter.com/
   - Requires webhook setup

---

## 📁 Step 1: Clone and Navigate

```bash
git clone https://github.com/Whintyr/Pathway_InterIIT.git
cd Pathway_InterIIT/backend
```

---

## 🔐 Step 2: Configure Environment

Create a `.env` file in the `backend/` directory:

```bash
# Create the .env file
cat > .env << 'EOF'
# ============================================
# LLM API (Choose one)
# ============================================
OPENROUTER_API_KEY=your_openrouter_key
# OR
# OPENAI_API_KEY=your_openai_key

# ============================================
# Market Data APIs (At least one required)
# ============================================
FINNHUB_API_KEY=your_finnhub_key
FMP_API_KEY=your_fmp_key
ALPHA_VANTAGE_API_KEY=your_alphavantage_key

# ============================================
# News API
# ============================================
NEWSAPI_API_KEY=your_newsapi_key

# ============================================
# Social Media (Optional)
# ============================================
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=StockSentimentBot/1.0

# ============================================
# Stock Configuration
# ============================================
STOCKS=AAPL,GOOGL,TSLA,NVDA

# Fetch intervals (seconds)
MARKET_DATA_INTERVAL=60
NEWS_FETCH_INTERVAL=300
SENTIMENT_FETCH_INTERVAL=300

# ============================================
# LLM Model Configuration
# ============================================
OPENAI_MODEL=openai/gpt-4o-mini
OPENAI_MODEL_AGENT=openai/gpt-4o-mini

# ============================================
# Redis (Optional - uses local by default)
# ============================================
# For Upstash Redis (recommended for production):
# REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# ============================================
# Pathway License (Optional)
# ============================================
# PATHWAY_LICENSE_KEY=your_license_key
EOF
```

---

## 🐳 Step 3: Start All Services

### Option A: Start Everything at Once (Recommended)

```bash
# From the backend directory
docker compose up -d

# Monitor startup
docker compose logs -f
```

### Option B: Start Services Individually

```bash
# 1. Start Kafka first (creates the network)
cd kafka
docker compose up -d
cd ..

# Wait for Kafka to be ready
sleep 30

# 2. Start streaming producers
cd streaming
docker compose up -d
cd ..

# 3. Start Pathway consumers & API
cd pathway
docker compose up -d
cd ..

# 4. Start WebSocket server
cd websocket
docker compose up -d
cd ..
```

---

## ✅ Step 4: Verify Services

### Health Checks

```bash
# Unified API (Reports, RAG, Backtesting, Bull-Bear, Strategist)
curl http://localhost:8000/health

# WebSocket Server
curl http://localhost:8080/health
```

### Expected Response

```json
{
  "status": "healthy",
  "service": "pathway-unified-api",
  "version": "8.0.0"
}
```

### Check All Containers

```bash
docker compose ps
```

Expected output:
```
NAME                    STATUS
pathway-redis           Up (healthy)
kafka                   Up (healthy)
zookeeper               Up
pathway-unified-api     Up
market-consumer         Up
news-consumer           Up
sentiment-phase1        Up
websocket-server        Up
...
```

---

## 🧪 Step 5: Test the System

### Get Available Symbols

```bash
curl http://localhost:8000/symbols
```

### Get Reports for a Symbol

```bash
# All reports
curl http://localhost:8000/reports/AAPL

# Specific report types
curl http://localhost:8000/reports/AAPL/market
curl http://localhost:8000/reports/AAPL/sentiment
curl http://localhost:8000/reports/AAPL/news
```

### Test Bull-Bear Debate

```bash
curl -X POST http://localhost:8000/bullbear/debate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "max_rounds": 2}'
```

### Test Strategist Chat

```bash
curl -X POST http://localhost:8000/strategist/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What trading strategies are available?", "user_id": "test"}'
```

### Test Backtesting

```bash
# List all strategies
curl http://localhost:8000/backtesting/strategies
```

### Test RAG Query

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Apple revenue?", "symbol": "AAPL"}'
```

---

## 🌐 Step 6: Connect Frontend

The frontend expects the backend at `http://localhost:8000`. Start the frontend:

```bash
cd ../frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

---

## 📊 Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f unified-api
docker compose logs -f market-consumer
docker compose logs -f sentiment-phase1
```

### Redis Monitoring

```bash
docker exec -it pathway-redis redis-cli

# List all keys
KEYS *

# View sentiment clusters
GET sentiment_clusters:AAPL

# View cached reports
HGETALL reports:AAPL
```

### Kafka Topics

```bash
# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:29092

# View messages on a topic
docker exec kafka kafka-console-consumer \
  --topic market-data \
  --bootstrap-server localhost:29092 \
  --from-beginning \
  --max-messages 5
```

---

## 🛑 Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v

# Stop specific service
docker compose stop unified-api
```

---

## 🔧 Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
docker compose logs <service-name>

# Rebuild a specific service
docker compose build <service-name> --no-cache
docker compose up -d <service-name>
```

### Redis Connection Issues

```bash
# Check Redis is running
docker exec pathway-redis redis-cli ping
# Expected: PONG

# If using Upstash, verify REDIS_URL in .env
```

### Kafka Connection Issues

```bash
# Check Kafka is healthy
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:29092

# Check if topics exist
docker exec kafka kafka-topics --list --bootstrap-server localhost:29092
```

### API Returns Empty Reports

Reports take 1-2 minutes to generate after startup. Check:
```bash
# View consumer logs
docker compose logs -f market-consumer news-consumer

# Reports should appear after "Report saved to Redis" messages
```

### Out of Memory

Reduce resource limits in `pathway/docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 512M  # Reduce from 999M
```

---

## 📁 File Structure Reference

```
backend/
├── .env                    # Your API keys (create this)
├── docker-compose.yml      # Root orchestration
├── kafka/                  # Kafka + Zookeeper
├── streaming/              # Data producers
├── pathway/                # AI processing + API
├── websocket/              # Real-time events
└── validation/             # Evaluation tools
```

---

## 🎯 Next Steps

1. **Explore the API**: See [README.md](README.md) for full API documentation
2. **Customize stocks**: Edit `STOCKS` in `.env`
3. **Add strategies**: Create `.txt` files in `pathway/strategies/`
4. **Run evaluations**: See `validation/` directory

## 📚 Additional Resources

- [Main README](README.md) - Full architecture and API reference
- [Pathway Documentation](pathway/README.md) - Stream processing details
- [Streaming Documentation](streaming/README.md) - Data producer details
- [WebSocket Events](WEBSOCKET_EVENT_SCHEMAS.md) - Event type reference
