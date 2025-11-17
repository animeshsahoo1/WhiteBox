# Phase 2: Strategy Management System

AI-powered trading strategy orchestration system using Pathway, LLMs, and MCP.

## Architecture

```
Phase 1 Reports → Hypothesis Generator → MCP Server → Orchestrator → User
                      ↓                      ↓
                    Kafka              Risk Assessment
                                       Backtesting API
                                       Web Search (DDGS)
```

## Components

1. **Hypothesis Generator** (Pathway + OpenAI)
   - Reads 5 Phase 1 reports from Kafka
   - Synthesizes 5 market hypotheses via LLM
   - Outputs to Kafka for MCP consumption

2. **MCP Server** (Pathway MCP)
   - Exposes tools and resources:
     - `search_backtesting_api`: Search strategies
     - `assess_risk_all_tiers`: Get 3 risk assessments (LLM-based)
     - `web_search_strategy`: Find new strategies via DDGS
     - `get_current_hypotheses`: Latest hypotheses
     - `get_phase1_reports`: All Phase 1 intelligence
     - `get_market_conditions`: Current market state

3. **Orchestrator** (LangChain + MCP Client)
   - Classifies user queries
   - Coordinates MCP tools
   - Formats conversational responses
   - Manages conversation memory

## Installation

```bash
# Clone repository
cd phase2

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
psql -U postgres -f database/schema.sql
```

## Running Services

### With Docker Compose

```bash
cd docker
docker-compose up -d
```

### Manually

```bash
# Terminal 1: Hypothesis Generator
python -m phase2.run_hypothesis_generator

# Terminal 2: MCP Server
python -m phase2.run_mcp_server

# Terminal 3: Orchestrator (Interactive)
python -m phase2.run_orchestrator
```

## Usage Examples

### Interactive CLI

```
Green-Kedia> What should I trade now?

🤔 Processing...

**Based on Current Market Hypothesis:**
_Due to CEO insider buying of 500K shares, market seems bullish_ (Confidence: 88%)

## 📊 Recommended Strategies

### 1. **Moving Average Crossover** (Rank #1)
...
```

### Query Types

1. **Hypothesis-based**
   - "What should I trade now?"
   - "Recommend strategies for current market"

2. **General**
   - "Show me RSI strategies"
   - "Find momentum strategies"

3. **Risk-based**
   - "Give me low-risk strategies"
   - "Show aggressive approaches"

4. **Performance**
   - "What are top performing strategies?"
   - "Best win rate strategies"

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
POSTGRES_HOST=postgres
BACKTESTING_API_URL=http://backtesting-api:8000

# Optional
OPENAI_MODEL_HYPOTHESIS=gpt-4-turbo-preview
MCP_PORT=8080
```

### Kafka Topics

**Phase 1 Inputs:**
- `phase1.news_reports`
- `phase1.sentiment_reports`
- `phase1.fundamental_reports`
- `phase1.market_reports`
- `phase1.facilitator_reports`
- `phase1.market_data`

**Phase 2 Outputs:**
- `phase2.hypotheses`
- `phase2.market_conditions`

## Development

### Project Structure

```
phase2/
├── config/              # Settings and configuration
├── hypothesis_generator/ # LLM-based hypothesis synthesis
├── mcp_server/          # MCP tools and resources
│   ├── tools/           # Backtesting, risk, search
│   └── resources/       # Hypotheses, Phase 1, market
├── orchestrator/        # Main agent logic
├── database/            # SQL schemas
├── docker/              # Docker configs
└── tests/               # Unit tests
```

### Adding New MCP Tools

```python
from pathway.xpacks.llm.mcp_server import McpServable, McpServer
import pathway as pw

class MyTool(McpServable):
    class MySchema(pw.Schema):
        param1: str
    
    def my_handler(self, request: pw.Table) -> pw.Table:
        # Process request
        return request.select(result="...")
    
    def register_mcp(self, server: McpServer):
        server.tool("my_tool", request_handler=self.my_handler, schema=self.MySchema)
```

## Testing

```bash
# Unit tests
pytest tests/

# Integration test
python -m phase2.run_orchestrator
# Enter: "What should I trade now?"
```

## Monitoring

- **Logs**: `docker logs phase2-mcp-server -f`
- **MCP Health**: `http://localhost:8080/health`
- **Database**: `psql -U postgres -d trading_system`

## Troubleshooting

**Issue: No hypotheses available**
- Check Kafka topics: `kafka-console-consumer --topic phase2.hypotheses`
- Verify Phase 1 is running and producing reports

**Issue: Backtesting API timeout**
- Check `BACKTESTING_API_URL` in `.env`
- Verify API is running: `curl http://backtesting-api:8000/health`

**Issue: MCP connection refused**
- Ensure MCP server is running on port 8080
- Check firewall rules

## License

MIT License
