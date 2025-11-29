# Bull-Bear Debate System

AI-powered bull-bear debate system with LangGraph orchestration and Pathway streaming for facilitator reports.

## 🏗️ Architecture

```
┌──────────────────┐
│  Pathway API     │ ──→ Provides 4 analysis reports
│  (port 8000)     │     (market, sentiment, news, fundamental)
└──────────────────┘
         ↓
┌──────────────────┐
│ Bull-Bear API    │ ──→ Orchestrates debate workflow
│  (port 8001)     │     Endpoint: POST /begin_debate
└──────────────────┘
         ↓
┌──────────────────┐
│ LangGraph        │ ──→ Bull ↔ Bear alternating debate
│ (bull_bear_graph)│     Uses real agent nodes
└──────────────────┘
         ↓
┌──────────────────┐
│ Debate Points    │ ──→ JSON output with full transcript
│ (.json/.jsonl)   │
└──────────────────┘
         ↓
┌──────────────────┐
│ Facilitator      │ ──→ Pathway streaming processor
│ (Pathway Stream) │     Generates balanced summary
└──────────────────┘
         ↓
┌──────────────────┐
│ Final Report     │ ──→ Markdown facilitator report
│ (.md)            │
└──────────────────┘
```

## 📦 Services

### 1. **Bull-Bear API** (port 8001)
- FastAPI server that orchestrates the debate
- Fetches reports from Pathway API
- Runs LangGraph workflow
- Converts output for facilitator processing

### 2. **Facilitator** (Pathway Streaming)
- Processes debate points using Pathway
- Generates balanced summary reports
- Updates incrementally like news_agent pattern

## 🚀 Quick Start

### Using Docker Compose

```bash
# 1. Copy environment file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 2. Start services
docker-compose up -d

# 3. Check health
curl http://localhost:8001/health

# 4. Trigger a debate
curl -X POST http://localhost:8001/begin_debate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "max_rounds": 2}'
```

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export OPENAI_API_KEY=your_key
export PATHWAY_API_URL=http://localhost:8000

# 3. Start the API server
python bull_bear_main.py

# 4. In another terminal, run facilitator
python facilitator_main.py
```

## 📋 API Endpoints

### POST /begin_debate
Start a bull-bear debate for a symbol.

**Request:**
```json
{
  "symbol": "AAPL",
  "max_rounds": 2
}
```

**Response:**
```json
{
  "status": "success",
  "symbol": "AAPL",
  "message": "Bull-bear debate completed for AAPL",
  "rounds_completed": 2,
  "output_file": "/app/debate_points.json",
  "timestamp": "2025-11-18T10:30:00.000000"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T10:30:00.000000",
  "pathway_api": {
    "url": "http://localhost:8000",
    "status": "connected"
  }
}
```

### GET /
API information and available endpoints.

## 📁 Project Structure

```
bullbear/
├── bull_bear_main.py          # FastAPI server
├── bull_bear_graph.py          # LangGraph workflow
├── facilitator_main.py         # Pathway facilitator processor
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Service orchestration
├── .env.example                # Environment template
├── README.md                   # This file
│
├── all_agents/                 # Agent implementations
│   └── researchers/
│       ├── bull_researcher.py  # Bullish analyst
│       ├── bear_researcher.py  # Bearish analyst
│       └── researcher_tools.py # Pathway retrieval tools
│
├── A-mem/                      # Agentic Memory System
│   └── agentic_memory/
│
├── reports/                    # Generated reports (volume)
│   └── {SYMBOL}/
│       └── facilitator_report.md
│
└── debate_data/                # Debate outputs (volume)
    ├── debate_points.json
    └── debate_points.jsonl
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenRouter API key | Required |
| `PATHWAY_API_URL` | Pathway reports API URL | `http://localhost:8000` |
| `LLM_MODEL` | LLM model to use | `openai/gpt-4o-mini` |
| `LLM_TEMPERATURE` | LLM temperature | `0.7` |
| `DEFAULT_MAX_ROUNDS` | Default debate rounds | `2` |

### Docker Volumes

- `./reports` - Facilitator reports storage
- `./debate_data` - Debate points storage
- `./all_agents` - Agent code (dev mode)
- `./A-mem` - Agentic memory storage

## 🧪 Testing

```bash
# Run test workflow
python test_workflow.py
```

This creates mock debate data and tests the complete pipeline.

## 🔄 Complete Workflow Example

```bash
# 1. Ensure Pathway API is running
curl http://localhost:8000/health

# 2. Trigger debate for AAPL
curl -X POST http://localhost:8001/begin_debate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "max_rounds": 2}'

# Output files created:
# - debate_points.json      (Full debate transcript)
# - debate_points.jsonl     (Pathway format)

# 3. Facilitator processes automatically
# Check logs: docker-compose logs facilitator

# 4. View facilitator report
cat reports/AAPL/facilitator_report.md
```

## 🐳 Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f bullbear-api
docker-compose logs -f facilitator

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Rebuild images
docker-compose build --no-cache

# Check service status
docker-compose ps
```

## 🔍 Monitoring

### Health Checks

```bash
# Bull-Bear API health
curl http://localhost:8001/health

# Check if Pathway API is reachable
curl http://localhost:8000/health
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f bullbear-api
docker-compose logs -f facilitator
```

## 🛠️ Development

### Running Without Docker

```bash
# Terminal 1: Start Bull-Bear API
python bull_bear_main.py

# Terminal 2: Start Facilitator (after debate completes)
python facilitator_main.py
```

### Adding New Agents

1. Create agent in `all_agents/researchers/`
2. Follow the bull/bear researcher pattern
3. Update graph in `bull_bear_graph.py`

### Customizing Reports

Edit prompts in:
- `bull_bear_graph.py` - Debate agent prompts
- `facilitator_main.py` - Facilitator summary prompts

## 📊 Output Files

### debate_points.json
Full debate transcript with metadata:
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-11-18T10:30:00",
  "rounds_completed": 2,
  "total_exchanges": 4,
  "bull_history": "...",
  "bear_history": "...",
  "full_debate_transcript": "...",
  "summary": {...}
}
```

### facilitator_report.md
Balanced summary with:
- Executive Summary
- Key Arguments (Bull & Bear)
- Consensus & Divergence
- Facilitator's Assessment
- Trading Recommendations
- Risk Considerations

## 🤝 Integration

This service integrates with:
- **Pathway API** (port 8000) - Source of analysis reports
- **Kafka Network** - Shared network for microservices
- **A-Mem** - Agentic memory for historical context

## 📝 Dependencies

Key packages:
- `langgraph` - Graph orchestration
- `pathway` - Streaming processing
- `fastapi` - API framework
- `httpx` - HTTP client
- `python-dotenv` - Environment management

See `requirements.txt` for complete list.

## 🐛 Troubleshooting

**Issue**: Cannot connect to Pathway API
```bash
# Solution: Ensure Pathway services are running
docker-compose -f ../pathway/docker-compose.yml ps
```

**Issue**: LLM not responding
```bash
# Solution: Check API key and OpenRouter status
echo $OPENAI_API_KEY
curl https://openrouter.ai/api/v1/models
```

**Issue**: Facilitator not generating reports
```bash
# Solution: Check if debate_points.jsonl exists and is valid
cat debate_points.jsonl | jq .
```

## 📄 License

Part of the Pathway_InterIIT project.

## 🙏 Credits

Built using:
- [Pathway](https://pathway.com/) - Streaming data processing
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
