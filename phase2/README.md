# Phase 2: AI-Powered Trading Strategy Orchestrator

> **Conversational AI assistant that discovers, analyzes, backtests, and evaluates trading strategies using multi-agent reasoning and real-time market intelligence.**

---

## 🎯 Overview

Phase 2 is an intelligent trading strategy orchestrator built on **LangGraph** that provides:
- **Natural conversation interface** for strategy discovery and analysis
- **Multi-tier risk assessment** (No-Risk, Neutral, Aggressive) using specialized LLM agents
- **Automated hypothesis generation** from real-time market reports
- **Strategy backtesting** with performance metrics
- **Web-based strategy synthesis** when database searches fail

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Conversational Interface                      │
│  (Natural language chat → Extracts intent → Invokes workflow)   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator                        │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐     │
│  │  Classify  │→ │   Extract    │→ │  Search/Synthesize  │     │
│  │   Query    │  │   Strategy   │  │     Strategies      │     │
│  └────────────┘  └──────────────┘  └─────────────────────┘     │
│                                              │                   │
│  ┌────────────┐  ┌──────────────┐           │                   │
│  │  Generate  │← │   Backtest   │← ─────────┘                   │
│  │  Response  │  │   & Risk     │                                │
│  └────────────┘  └──────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────────┐ ┌──────────┐ ┌──────────────────┐
│ Hypothesis Gen   │ │ Risk Mgr │ │ Backtesting API  │
│ (MCP Server)     │ │ (MCP)    │ │ (Strategy Bank)  │
│ - Watches Phase1 │ │ - 3 LLMs │ │ - Returns Data   │
│ - Generates 5    │ │ - Parallel│ │                  │
│   hypotheses     │ │   Analysis│ │                  │
└──────────────────┘ └──────────┘ └──────────────────┘
```

---

## 📂 Component Breakdown

### 1. **Conversational Interface** (`orchestrator/conversational_interface.py`)
**What it does:**
- Natural language chat wrapper around LangGraph workflow
- Decides when to invoke full strategy analysis vs continue chatting
- Maintains conversation history and user preferences
- Extracts structured queries from casual conversation

**Key features:**
- **Intelligent routing**: Only invokes workflow when user is ready
- **Context extraction**: Builds formal query from chat history
- **Capability explanations**: Helps users understand what's possible

**Example flow:**
```
User: "I'm looking for low-risk strategies"
Bot: "Great! Do you prefer specific indicators like RSI or MACD?"
User: "RSI would be good"
Bot: [Invokes workflow with: "Find low-risk RSI strategies"]
```

---

### 2. **LangGraph Orchestrator** (`orchestrator/`)

#### **Graph Structure** (`graph.py`)
Defines the workflow with 12 nodes:
1. **classify_query** → Categorize user intent (5 types)
2. **extract_user_strategy** → Parse strategy from user input
3. **decide_hypothesis_need** → Check if market context needed
4. **fetch_hypotheses** → Get top 5 market hypotheses from MCP
5. **build_search_params** → Build strategy search filters
6. **search_strategy_bank** → Query database via FastAPI
7. **decide_web_search_need** → Check if strategies found
8. **synthesize_strategy_from_web** → LLM + web search creates strategy
9. **backtest_strategy** → Run backtest via API
10. **analyze_risk** → 3-tier parallel risk assessment
11. **generate_response** → Format comprehensive answer
12. **update_memory** → Save to conversation history

#### **Nodes** (`nodes.py`)
Implements each graph node as a function that processes `AgentState`:
- **Classification**: 5 query types (request_strategy, input_strategy, risk_based, hypothesis_based, performance)
- **Strategy extraction**: JSON parsing with fallbacks
- **Hypothesis integration**: Uses latest market conditions
- **Web synthesis**: LLM with DuckDuckGo search tool (max 2 searches)
- **Risk analysis**: Calls 3 LLM agents in parallel

#### **State** (`state.py`)
Maintains workflow state:
```python
{
  "user_query": str,           # Original question
  "query_type": str,           # Classification result
  "hypotheses": list,          # Market hypotheses
  "strategies_found": list,    # Search results
  "selected_strategy": dict,   # Final strategy
  "backtest_results": dict,    # Performance metrics
  "risk_analyses": dict,       # 3-tier assessments
  "final_response": str        # Generated answer
}
```

#### **Tools** (`tools.py`)
External integrations:
- **Hypothesis MCP**: `call_hypothesis_mcp()` → Top 5 hypotheses
- **Risk Analysis MCP**: `call_risk_analysis_mcp()` → 3 parallel LLM calls
- **Strategy API**: Search & backtest endpoints
- **Web Search**: DuckDuckGo for strategy synthesis

---

### 3. **Hypothesis Generator** (`hypothesis_generator/`)

**Purpose**: Continuously monitors Phase 1 facilitator reports and auto-generates 5 ranked market hypotheses.

#### **How it works** (`generator.py`)
1. **Watches facilitator report** endpoint (polls every 1s)
2. When facilitator changes → **fetches all other reports** (news, sentiment, fundamental, market)
3. **LLM synthesis**: GPT-4o-mini generates 5 hypotheses with:
   - Statement, confidence (0-1), evidence, risks, time horizon, action (BUY/SELL/HOLD)
4. **Caches to Redis** (no expiration) for fast retrieval
5. **Serves via MCP** for orchestrator consumption

**Key feature**: **Efficient polling** - only watches 1 endpoint, fetches others on-demand.

#### **API Server** (`app.py`)
REST endpoints for querying cached hypotheses:
- `GET /hypotheses/{symbol}` → Latest hypotheses
- `GET /hypotheses/{symbol}/metadata` → Last update time, count
- `GET /health` → Cache statistics

---

### 4. **Risk Managers** (`risk_managers/`)

**Purpose**: 3 independent LLM agents evaluate strategies with different risk philosophies.

#### **Architecture** (`risk_assessment.py`)
- **Input**: Symbol, strategy, risk_levels list
- **Processing**: 
  1. Fetches all Phase 1 reports (news, sentiment, fundamental, market, facilitator)
  2. Creates 3 parallel prompts (no-risk, neutral, aggressive)
  3. Invokes 3 LLM calls simultaneously
  4. Extracts JSON responses
  5. Concatenates into single response

#### **Risk Tiers** (`risk_managers_prompt.py`)

| Tier | Position Size | Stop Loss | Volatility Acceptance | Philosophy |
|------|---------------|-----------|----------------------|------------|
| **No-Risk** | 3-5% | 1.5-2.5% | VIX < 20 only | Capital preservation above all |
| **Neutral** | 8-15% | 4-6% | VIX 15-30 | Balanced risk-adjusted returns |
| **Aggressive** | 10-30% | 7-12% | Embraces VIX > 25 | Maximum returns, calculated risks |

**Each agent analyzes:**
- Market environment (volatility levels)
- Fundamental health (red flags)
- News risks (crisis indicators)
- Sentiment extremes
- Bull-Bear debate outcome
- Strategy technical merit

**Output format:**
```json
{
  "approval_status": "approved|conditional|rejected",
  "recommended_params": {
    "position_size_pct": 5.0,
    "stop_loss_pct": 2.0,
    "profit_target_pct": 8.0
  },
  "conviction_level": "high|medium|low",
  "reasoning": "...",
  "key_risks": [...],
  "conditions": [...]
}
```

---

### 5. **Backtesting API** (`backtesting/`)

**Current implementation**: Minimal FastAPI server returning hardcoded strategy data.

**Purpose**: Simulate strategy bank database and backtesting engine.

**Returns:**
- Strategy metadata (name, type, indicators)
- Performance metrics (total return, Sharpe ratio, max drawdown, win rate)
- Risk tier classification

**Future**: Replace with real backtesting engine and database.

---

## 🔄 Complete Workflow Example

**User query**: *"What should I trade now?"*

### Step-by-step:

1. **Conversational Interface**
   - Detects query is ready for analysis
   - Extracts: "Find strategies based on current market conditions"

2. **Classify Query**
   - Type: `hypothesis_based`

3. **Decide Hypothesis Need**
   - Decision: YES (query asks for "now")

4. **Fetch Hypotheses**
   - Calls MCP: Gets top 5 hypotheses
   - Example: "Stock likely to rally 5-8% due to CEO insider buying" (confidence: 0.85)

5. **Build Search Params**
   - Filters: `trend: "bullish"`, `time_window: "30d"`, `sort_by: "rank"`

6. **Search Strategy Bank**
   - Calls FastAPI: Returns 3 strategies
   - Selects top: "Momentum Breakout" (Sharpe: 2.1, win rate: 65%)

7. **Backtest Strategy**
   - Returns: Total return 35%, max drawdown -18%

8. **Analyze Risk** (Parallel)
   - **No-Risk Agent**: "REJECTED - Max drawdown exceeds 12% threshold"
   - **Neutral Agent**: "APPROVED - 12% position size, 5% stop-loss, conviction: MEDIUM"
   - **Aggressive Agent**: "APPROVED - 25% position size, 10% stop-loss, conviction: HIGH"

9. **Generate Response**
   - Synthesizes comprehensive report with:
     - Market context (hypothesis)
     - Strategy details
     - Backtest results
     - Risk analysis for all 3 tiers
     - Recommendation

10. **Update Memory**
    - Saves exchange to conversation history

---

## 🚀 Running Phase 2

### Prerequisites
```bash
# Environment variables (.env)
OPENAI_API_KEY=your_key
PATHWAY_LICENSE_KEY=your_key
SYMBOL=AAPL
REDIS_HOST=localhost
REDIS_PORT=6379
PATHWAY_API_HOST=localhost  # Phase 1 reports API
PATHWAY_API_PORT=9000
```

### Local Development
```bash
# 1. Start dependencies (Redis, Phase 1 APIs)
# 2. Run hypothesis generator
python -m phase2.hypothesis_generator.generator

