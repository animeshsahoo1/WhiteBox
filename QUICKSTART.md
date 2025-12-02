# 🚀 Quick Start Guide - New Developer Setup

**Last Updated**: November 16, 2025  
**Estimated Setup Time**: 15-20 minutes

---

## ⚡ TL;DR - Quick Command Reference

**Start everything in this exact order:**

```powershell
# Terminal 1: Start webhook receiver (must be first!)
cd streaming
python webhook_receiver.py

# Terminal 2: Start Kafka, wait 30s, then start producers and Pathway
cd kafka
docker-compose up -d
Start-Sleep -Seconds 30

cd ..\streaming
docker-compose up -d

cd ..\pathway
docker-compose up -d --build

# Verify on port 8000
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/clusters
```

---

## 📋 What You're Building

A real-time stock analysis system with:
- **Kafka** streaming market data from multiple sources
- **Pathway** processing streams and generating AI reports
- **Redis** caching reports and cluster data
- **FastAPI** serving data to frontend
- **Sentiment Analysis** with VADER scoring and clustering

---

## ✅ Prerequisites

### Required Software
- **Docker Desktop** (version 20.10+)
  - Download: https://www.docker.com/products/docker-desktop
  - Ensure Docker Compose is included (usually bundled)
- **Git** (for cloning the repository)
- **Text Editor** (VS Code recommended)

### Required API Keys
You'll need at least one key from each category:

#### 🔑 Essential (Required)
1. **OpenRouter API Key** (for LLM analysis)
   - Get it at: https://openrouter.ai/
   - Used for: Generating AI-powered sentiment reports
   - Cost: ~$0.02 per 1000 requests

#### 📊 Market Data (Choose at least one)
2. **Finnhub API Key** (Recommended - Free tier available)
   - Get it at: https://finnhub.io/register
   - Used for: Real-time stock prices, news
   - Free tier: 60 API calls/minute

3. **Alpha Vantage API Key** (Alternative/Fallback)
   - Get it at: https://www.alphavantage.co/support/#api-key
   - Free tier: 25 requests/day

4. **Financial Modeling Prep (FMP) API Key** (Alternative/Fallback)
   - Get it at: https://site.financialmodelingprep.com/developer/docs
   - Free tier: 250 requests/day

#### 📰 News Data (Choose at least one)
5. **NewsAPI Key** (Recommended - Free tier available)
   - Get it at: https://newsapi.org/register
   - Used for: Stock-related news articles
   - Free tier: 100 requests/day

#### 🗨️ Social Media (Optional but recommended)
6. **Reddit API Credentials** (Optional)
   - Create app at: https://www.reddit.com/prefs/apps
   - Used for: Reddit sentiment from r/wallstreetbets, r/stocks
   - Free tier: 60 requests/minute

7. **Twitter API Key** (Optional)
   - Get it at: https://developer.twitter.com/
   - Used for: Tweet sentiment analysis
   - Free tier available
   - **Note**: Requires ngrok setup to receive webhooks (see `streaming/NGROK_SETUP.md`)

---

## 📁 Step 1: Clone the Repository

```powershell
# Clone the repository
git clone https://github.com/Whintyr/Pathway_InterIIT.git
cd Pathway_InterIIT
```

---

## ⚙️ Step 2: Configure Environment Variables

You need to create `.env` files in **three directories**: `kafka`, `streaming`, and `pathway`.

### 2.1 - Kafka Configuration

```powershell
cd kafka
copy .env.example .env
notepad .env  # Or use your preferred editor
```

**Edit `kafka/.env`:**
```bash
# Usually no changes needed - defaults work fine
KAFKA_BROKER=localhost:9092
```

### 2.2 - Streaming Service Configuration

```powershell
cd ..\streaming
copy .env.example .env
notepad .env
```

**Edit `streaming/.env` with your API keys:**
```bash
# Required: At least one market data source
FINNHUB_API_KEY=your_finnhub_key_here

# Required: News source
NEWS_API_KEY=your_newsapi_key_here

# Optional: Fallback APIs (recommended for production)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
FMP_API_KEY=your_fmp_key_here

# Optional: Social media (Reddit)
REDDIT_CLIENT_IDS=your_reddit_client_id_here
REDDIT_CLIENT_SECRETS=your_reddit_client_secret_here

# Optional: Twitter
TWITTER_API_KEY=your_twitter_api_key_here

# Configuration (customize these)
STOCKS=AAPL,GOOGL,MSFT,TSLA,NVDA
KAFKA_BROKER=localhost:9092

# Fetch intervals (in seconds)
MARKET_DATA_INTERVAL=60
NEWS_DATA_INTERVAL=300
SENTIMENT_DATA_INTERVAL=60
```

