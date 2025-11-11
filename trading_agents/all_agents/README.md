# Trading Agents - Agent Implementations

Specialized AI agents for collaborative trading analysis and decision-making.

## 📋 Overview

This directory contains all agent implementations organized by role:
- **researchers/** - Bull and Bear debate agents
- **trader/** - Investment plan synthesis agent
- **risk_mngt/** - Risk analysis from multiple perspectives
- **managers/** - Risk and final decision managers
- **utils/** - Shared utilities (state, LLM config, sample data)

## 🤖 Agent Categories

### Researchers (Bull vs Bear Debate)

**Bull Researcher** (`researchers/bull_researcher.py`)
- Advocates for buying/holding
- Highlights growth potential
- Emphasizes competitive advantages
- Counters bearish arguments

**Bear Researcher** (`researchers/bear_researcher.py`)
- Advocates for selling/avoiding
- Identifies risks and challenges
- Highlights valuation concerns
- Counters bullish arguments

**Debate Mechanism**:
```python
# Dynamic rounds until consensus
Bull → Bear → Bull → Bear → ... → Trader
      (1-3 rounds based on convergence)
```

### Trader (Investment Synthesis)

**Trader** (`trader/trader.py`)
- Synthesizes bull/bear debate
- Identifies consensus points
- Formulates balanced recommendation
- Outputs: BUY/SELL/HOLD with reasoning

### Risk Analysts (Multi-Perspective)

**Aggressive Analyst** (`risk_mngt/aggresive_debator.py`)
- High risk tolerance
- Growth-focused
- Larger position sizes
- Aggressive stops

**Neutral Analyst** (`risk_mngt/neutral_debator.py`)
- Balanced approach
- Moderate risk tolerance
- Standard position sizing
- Reasonable stops

**Conservative Analyst** (`risk_mngt/conservative_debator.py`)
- Low risk tolerance
- Capital preservation
- Smaller positions
- Wide stop losses

### Managers (Final Decision)

**Risk Manager** (`managers/risk_manager.py`)
- Synthesizes 3 risk perspectives
- Sets position size
- Determines stop loss
- Validates risk/reward

**Final Manager** (`managers/final_manager.py`)
- Integrates all analyses
- Generates executable signal
- Ensures completeness
- Outputs structured JSON

## 📊 Agent Flow

```
Input Reports (Market, News, Sentiment, Fundamentals)
                    ↓
        ┌───────────────────────┐
        │  Bull vs Bear Debate  │
        │   (1-3 rounds)        │
        └───────────┬───────────┘
                    ↓
            ┌──────────────┐
            │    Trader    │
            │  (Synthesis) │
            └──────┬───────┘
                   ↓
    ┌──────────────┼──────────────┐
    ↓              ↓              ↓
┌────────┐   ┌─────────┐   ┌────────────┐
│ Risky  │   │ Neutral │   │    Safe    │
│Analyst │   │ Analyst │   │  Analyst   │
└────┬───┘   └────┬────┘   └──────┬─────┘
     └────────────┼───────────────┘
                  ↓
         ┌────────────────┐
         │ Risk Manager   │
         │ (Position Size)│
         └────────┬───────┘
                  ↓
         ┌────────────────┐
         │ Final Manager  │
         │ (Trade Signal) │
         └────────────────┘
```

## 🔧 Agent State

All agents share a common state structure defined in `utils/agent_state.py`:

```python
class AgentState(TypedDict):
    # Input reports
    company_of_interest: str
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str
    
    # Debate state
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
    
    # Routing
    sender: str
```

## 💬 Agent Communication

Each agent:
1. Receives state with all previous outputs
2. Processes relevant information
3. Returns state updates (new fields or modifications)
4. Passes to next agent via LangGraph

Example agent pattern:
```python
def create_agent(llm):
    def agent_node(state, name):
        # 1. Extract inputs
        symbol = state["company_of_interest"]
        reports = {
            "market": state["market_report"],
            "news": state["news_report"],
            # ...
        }
        
        # 2. Process with LLM
        prompt = create_prompt(symbol, reports)
        response = llm(prompt)
        
        # 3. Return state update
        return {
            "agent_output_field": response,
            "sender": name
        }
    
    return functools.partial(agent_node, name="Agent Name")
```

## 🧪 Testing Individual Agents

### Test Bull Researcher
```python
from all_agents.researchers.bull_researcher import create_bull_researcher
from all_agents.utils.llm import chat_model

# Create agent
bull_agent = create_bull_researcher(chat_model)

# Mock state
state = {
    "company_of_interest": "AAPL",
    "market_report": "Strong uptrend...",
    "sentiment_report": "Positive sentiment...",
    "news_report": "Earnings beat...",
    "fundamentals_report": "Solid financials...",
    "investment_debate_state": {
        "history": "",
        "bear_history": "Initial concern...",
        "count": 1,
        "last_speaker": "bear"
    }
}

# Execute
result = bull_agent(state)
print(result["investment_debate_state"]["bull_history"])
```

### Test Trader
```python
from all_agents.trader.trader import create_trader

trader_agent = create_trader(chat_model)

state = {
    "company_of_interest": "AAPL",
    "market_report": "...",
    "sentiment_report": "...",
    "news_report": "...",
    "fundamentals_report": "...",
    "investment_debate_state": {
        "history": "Bull: ... Bear: ... Bull: ... Bear: ...",
        "count": 2
    }
}

result = trader_agent(state)
print(result["trader_investment_plan"])
```

## 📝 Agent Prompts

Each agent has a carefully crafted system prompt:

### Bull Researcher Prompt Structure
```
Role: Bull Analyst advocating for {symbol}
Task: Build evidence-based case for investment

Focus:
- Growth potential
- Competitive advantages
- Positive indicators
- Counter bear arguments

Context:
- Research reports
- Bear's last argument
- Debate history

Output: Compelling bull thesis with rebuttals
```

### Risk Analyst Prompt Structure
```
Role: {Aggressive/Neutral/Conservative} Risk Analyst
Task: Evaluate trader's plan from {risk perspective}

Considerations:
- Position sizing ({large/moderate/small})
- Stop loss placement ({tight/moderate/wide})
- Risk/reward ratio
- Portfolio impact

Output: Risk assessment with recommendations
```

### Final Manager Prompt Structure
```
Role: Final Manager generating trade signal
Task: Synthesize all analyses into executable signal

Inputs:
- Trader recommendation
- Risk manager decision
- All research reports
- Portfolio context

Output: JSON trade signal with:
{
  "signal": "buy/sell/hold",
  "quantity": int,
  "profit_target": float,
  "stop_loss": float,
  "leverage": int,
  "confidence": float,
  "risk_usd": float
}
```

## 🔧 Configuration

### LLM Settings
In `utils/llm.py`:
```python
chat_model = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7,  # Creative for debate
    api_key=os.getenv("OPENAI_API_KEY")
)
```

### Sample Data
In `utils/sample.py`:
```python
# Fallback data when Pathway API unavailable
market_report_example = "..."
sentiment_report_example = "..."
news_report_example = "..."
fundamentals_report_example = "..."
```

## 📈 Performance

### Execution Time per Agent
- Bull/Bear Researcher: 10-20 seconds each
- Trader: 15-25 seconds
- Risk Analysts: 8-12 seconds each
- Risk Manager: 15-20 seconds
- Final Manager: 10-15 seconds

**Total**: 2-5 minutes for complete workflow

### LLM Token Usage
- Debate agents: ~2000 tokens/response
- Trader: ~3000 tokens/response
- Risk analysts: ~1500 tokens/response
- Managers: ~2500 tokens/response

## 🛡️ Error Handling

### LLM Failures
```python
try:
    response = llm(prompt)
except Exception as e:
    logger.error(f"LLM error in {agent_name}: {e}")
    response = "Analysis unavailable due to error"
```

### State Validation
```python
# Validate required fields
required = ["company_of_interest", "market_report", "news_report"]
for field in required:
    if field not in state:
        raise ValueError(f"Missing required field: {field}")
```

## 📚 Adding New Agent

1. Create agent file:
```python
# all_agents/new_category/new_agent.py
import functools
from all_agents.utils.llm import chat_model

def create_new_agent(llm):
    def agent_node(state, name):
        # Agent logic
        return {"new_output": "...", "sender": name}
    
    return functools.partial(agent_node, name="New Agent")
```

2. Register in workflow (`graph/setup.py`):
```python
from all_agents.new_category.new_agent import create_new_agent

# In GraphSetup.setup_graph()
new_agent = create_new_agent(self.quick_thinking_llm)
workflow.add_node("new_agent", new_agent)
workflow.add_edge("previous_agent", "new_agent")
```

3. Update state schema if needed (`utils/agent_state.py`):
```python
class AgentState(TypedDict):
    # ... existing fields
    new_agent_output: str  # Add new field
```

## 🔗 Related

- [../graph/](../graph/) - LangGraph workflow setup
- [../utils/](../utils/) - Shared utilities
- [../api/](../api/) - API endpoints triggering agents
