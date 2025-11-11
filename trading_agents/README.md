# Trading Agents - Multi-Agent Trading System

AI-powered multi-agent trading system using LangGraph for orchestrating complex trading decisions through collaborative agent debate, risk analysis, and signal generation.

## 📋 Overview

This system implements a sophisticated multi-agent architecture where specialized AI agents collaborate to:
- **Research**: Bull vs Bear debate on investment thesis
- **Trade**: Synthesize research into investment plans
- **Analyze Risk**: Multi-perspective risk evaluation
- **Manage**: Final position sizing and signal generation

Built with:
- **LangGraph**: Agent orchestration and state management
- **MongoDB**: Conversation checkpointing and persistence
- **Redis Queue (RQ)**: Asynchronous job processing
- **FastAPI**: REST API for workflow execution
- **PostgreSQL**: Storage for reports and signals

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    User Request (API)                      │
│                  POST /execute/{symbol}                    │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  Redis Queue   │ (Job queuing)
            └────────┬───────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│                    Worker Process                          │
│  1. Fetch reports from Pathway API                        │
│  2. Initialize LangGraph workflow                          │
│  3. Execute multi-agent pipeline                           │
│  4. Store results in PostgreSQL                            │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│              LangGraph Agent Workflow                      │
│                                                            │
│  ┌───────────┐           ┌───────────┐                   │
│  │   Bull    │  ←────→   │   Bear    │                   │
│  │Researcher │  (Debate) │ Researcher│                   │
│  └─────┬─────┘           └─────┬─────┘                   │
│        │                       │                          │
│        └───────────┬───────────┘                          │
│                    ▼                                       │
│             ┌─────────────┐                               │
│             │   Trader    │                               │
│             └──────┬──────┘                               │
│                    │                                       │
│          ┌─────────┴─────────┐                           │
│          ▼         ▼         ▼                           │
│    ┌─────────┐ ┌────────┐ ┌──────────┐                 │
│    │ Risky   │ │Neutral │ │  Safe    │                 │
│    │ Analyst │ │Analyst │ │ Analyst  │                 │
│    └────┬────┘ └───┬────┘ └────┬─────┘                 │
│         └──────────┼───────────┘                         │
│                    ▼                                      │
│          ┌──────────────────┐                            │
│          │  Risk Manager    │                            │
│          └────────┬─────────┘                            │
│                   │                                       │
│                   ▼                                       │
│          ┌──────────────────┐                            │
│          │  Final Manager   │                            │
│          └────────┬─────────┘                            │
│                   │                                       │
└───────────────────┼───────────────────────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  Trade Signal │
            │   (JSON)      │
            └───────────────┘
```

## 📁 Structure

```
trading_agents/
├── all_agents/             # Agent implementations
│   ├── researchers/
│   │   ├── bull_researcher.py     # Bull case advocate
│   │   └── bear_researcher.py     # Bear case advocate
│   ├── trader/
│   │   └── trader.py              # Investment plan synthesis
│   ├── risk_mngt/
│   │   ├── aggresive_debator.py   # Risky perspective
│   │   ├── neutral_debator.py     # Balanced perspective
│   │   └── conservative_debator.py # Safe perspective
│   ├── managers/
│   │   ├── risk_manager.py        # Risk assessment
│   │   └── final_manager.py       # Trade signal generation
│   └── utils/
│       ├── agent_state.py         # State schema
│       ├── llm.py                 # LLM configuration
│       └── sample.py              # Fallback data
│
├── graph/                  # LangGraph workflow
│   ├── setup.py               # Graph construction
│   ├── propagation.py         # State propagation
│   └── conditional_logic.py   # Routing logic
│
├── redis_queue/            # Job queue system
│   ├── task_queue.py          # Job enqueueing
│   └── worker.py              # Background worker
│
├── api/                    # FastAPI server
│   └── fastapi_server.py      # REST endpoints
│
├── utils/                  # Utilities
│   └── reports_client.py      # Pathway API client
│
├── run_workflow.py         # Workflow execution entry point
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🚀 Quick Start

### Prerequisites
```bash
OPENAI_API_KEY=your_openai_key
PATHWAY_API_URL=http://pathway-reports-api:8000
MONGODB_URI=mongodb://mongo:27017
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_HOST=redis
REDIS_PORT=6379
```

### Environment Configuration

