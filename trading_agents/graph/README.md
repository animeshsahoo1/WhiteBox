# LangGraph Workflow Setup

LangGraph workflow configuration and orchestration for the multi-agent investment intelligence system.

## 📋 Overview

This directory contains the LangGraph graph construction, state propagation, and conditional routing logic that orchestrates the entire multi-agent workflow for investment analysis and hypothesis generation.

## 🗂️ Files

- **setup.py** - Graph construction and node registration
- **conditional_logic.py** - Routing decisions and flow control
- **propagation.py** - State management and propagation utilities

## 🏗️ Graph Architecture

### Workflow Structure

```python
# In setup.py
workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("bull_researcher", bull_node)
workflow.add_node("bear_researcher", bear_node)
workflow.add_node("trader", trader_node)
workflow.add_node("risky_analyst", risky_node)
workflow.add_node("neutral_analyst", neutral_node)
workflow.add_node("safe_analyst", safe_node)
workflow.add_node("risk_judge", risk_manager_node)
workflow.add_node("final_manager", final_manager_node)

# Edges (connections)
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

# Sequential flow after debate
workflow.add_edge("trader", "risky_analyst")
workflow.add_edge("risky_analyst", "neutral_analyst")
workflow.add_edge("neutral_analyst", "safe_analyst")
workflow.add_edge("safe_analyst", "risk_judge")
workflow.add_edge("risk_judge", "final_manager")
workflow.add_edge("final_manager", END)

# Compile with checkpointing
app = workflow.compile(checkpointer=MongoDBSaver(...))
```

### Visual Flow

```
START
  ↓
Bull Researcher
  ↓
  ├─→ Bear Researcher (if not converged)
  │     ↓
  │     └─→ Bull Researcher (if not converged)
  │           ↓
  └─→ Trader (if converged or max rounds)
        ↓
    Risky Analyst
        ↓
    Neutral Analyst
        ↓
    Safe Analyst
        ↓
    Risk Manager
        ↓
    Final Manager
        ↓
      END
```

## 🔄 Conditional Logic

### Debate Convergence Check

In `conditional_logic.py`:

```python
class ConditionalLogic:
    def should_continue_debate(self, state: AgentState) -> str:
        """Decide if debate should continue or move to trader"""
        
        debate_state = state["investment_debate_state"]
        round_num = debate_state["count"]
        last_speaker = debate_state.get("last_speaker", "")
        
        # Minimum rounds required
        if round_num < MIN_DEBATE_ROUNDS:
            return self._alternate_speaker(last_speaker)
        
        # Maximum rounds cap
        if round_num >= MAX_DEBATE_ROUNDS:
            return "trader"
        
        # Check consensus (optional LLM-based)
        # debate_history = debate_state["history"]
        # if self._has_consensus(debate_history):
        #     return "trader"
        
        # Continue alternating
        return self._alternate_speaker(last_speaker)
    
    def _alternate_speaker(self, last_speaker: str) -> str:
        """Alternate between bull and bear"""
        if last_speaker == "bull_researcher":
            return "bear_researcher"
        else:
            return "bull_researcher"
```

### Configuration

```python
# Debate parameters
MIN_DEBATE_ROUNDS = 1  # At least 1 round
MAX_DEBATE_ROUNDS = 3  # Cap at 3 rounds

# Optional: LLM-based consensus detection
def _has_consensus(debate_history: str) -> bool:
    """Use LLM to detect if bull/bear have converged"""
    prompt = f"""Analyze this debate:
    {debate_history}
    
    Have the bull and bear reached consensus? (yes/no)"""
    
    response = llm(prompt).lower()
    return "yes" in response
```

## 🔧 Graph Setup

### GraphSetup Class

In `setup.py`:

