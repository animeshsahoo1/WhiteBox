# Pathway AI Agents

LLM-powered analysis agents that process streaming data and generate comprehensive reports.

## 📋 Overview

Each agent:
- Receives Pathway tables from consumers
- Applies windowing and aggregation
- Calculates domain-specific metrics
- Generates LLM-powered analysis
- Outputs structured reports to Redis and filesystem

## 🗂️ Files

| File | Description |
|------|-------------|
| `market_agent2.py` | LangGraph + TA-Lib technical analysis |
| `news_agent.py` | Story clustering + LLM synthesis |
| `sentiment_clustering.py` | Phase 1: Fast VADER clustering |
| `sentiment_reports.py` | Phase 2: LLM sentiment reports |
| `fundamental_agent.py` | Agentic RAG fundamental analysis |
| `fundamental_report.py` | RAG report generator |
| `drift_agent.py` | Model drift detection |
| `utils/` | Shared utilities |

## 🤖 Agent Implementations

### Market Agent (`market_agent2.py`)

**Purpose**: Technical analysis using LangGraph multi-agent workflow

**Features**:
- TA-Lib indicator calculation (SMA, EMA, RSI, MACD, Bollinger Bands)
- LangGraph state management for multi-step analysis
- Module-level LLM caching (avoids recreation per UDF call)
- Saves reports to Redis and `/app/reports/market/`

**Technical Indicators**:
```python
# Via TechnicalTools class
- SMA (20, 50 periods)
- EMA (12, 26 periods)
- RSI (14 period)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- ATR (14 period)
```

**Entry Point**: `main_market.py`

---

### News Agent (`news_agent.py`)

**Purpose**: Story clustering with centroid-based similarity

**Features**:
- Embedding-based clustering (text-embedding-3-small)
- Centroid cosine similarity (threshold: 0.65)
- Cluster merging when similarity > 0.80
- LLM synthesis for cluster summaries
- News impact assessment for alerts

**Clustering Process**:
```
New Article → Embed → Find Similar Cluster → 
  If similarity > 0.65: Add to cluster, update centroid
  Else: Create new cluster
```

**Entry Point**: `main_news.py`

---

### Sentiment Agent (Two-Phase)

**Phase 1: Fast Clustering** (`sentiment_clustering.py`)

**Purpose**: Real-time sentiment scoring and clustering

**Features**:
- VADER sentiment scoring (no LLM required)
- Centroid-based post clustering
- Time-decay weighted sentiment (30-min half-life)
- Real-time Redis updates for API access
- Alert triggering for extreme sentiment

**Output**:
- JSON files: `{symbol}_clusters.json`
- Redis key: `sentiment_clusters:{symbol}`

**Entry Point**: `main_sentiment_phase1.py`

---

**Phase 2: LLM Reports** (`sentiment_reports.py`)

**Purpose**: Generate narrative sentiment reports

**Features**:
- Reads cluster data from Phase 1
- LLM-powered cluster analysis
- Trend detection and theme extraction
- Publishes reports to Redis

**Entry Point**: `main_sentiment_phase2.py`

---

### Fundamental Agent (`fundamental_agent.py`)

**Purpose**: Agentic RAG fundamental analysis

**Features**:
- Pathway DocumentStore for 10-K retrieval
- Contextual chunk enrichment
- LLM report generation
- Rating: BUY/SELL/HOLD

**Entry Point**: `main_fundamental.py`

---

## 📡 Event Publishing

All agents publish events to Redis for WebSocket forwarding:

```python
from event_publisher import publish_agent_status, publish_report, publish_alert

# Status updates
publish_agent_status("symbol:AAPL", "Market Agent", "RUNNING")
publish_agent_status("symbol:AAPL", "Market Agent", "COMPLETED")

# Reports
publish_report("symbol:AAPL", "Market Agent", report_data)

# Alerts (for significant events)
publish_alert("AAPL", "sentiment", "Extreme bearish sentiment", "high")
```

## 🔧 Configuration

### Environment Variables

```bash
# LLM
OPENROUTER_API_KEY=your_key
# OR
OPENAI_API_KEY=your_key

# Models
OPENAI_MODEL=openai/gpt-4o-mini

# Sentiment
SENTIMENT_ALERT_ENABLED=true
SENTIMENT_ALERT_MIN=-0.3
SENTIMENT_ALERT_MAX=0.3
SENTIMENT_ALERT_COOLDOWN=300

# Clustering
SIMILARITY_THRESHOLD=0.65
MERGE_THRESHOLD=0.80
```

## 📊 Report Output

Reports are saved to:
- **Redis**: For API access (`reports:AAPL:market`)
- **Filesystem**: `/app/reports/{type}/{symbol}/`

### Report Structure Example

```json
{
  "symbol": "AAPL",
  "report_type": "market",
  "timestamp": "2025-12-07T10:00:00Z",
  "trend": "BULLISH",
  "strength": "STRONG",
  "indicators": {
    "sma_20": 192.30,
    "sma_50": 188.50,
    "rsi": 65.4,
    "macd": 2.15
  },
  "analysis": "Technical analysis shows..."
}
```

## 🧪 Testing

```bash
# Run individual agent pipelines
python main_market.py
python main_news.py
python main_sentiment_phase1.py
python main_sentiment_phase2.py
python main_fundamental.py
```