### 2.3 - Pathway Service Configuration

```powershell
cd ..\pathway
copy .env.example .env
notepad .env
```

**Edit `pathway/.env` with your LLM key:**
```bash
# Required: LLM API for generating reports
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Alternative: Use OpenAI directly
# OPENAI_API_KEY=your_openai_api_key_here

# Model configuration (default is good for most use cases)
OPENAI_MODEL=openai/gpt-4o-mini

# Stocks to track (must match streaming/.env)
STOCKS=AAPL,GOOGL,MSFT,TSLA,NVDA

# Company name mapping (used in reports)
STOCK_COMPANY_MAP={"AAPL": "Apple Inc.", "GOOGL": "Alphabet Inc.", "MSFT": "Microsoft Corporation", "TSLA": "Tesla Inc.", "NVDA": "NVIDIA Corporation"}

# Redis configuration (defaults work with docker-compose)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Kafka configuration (defaults work with docker-compose)
KAFKA_BROKER=kafka:29092
```

---

## 🐳 Step 3: Start the System

**IMPORTANT**: Services must be started in this exact order!

### 3.1 - Start Twitter Webhook Receiver (FIRST!)

```powershell
# Navigate to streaming directory
cd ..\streaming

# Start webhook receiver in a dedicated terminal
python webhook_receiver.py
```

**Expected output:**
```
🚀 Twitter Webhook Receiver Starting
Configuration loaded
Webhook URL: http://localhost:5001/webhook/twitter
 * Running on http://0.0.0.0:5001
```

**Leave this running in the terminal!** Open a new PowerShell terminal for the next steps.

> **Why first?** The webhook receiver must be running before starting the sentiment producer, as the producer will attempt to connect to it on startup to fetch Twitter data.

> **🌐 Optional - Twitter Integration**: To receive real-time tweets, you need to expose the webhook using ngrok and configure TwitterAPI.io. See `streaming/NGROK_SETUP.md` for detailed instructions. This is optional - the system works with Reddit sentiment alone.

### 3.2 - Start Kafka Infrastructure

```powershell
# In a NEW terminal, navigate to kafka directory
cd D:\interiit\Pathway_InterIIT\kafka

# Start Kafka, Zookeeper, and dependencies
docker-compose up -d

# Verify Kafka is running (wait ~30 seconds)
docker-compose ps
```

**Expected output:**
```
NAME                STATUS              PORTS
kafka               Up 30 seconds       0.0.0.0:9092->9092/tcp
zookeeper           Up 30 seconds       2181/tcp
```

**Wait 30-60 seconds** for Kafka to fully initialize before proceeding.

### 3.3 - Start Streaming Producers

```powershell
# Navigate to streaming directory
cd ..\streaming

# Start all data producers (including sentiment producer that connects to webhook)
docker-compose up -d

# Check logs to verify data is flowing
docker-compose logs -f
```

**What you should see:**
- `market-producer` fetching stock prices every 60s
- `news-producer` fetching news articles every 300s
- `sentiment-producer` connecting to webhook receiver on port 5001
- `sentiment-producer` collecting Reddit + Twitter data
- `fundamental-producer` gathering company financials

**Press Ctrl+C to stop following logs**

### 3.4 - Start Pathway Consumers & API

```powershell
# Navigate to pathway directory
cd ..\pathway

# Build and start Pathway services
docker-compose up -d --build

# Monitor logs to see report generation
docker-compose logs -f sentiment-consumer
```

**What you should see:**
- Connecting to Kafka topics
- Processing sentiment data
- Generating cluster summaries
- Writing to Redis cache
- "Done writing X entries" messages

**Press Ctrl+C to stop following logs**

---

## ✨ Step 4: Verify Everything Works

### 4.1 - Check Webhook Receiver (Port 5001)

```powershell
# In a new terminal, test webhook receiver
Invoke-RestMethod http://localhost:5001/
```

**Expected response:**
```json
{
  "status": "running",
  "service": "Twitter Webhook Receiver",
  "endpoints": {
    "webhook": "/webhook/twitter (POST)",
    "tweets": "/tweets/<stock> (GET)"
  }
}
```

### 4.2 - Check FastAPI Health (Port 8000)

```powershell
# Check Pathway API health
Invoke-RestMethod http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "reports_count": 5,
  "clusters_count": 12,
  "timestamp": "2025-11-16T..."
}
```

### 4.3 - Test API Endpoints