Create `trading_agents/.env`:
```bash
# LLM
OPENAI_API_KEY=your_openai_api_key

# Pathway API
PATHWAY_API_URL=http://pathway-reports-api:8000
USE_FALLBACK_DATA=false  # Use sample data if reports unavailable

# MongoDB (LangGraph checkpointing)
MONGODB_URI=mongodb://mongo:27017/trading_agents

# PostgreSQL (Reports storage)
DATABASE_URL=postgresql://user:password@postgres:5432/trading_db

# Redis (Job queue)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1

# Agent Configuration
MAX_DEBATE_ROUNDS=3
MIN_DEBATE_ROUNDS=1
AGENT_TEMPERATURE=0.7
```

### Docker Deployment

```bash
# Start trading agents
docker-compose up -d

# View logs
docker-compose logs -f trading-agents-api
docker-compose logs -f trading-agents-worker

# Check health
curl http://localhost:8001/health
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start worker (in one terminal)
python redis_queue/worker.py

# Start API (in another terminal)
uvicorn api.fastapi_server:app --reload --port 8001

# Or run workflow directly
python run_workflow.py
```

## 🤖 Agent System

### Agent Roles & Responsibilities

#### 1. Bull Researcher
**Purpose**: Advocate for buying/holding the stock

**Analysis Focus**:
- Growth potential and market opportunities
- Competitive advantages
- Positive financial indicators
- Favorable news and sentiment
- Counter-arguments to bearish concerns

**Input**: 
- Market report
- Sentiment report
- News report
- Fundamentals report
- Bear researcher's previous argument

**Output**: 
- Bullish investment thesis
- Evidence-based arguments
- Rebuttals to bear case

**Prompt Strategy**:
```python
"""You are a Bull Analyst advocating for investing in {symbol}. 
Build a strong case emphasizing:
- Growth potential
- Competitive advantages
- Positive indicators
Counter the bear's arguments with data and reasoning."""
```

#### 2. Bear Researcher
**Purpose**: Advocate for selling/avoiding the stock

**Analysis Focus**:
- Risks and challenges
- Competitive threats
- Concerning financial metrics
- Negative news and sentiment
- Market headwinds

**Input**:
- Market report
- Sentiment report
- News report
- Fundamentals report
- Bull researcher's previous argument

**Output**:
- Bearish investment thesis
- Risk identification
- Rebuttals to bull case

**Prompt Strategy**:
```python
"""You are a Bear Analyst cautioning against investing in {symbol}.
Highlight:
- Risks and red flags
- Valuation concerns
- Negative indicators
Challenge the bull's thesis with critical analysis."""
```

#### 3. Trader
**Purpose**: Synthesize debate into actionable investment plan

**Analysis Focus**:
- Integrate bull and bear perspectives
- Identify consensus and conflicts
- Formulate balanced recommendation
- Suggest position sizing strategy

**Input**:
- Complete bull/bear debate history
- All research reports

**Output**:
- Investment plan (BUY/SELL/HOLD)
- Reasoning and key factors
- Position sizing suggestions

**Prompt Strategy**:
```python
"""You are a Trader synthesizing the bull/bear debate.
Analyze:
- Strength of each argument
- Risk/reward balance
- Conviction level
Generate: BUY/SELL/HOLD recommendation with reasoning."""
```

#### 4. Risk Analysts (3 Perspectives)

**Aggressive Analyst**:
- High risk tolerance
- Growth-focused
- Larger position sizes
- Shorter stop losses

**Neutral Analyst**:
- Balanced approach
- Moderate risk tolerance
- Standard position sizing
- Reasonable stops

**Conservative Analyst**:
- Low risk tolerance
- Capital preservation focus
- Smaller positions
- Wide stop losses

**Input**: Trader's investment plan + all reports

**Output**: Risk perspective with:
- Position size recommendation
- Stop loss suggestion
- Risk assessment
- Concerns and considerations

#### 5. Risk Manager
**Purpose**: Evaluate all risk perspectives and set position

**Analysis Focus**:
- Synthesize 3 risk analyst views
- Balance risk/reward
- Account for portfolio context
- Set concrete risk parameters

**Input**:
- Trader plan
- Aggressive analyst view
- Neutral analyst view
- Conservative analyst view
- All research reports