# 3. Run risk manager MCP
python -m phase2.risk_managers.risk_assessment

# 4. Run backtesting API
python -m phase2.backtesting.backtesting_api

# 5. Run conversational orchestrator
python phase2/run_conversational_orchestrator.py
```

### Docker Compose
```bash
cd phase2
docker-compose up -d
```

**Services:**
- `hypothesis-generator`: Port 9000 (MCP)
- `mcp-server`: Port 8080 (Risk Manager MCP)
- `backtesting-api`: Port 8001
- `orchestrator`: Interactive terminal
- `postgres`: Port 5432 (conversation memory)
- `kafka`: Port 9092 (future use)

---

## 💬 Usage Examples

### 1. **General Strategy Search**
```
You: Show me momentum strategies
Bot: I found 3 momentum strategies. Top pick: "Momentum Breakout"
     - Sharpe: 2.1, Win rate: 65%
     - No-Risk: REJECTED (too volatile)
     - Neutral: APPROVED (12% position)
     - Aggressive: APPROVED (25% position, high conviction)
```

### 2. **User-Provided Strategy**
```
You: Analyze this: buy when RSI < 30 and MACD positive, sell at RSI > 70
Bot: [Extracts strategy]
     [Backtests]
     Results: Win rate 58%, Sharpe 1.45
     Risk Assessment:
     - No-Risk: APPROVED (3% position, tight 2% stop)
     - Neutral: APPROVED (10% position, 5% stop)
     - Aggressive: CONDITIONAL (reduce to 15%, watch for false signals)