```powershell
# Get all cluster data with market sentiment
Invoke-RestMethod http://localhost:8000/clusters | ConvertTo-Json -Depth 10

# Get clusters for a specific stock (e.g., AAPL)
Invoke-RestMethod http://localhost:8000/clusters/AAPL | ConvertTo-Json -Depth 10

# Get sentiment report for a stock
Invoke-RestMethod http://localhost:8000/reports/AAPL | ConvertTo-Json -Depth 10
```

### 4.4 - Inspect Redis Data

```powershell
# Connect to Redis container
docker exec -it pathway-redis redis-cli

# Inside Redis CLI:
KEYS *                    # See all keys
HGETALL clusters:all      # View all cluster data
GET clusters:AAPL:1       # View specific cluster
GET report:sentiment:AAPL # View sentiment report
EXIT
```

### 4.5 - Test Backtesting API (Optional)

```powershell
# Start backtesting pipeline
cd pathway
docker-compose up -d backtesting-pipeline

# Start candle producer (in streaming folder)
cd ..\streaming
docker-compose up -d candle-producer

# List all strategies
Invoke-RestMethod http://localhost:8000/api/backtesting/strategies | ConvertTo-Json -Depth 10

# Get metrics for a specific strategy
Invoke-RestMethod http://localhost:8000/api/backtesting/strategy/sma_crossover | ConvertTo-Json

# Create a new strategy using LLM
$body = @{ description = "RSI oversold bounce with 30/70 levels" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/backtesting/strategy -Body $body -ContentType "application/json"
```

**Expected response for strategies:**
```json
{
  "strategies": [
    {
      "strategy": "sma_crossover",
      "metrics": {
        "total_pnl": -350.27,
        "win_rate": 0.667,
        "sharpe_ratio": -0.23,
        "max_drawdown": 0.05,
        ...
      }
    }
  ]
}
```

---

## 📊 Step 5: Understanding the Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  WEBHOOK RECEIVER (streaming/webhook_receiver.py)               │
│  - Runs on localhost:5001-> ngrok http 5001                     │
│  - Receives real-time tweets from TwitterAPI.io                 │
│  - Buffers tweets in memory (1000 per stock)                    │
│  - Provides /tweets/<stock> endpoint for producers              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STREAMING PRODUCERS (streaming/)                                │
│  - market-producer: Stock prices every 60s                       │
│  - news-producer: News articles every 300s                       │
│  - sentiment-producer: Fetches from webhook + Reddit every 60s   │
│  - fundamental-producer: Company data every 10 hours             │
│  - candle-producer: OHLCV candles for backtesting               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
                    ┌─────────┐
                    │  KAFKA  │ (5 topics: market, news,
                    │         │  sentiment, fundamental, candles)
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
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
                    │  REDIS  │ (Caches reports, clusters,
                    │         │  backtesting metrics)
                    └────┬────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  FASTAPI SERVER (pathway/api/)                                   │
│  - GET /health: Service status                                   │
│  - GET /clusters: All clusters + market sentiment                │
│  - GET /clusters/{symbol}: Stock-specific clusters               │
│  - GET /reports/{symbol}: AI-generated reports                   │
│  - GET /api/backtesting/strategies: All strategy metrics         │
│  - POST /api/backtesting/strategy: Create new strategy (LLM)     │
│  Port: 8000                                                       │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
                    ┌─────────┐
                    │FRONTEND │ (Your custom visualization)
                    └─────────┘
```

---

## ✅ Success Checklist

- [ ] Docker Desktop installed and running
- [ ] All required API keys obtained
- [ ] `.env` files created in kafka, streaming, and pathway directories
- [ ] **Webhook receiver started FIRST** (`python webhook_receiver.py` running on port 5001)
- [ ] Kafka started successfully (`docker-compose up -d` in kafka/)
- [ ] **Waited 30-60 seconds** after starting Kafka
- [ ] Streaming producers running (`docker-compose up -d` in streaming/)
- [ ] Pathway consumers running (`docker-compose up -d --build` in pathway/)
- [ ] Webhook health check passes (`GET http://localhost:5001/` returns 200)
- [ ] Pathway health check passes (`GET http://localhost:8000/health` returns "healthy")
- [ ] Clusters endpoint returns data (`GET /clusters` has clusters)
- [ ] Can fetch stock-specific data (`GET /clusters/AAPL` works)

### Optional: Backtesting
- [ ] Candle producer running (`docker-compose up -d candle-producer` in streaming/)
- [ ] Backtesting pipeline running (`docker-compose up -d backtesting-pipeline` in pathway/)
- [ ] Strategies endpoint works (`GET /api/backtesting/strategies`)
- [ ] Can create strategy via LLM (`POST /api/backtesting/strategy`)

**If all items checked, you're ready to build your frontend! 🎉**