**Output**:
- Final risk assessment
- Position size determination
- Stop loss level
- Risk justification

#### 6. Final Manager
**Purpose**: Generate executable trade signal

**Analysis Focus**:
- Integrate all previous analyses
- Convert to precise trade parameters
- Ensure signal completeness
- Validate feasibility

**Input**: 
- All agent outputs
- Current portfolio state
- Account balance

**Output**: Structured trade signal
```json
{
  "symbol": "AAPL",
  "signal": "buy",
  "quantity": 50,
  "profit_target": 185.50,
  "stop_loss": 172.30,
  "invalidation_condition": "Break below 170 support",
  "leverage": 10,
  "confidence": 0.78,
  "risk_usd": 325.00
}
```

### Debate Mechanism

#### Dynamic Rounds
```python
# Debate continues until consensus or max rounds
def should_continue_debate(state):
    round_num = state["investment_debate_state"]["count"]
    
    if round_num < MIN_DEBATE_ROUNDS:
        return "continue"  # Force minimum rounds
    
    if round_num >= MAX_DEBATE_ROUNDS:
        return "finish"   # Cap at maximum
    
    # Check for consensus (via LLM)
    consensus = llm_evaluate_consensus(debate_history)
    return "finish" if consensus else "continue"
```

#### State Management
```python
class AgentState(TypedDict):
    # Core data
    company_of_interest: str
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str
    
    # Debate tracking
    investment_debate_state: dict  # {history, count, last_speaker}
    
    # Agent outputs
    trader_investment_plan: str
    risky_analyst_view: str
    neutral_analyst_view: str
    safe_analyst_view: str
    final_trade_decision: str
    
    # Portfolio context
    current_position_size: int
    account_balance: float
```

## 🔄 Workflow Execution

### Full Pipeline

```
1. API receives request: POST /execute/AAPL
2. Job enqueued in Redis
3. Worker picks up job
4. Fetch reports from Pathway API
5. Initialize LangGraph with reports
6. Execute agent workflow:
   a. Bull Researcher → Bear Researcher (debate)
   b. Check consensus
   c. If not converged, repeat debate
   d. Once converged → Trader
   e. Trader → 3 Risk Analysts (parallel → sequential)
   f. Risk Analysts → Risk Manager
   g. Risk Manager → Final Manager
   h. Final Manager → Trade Signal
7. Store signal in PostgreSQL
8. Return job result
```

### Workflow Graph (LangGraph)

```python
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("bull_researcher", bull_node)
workflow.add_node("bear_researcher", bear_node)
workflow.add_node("trader", trader_node)
workflow.add_node("risky_analyst", risky_node)
workflow.add_node("neutral_analyst", neutral_node)
workflow.add_node("safe_analyst", safe_node)
workflow.add_node("risk_judge", risk_manager_node)
workflow.add_node("final_manager", final_manager_node)

# Define edges
workflow.add_edge(START, "bull_researcher")

# Conditional debate routing
workflow.add_conditional_edges(
    "bull_researcher",
    should_continue_debate,
    {"bear_researcher": "bear_researcher", "trader": "trader"}
)

workflow.add_conditional_edges(
    "bear_researcher",
    should_continue_debate,
    {"bull_researcher": "bull_researcher", "trader": "trader"}
)

# Sequential risk analysis
workflow.add_edge("trader", "risky_analyst")
workflow.add_edge("risky_analyst", "neutral_analyst")
workflow.add_edge("neutral_analyst", "safe_analyst")
workflow.add_edge("safe_analyst", "risk_judge")
workflow.add_edge("risk_judge", "final_manager")
workflow.add_edge("final_manager", END)

# Compile with MongoDB checkpointing
app = workflow.compile(checkpointer=MongoDBSaver(...))
```

### Checkpointing

MongoDB stores conversation state for:
- **Resume capability**: Restart failed jobs
- **Inspection**: Debug agent conversations
- **Audit trail**: Review decision history

```python
# Save checkpoint after each agent
checkpointer = MongoDBSaver(
    connection_string=MONGODB_URI,
    db_name="trading_agents"
)

# Use in workflow
config = {"configurable": {"thread_id": f"{symbol}_{date}"}}
result = app.invoke(initial_state, config=config)
```

## 🌐 API Endpoints

### POST `/execute/{symbol}`
Trigger trading workflow for a symbol