```python
class GraphSetup:
    """Handles graph setup and configuration"""
    
    def __init__(self, conditional_logic, checkpointer):
        self.conditional_logic = conditional_logic
        self.checkpointer = checkpointer
        self.quick_thinking_llm = None  # Set externally
        self.deep_thinking_llm = None   # Set externally
    
    def setup_graph(self):
        """Construct and compile the workflow graph"""
        
        # Create agent nodes
        bull_node = create_bull_researcher(self.quick_thinking_llm)
        bear_node = create_bear_researcher(self.quick_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)
        # ... other agents
        
        # Build workflow
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("bull_researcher", bull_node)
        # ... add other nodes
        
        # Add edges
        # ... configure routing
        
        # Compile
        return workflow.compile(checkpointer=self.checkpointer)
```

### Usage

```python
from graph.setup import GraphSetup
from graph.conditional_logic import ConditionalLogic
from langgraph.checkpoint.mongodb import MongoDBSaver

# Create components
conditional_logic = ConditionalLogic()
checkpointer = MongoDBSaver(connection_string=MONGODB_URI)

# Setup graph
setup = GraphSetup(conditional_logic, checkpointer)
setup.quick_thinking_llm = chat_model
setup.deep_thinking_llm = chat_model
app = setup.setup_graph()

# Execute workflow
result = app.invoke(initial_state, config={"configurable": {"thread_id": "AAPL_123"}})
```

## 💾 State Checkpointing

### MongoDB Saver

```python
from langgraph.checkpoint.mongodb import MongoDBSaver

checkpointer = MongoDBSaver(
    connection_string="mongodb://mongo:27017",
    db_name="intelligence_agents"
)

# Compile with checkpointing
app = workflow.compile(checkpointer=checkpointer)

# Execute with thread_id for persistence
config = {"configurable": {"thread_id": f"{symbol}_{date}"}}
result = app.invoke(initial_state, config=config)
```

### Benefits

- **Resume capability** - Restart from last checkpoint on failure
- **Inspection** - Debug agent conversations
- **Audit trail** - Review decision history
- **State snapshots** - Access intermediate states

### Checkpoint Structure

```json
{
  "_id": "checkpoint_id",
  "thread_id": "AAPL_2025-11-11_10-00-00",
  "checkpoint_ns": "",
  "checkpoint_id": "step_5",
  "parent_checkpoint_id": "step_4",
  "checkpoint": {
    "values": {
      "company_of_interest": "AAPL",
      "investment_debate_state": {...},
      "trader_investment_plan": "...",
      ...
    }
  }
}
```

## 🔄 State Propagation

### Propagator Utility

In `propagation.py`:

```python
class Propagator:
    """Handles state propagation between agents"""
    
    @staticmethod
    def merge_state(current_state: dict, updates: dict) -> dict:
        """Merge agent updates into current state"""
        return {**current_state, **updates}
    
    @staticmethod
    def validate_state(state: dict, required_fields: list) -> bool:
        """Validate state has required fields"""
        return all(field in state for field in required_fields)
    
    @staticmethod
    def extract_debate_context(state: dict) -> dict:
        """Extract debate-specific context"""
        return {
            "history": state["investment_debate_state"]["history"],
            "round": state["investment_debate_state"]["count"],
            "last_speaker": state["investment_debate_state"]["last_speaker"]
        }
```

### State Updates

Each agent returns partial state updates:

```python
# Agent returns
return {
    "new_field": "value",
    "updated_field": "new_value",
    "sender": "agent_name"
}

# LangGraph merges with existing state
merged_state = {**current_state, **agent_updates}
```

## 🧪 Testing

### Test Graph Construction

```python
from graph.setup import GraphSetup
from graph.conditional_logic import ConditionalLogic

# Mock checkpointer
class MockCheckpointer:
    def __init__(self):
        pass

# Setup
conditional_logic = ConditionalLogic()
checkpointer = MockCheckpointer()
setup = GraphSetup(conditional_logic, checkpointer)

# Mock LLMs (for testing)
setup.quick_thinking_llm = lambda x: "Mock response"
setup.deep_thinking_llm = lambda x: "Mock response"

# Build graph
app = setup.setup_graph()

# Verify nodes
assert "bull_researcher" in app.nodes
assert "trader" in app.nodes
print("✓ Graph constructed successfully")
```