```

### 3. **Market-Based Query**
```
You: What should I trade now?
Bot: Based on current hypothesis (bullish on tech, confidence 0.85):
     - Recommended: "Moving Average Crossover"
     - Current setup: Golden cross forming
     - All 3 risk tiers APPROVE
     - Suggested: Start with Neutral tier (12% position)
```

---

## 🛠️ Configuration (`config/settings.py`)

All components use Pydantic settings with `.env` overrides:

```python
orchestrator_settings.strategy_api_endpoint  # Backtesting API URL
orchestrator_settings.risk_analysis_mcp      # Risk Manager MCP URL
orchestrator_settings.hypothesis_mcp         # Hypothesis Generator MCP URL
orchestrator_settings.max_web_searches       # Web synthesis limit
orchestrator_settings.min_win_rate           # Strategy filter threshold
orchestrator_settings.default_time_window    # Backtest period
```

---

## 📊 Database Schema (`database/schema.sql`)

**PostgreSQL tables for memory:**
- `conversation_turns`: Full chat history
- `conversation_summaries`: Session summaries
- `user_profiles`: Preferences, interaction stats
- `strategy_feedback`: User ratings (optional)

**Purpose**: Enable personalization and long-term memory.

---

## 🔑 Key Design Decisions

1. **Conversational Layer**: Don't rush to invoke workflow - build context first
2. **Hypothesis Efficiency**: Poll only facilitator, fetch others on-demand
3. **Parallel Risk Analysis**: 3 independent LLM agents for diverse perspectives
4. **Web Synthesis Fallback**: Only when strategy bank empty (max 2 searches)
5. **No Expiration Caching**: Hypotheses persist until facilitator changes
6. **Modular MCP Architecture**: Each service (hypothesis, risk) is standalone

---

## 📈 Performance Considerations

- **Hypothesis caching**: Redis eliminates repeated LLM calls
- **Parallel risk analysis**: 3 LLM calls simultaneously (not sequential)
- **Efficient polling**: Pathway watches 1 endpoint, not 5
- **Lazy web search**: Only synthesize if database search fails
- **Conversation memory**: Keep last 5 exchanges for context

---

## 🔮 Future Enhancements

1. **Real backtesting engine**: Replace hardcoded API with actual historical testing
2. **Strategy bank database**: PostgreSQL with indexed strategies
3. **User profiles**: Personalized recommendations based on history
4. **Multi-symbol support**: Analyze portfolios, not just single stocks
5. **Live trading integration**: Execute approved strategies
6. **A/B testing**: Compare risk tier performance over time

---

## 🐛 Troubleshooting

**Issue**: Orchestrator hangs
- **Check**: Phase 1 reports API is running (port 9000)
- **Check**: Hypothesis MCP is accessible

**Issue**: Risk analysis returns empty
- **Check**: Risk Manager MCP is running (port 9001)
- **Check**: OpenAI API key is valid

**Issue**: Web synthesis fails
- **Check**: DuckDuckGo search not rate-limited
- **Check**: `max_web_searches` setting

---

## 📝 Summary

**Phase 2 = Intelligent Trading Assistant**

- 🗣️ **Conversational**: Natural language interface
- 🧠 **Multi-agent**: 3 risk tiers with specialized LLMs
- 📊 **Data-driven**: Integrates real-time market reports
- 🔍 **Autonomous**: Web search fallback
- ⚡ **Efficient**: Caching, parallel processing, smart polling

**Core value**: Transforms complex trading analysis into a simple conversation while maintaining rigorous multi-perspective risk assessment.