```bash
curl -X POST http://localhost:8001/execute/AAPL

# Response
{
    "status": "queued",
    "symbol": "AAPL",
    "job_id": "abc-123-def",
    "message": "Trading workflow job queued successfully"
}
```

**Query Parameters**:
- `use_fallback=true` - Use sample data if reports unavailable

### GET `/job/{job_id}`
Check job status

```bash
curl http://localhost:8001/job/abc-123-def

# Response
{
    "job_id": "abc-123-def",
    "status": "finished",
    "result": {
        "symbol": "AAPL",
        "signal": "buy",
        "quantity": 50,
        ...
    },
    "enqueued_at": "2025-11-11T10:00:00Z",
    "started_at": "2025-11-11T10:00:05Z",
    "ended_at": "2025-11-11T10:02:30Z"
}
```

**Job Statuses**:
- `queued` - Waiting for worker
- `started` - Currently processing
- `finished` - Completed successfully
- `failed` - Execution error

### GET `/signals/{symbol}`
Get latest trade signal

```bash
curl http://localhost:8001/signals/AAPL

# Response (most recent signal)
{
    "id": 123,
    "symbol": "AAPL",
    "signal": "buy",
    "quantity": 50,
    "profit_target": 185.50,
    "stop_loss": 172.30,
    "invalidation_condition": "Break below 170",
    "leverage": 10,
    "confidence": 0.78,
    "risk_usd": 325.00,
    "timestamp": "2025-11-11T10:02:30Z"
}
```

### GET `/reports/{symbol}/{report_type}`
Get specific agent report

```bash
# Available report types:
# bull_researcher, bear_researcher, trader,
# risky_analyst, neutral_analyst, safe_analyst,
# risk_manager, final_manager

curl http://localhost:8001/reports/AAPL/bull_researcher

# Response
{
    "id": 456,
    "graph_id": "AAPL_2025-11-11_10-00-00",
    "symbol": "AAPL",
    "report_type": "bull_researcher",
    "timestamp": "2025-11-11T10:00:15Z",
    "report_body": "# Bull Case for AAPL\n\n..."
}
```

### GET `/reports/{symbol}/all`
Get all reports and signals for symbol

```bash
curl http://localhost:8001/reports/AAPL/all

# Response
{
    "symbol": "AAPL",
    "input_reports": {
        "fundamental_report": "...",
        "market_report": "...",
        "news_report": "...",
        "sentiment_report": "...",
        "source": "pathway_api"
    },
    "agent_reports": [
        {"report_type": "bull_researcher", "report_body": "..."},
        {"report_type": "bear_researcher", "report_body": "..."},
        ...
    ],
    "trade_signals": [
        {"signal": "buy", "quantity": 50, ...}
    ]
}
```

### GET `/health`
Health check

```bash
curl http://localhost:8001/health

# Response
{
    "status": "healthy",
    "timestamp": "2025-11-11T10:00:00Z",
    "services": {
        "database": "connected",
        "redis": "connected",
        "pathway_api": "available"
    }
}
```

## 🗄️ Data Storage

### PostgreSQL Schema

```sql
-- Agent reports table
CREATE TABLE graph_reports (
    id SERIAL PRIMARY KEY,
    graph_id VARCHAR(255),
    symbol VARCHAR(10) NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    report_body TEXT NOT NULL
);

-- Trade signals table
CREATE TABLE trade_signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    signal VARCHAR(10) NOT NULL,  -- 'buy', 'sell', 'hold'
    quantity INTEGER NOT NULL,
    profit_target FLOAT NOT NULL,
    stop_loss FLOAT NOT NULL,
    invalidation_condition TEXT,
    leverage INTEGER,
    confidence FLOAT,
    risk_usd FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Input reports cache (optional)
CREATE TABLE input_reports (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, report_type)
);
```

## 🧪 Testing

### Test Complete Workflow

```bash
# Direct execution (bypasses queue)
python run_workflow.py

# Prompts for symbol input
# Enter: AAPL

# With fallback data
USE_FALLBACK_DATA=true python run_workflow.py
```

### Test via API

```bash
# Queue job
JOB_ID=$(curl -s -X POST http://localhost:8001/execute/AAPL | jq -r .job_id)

# Poll status
watch -n 2 "curl -s http://localhost:8001/job/$JOB_ID | jq"

# Get result
curl http://localhost:8001/signals/AAPL | jq
```