### Test Conditional Logic

```python
from graph.conditional_logic import ConditionalLogic

logic = ConditionalLogic()

# Test minimum rounds
state = {
    "investment_debate_state": {
        "count": 0,
        "last_speaker": "bull_researcher"
    }
}
next_node = logic.should_continue_debate(state)
assert next_node == "bear_researcher"

# Test maximum rounds
state["investment_debate_state"]["count"] = 3
next_node = logic.should_continue_debate(state)
assert next_node == "trader"

print("✓ Conditional logic working")
```

### Test Full Workflow

```python
# Initialize
app = setup.setup_graph()

# Mock initial state
initial_state = {
    "company_of_interest": "AAPL",
    "market_report": "Test market report",
    "sentiment_report": "Test sentiment",
    "news_report": "Test news",
    "fundamentals_report": "Test fundamentals",
    "investment_debate_state": {
        "history": "",
        "count": 0,
        "last_speaker": ""
    },
    "current_position_size": 0,
    "account_balance": 10000.0
}

# Execute
config = {"configurable": {"thread_id": "test_123"}}
result = app.invoke(initial_state, config=config)

# Verify outputs
assert "trader_investment_plan" in result
assert "final_trade_decision" in result
print("✓ Full workflow executed")
```

## 📊 Workflow Visualization

### View Graph Structure

```python
# Get graph structure
app = setup.setup_graph()

# Print nodes
print("Nodes:", list(app.nodes.keys()))

# Print edges
for source, edges in app._edges.items():
    print(f"{source} → {edges}")
```

### LangGraph Studio (Optional)

If using LangGraph Studio:
```python
# Export graph for visualization
app.get_graph().draw_mermaid()
```

## 🔧 Configuration

### Debate Parameters

```python
# In conditional_logic.py
MIN_DEBATE_ROUNDS = 1  # Minimum before checking consensus
MAX_DEBATE_ROUNDS = 3  # Maximum regardless

# Environment variables
import os
MIN_DEBATE_ROUNDS = int(os.getenv("MIN_DEBATE_ROUNDS", "1"))
MAX_DEBATE_ROUNDS = int(os.getenv("MAX_DEBATE_ROUNDS", "3"))
```

### LLM Assignment

```python
# In setup.py
setup.quick_thinking_llm = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7
)

setup.deep_thinking_llm = llms.OpenAIChat(
    model="gpt-4o",
    temperature=0.3
)
```

## 🛡️ Error Handling

### Graph Execution Errors

```python
try:
    result = app.invoke(initial_state, config=config)
except Exception as e:
    logger.error(f"Graph execution failed: {e}")
    # Checkpointer allows inspection of last successful state
    # Can retry from last checkpoint
```

### Node Failures

```python
# Wrap nodes with error handling
def safe_node(agent_fn):
    def wrapper(state):
        try:
            return agent_fn(state)
        except Exception as e:
            logger.error(f"Agent {agent_fn.__name__} failed: {e}")
            return {"error": str(e), "sender": agent_fn.__name__}
    return wrapper
```

## 📝 Adding New Routing

To add new conditional routing:

```python
# In conditional_logic.py
def should_skip_risk_analysis(self, state: AgentState) -> str:
    """Example: Skip risk analysis for HOLD signals"""
    trader_plan = state.get("trader_investment_plan", "")
    
    if "HOLD" in trader_plan.upper():
        return "final_manager"  # Skip risk analysts
    else:
        return "risky_analyst"  # Continue to risk analysis

# In setup.py
workflow.add_conditional_edges(
    "trader",
    conditional_logic.should_skip_risk_analysis,
    {
        "risky_analyst": "risky_analyst",
        "final_manager": "final_manager"
    }
)
```

## 🔗 Related

- [../all_agents/](../all_agents/) - Agent implementations
- [../run_workflow.py](../run_workflow.py) - Workflow execution
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