### Inspect MongoDB Checkpoints

```bash
# Connect to MongoDB
docker exec -it mongo mongosh

use trading_agents

# List checkpoints
db.checkpoints.find({}, {thread_id: 1, namespace: 1})

# View specific checkpoint
db.checkpoints.findOne({thread_id: "AAPL_2025-11-11_10-00-00"})
```

## 📈 Performance

### Execution Time
- Bull/Bear debate: 30-60 seconds (per round)
- Complete workflow: 2-5 minutes
- Depends on:
  - Number of debate rounds (1-3)
  - LLM response time
  - Report complexity

### Resource Usage
- CPU: 10-20% per worker
- Memory: 300-500 MB per worker
- MongoDB: ~1-2 MB per workflow run
- PostgreSQL: ~10 KB per signal

### Scalability
- **Horizontal**: Add more workers for parallel processing
- **Queue depth**: Redis handles thousands of jobs
- **Concurrent workflows**: Multiple symbols simultaneously

## 🔧 Configuration

### Debate Parameters

```python
# In conditional_logic.py
MIN_DEBATE_ROUNDS = 1  # Minimum rounds before checking consensus
MAX_DEBATE_ROUNDS = 3  # Maximum rounds regardless

# Consensus detection (optional)
def check_consensus(debate_history):
    # LLM evaluates if bull/bear have converged
    # Return True to end debate early
```

### LLM Configuration

```python
# In all_agents/utils/llm.py
chat_model = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7,  # Higher = more creative
    api_key=os.getenv("OPENAI_API_KEY"),
)

# For different agent types
quick_thinking_llm = llms.OpenAIChat(model="gpt-4o-mini", temperature=0.7)
deep_thinking_llm = llms.OpenAIChat(model="gpt-4o", temperature=0.3)
```

### Fallback Data

```python
# Enable sample data when Pathway API unavailable
USE_FALLBACK_DATA=true

# Or in code
reports = fetch_reports_from_pathway(symbol, use_fallback=True)
```

## 🛡️ Error Handling

### Pathway API Unavailable
```python
# Automatic fallback to sample data (if enabled)
if not client.health_check():
    if use_fallback:
        return sample_reports
    else:
        raise ConnectionError("Pathway API unavailable")
```

### LLM API Failures
```python
# Retry logic with exponential backoff
@retry(max_attempts=3, backoff=2.0)
def call_llm(messages):
    return llm(messages)
```

### Job Failures
```python
# Redis Queue automatic retry
job = q.enqueue(
    workflow_fn,
    retry=Retry(max=3),
    failure_ttl=86400  # Keep failed jobs 24h for inspection
)
```

### Database Errors
```python
# Graceful degradation
try:
    store_signal(signal)
except psycopg2.Error as e:
    logger.error(f"DB error: {e}")
    # Signal still returned to user
```

## 🔗 Integration

### Consumes From
- [pathway/api](../pathway/README.md) - AI analysis reports via HTTP

### Integration Points
- **REST API**: Trigger workflows via HTTP
- **Redis Queue**: Asynchronous execution
- **PostgreSQL**: Signal storage for other systems
- **MongoDB**: Audit trail and debugging

## 📚 Dependencies

See `requirements.txt`:
- `langgraph` - Agent orchestration
- `langgraph-checkpoint-mongodb` - State persistence
- `pymongo` - MongoDB client
- `psycopg2-binary` - PostgreSQL client
- `redis` - Redis client
- `rq` - Redis Queue
- `fastapi` - API framework
- `uvicorn` - ASGI server
- `requests` - HTTP client

## 🤝 Contributing

To add a new agent:

1. Create agent file in `all_agents/<category>/`
2. Implement agent function with state signature
3. Register in `graph/setup.py`
4. Add to workflow graph
5. Update `AgentState` if new fields needed
6. Add database schema for new outputs (if any)

Example:
```python
# all_agents/new/my_agent.py
def create_my_agent(llm):
    def my_node(state, name):
        # Access state
        data = state["some_field"]
        
        # Process with LLM
        prompt = [{"role": "user", "content": f"Analyze: {data}"}]
        response = llm(prompt)
        
        # Return state updates
        return {"my_output": response, "sender": name}
    
    return functools.partial(my_node, name="My Agent")
```
