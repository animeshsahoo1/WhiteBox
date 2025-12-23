# Strategist Agent + MCP Server

A production-ready orchestration layer that provides:
- **MCP Server**: Exposes trading tools via Model Context Protocol (FastMCP)
- **Strategist Agent**: LangGraph ReAct agent with Mem0 persistent memory
- **API Integration**: HTTP endpoints via FastAPI + WebSocket real-time events

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Strategist Agent (LangGraph)                 │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │   Mem0      │    │  LangGraph   │    │  MCP Client       │  │
│  │   Memory    │◄───│  ReAct Loop  │───►│  (Tool Calls)     │  │
│  │   (Redis)   │    │              │    │                   │  │
│  └─────────────┘    └──────────────┘    └─────────┬─────────┘  │
│                                                    │            │
└────────────────────────────────────────────────────┼────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server (FastMCP)                        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                        MCP Tools                            ││
│  │  • Risk Assessment (3-tier: no-risk/neutral/aggressive)     ││
│  │  • Backtesting API (list/search/create/compare strategies)  ││
│  │  • Web Search (smart search with query decomposition)       ││
│  │  • Reports (facilitator/bull-bear debate)                   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Structure

```
orchestrator/
├── server.py              # FastMCP server entry point
├── langgraph_agent.py     # ReAct agent with Mem0 memory
├── config.py              # Configuration settings
├── chat_store.py          # Conversation history management
├── web_search.py          # DuckDuckGo integration
├── api_clients.py         # API client utilities
├── risk_managers_prompt.py # Risk assessment prompts
└── tools/                 # MCP tool implementations
    ├── __init__.py        # Tool registration
    ├── risk_tools.py      # 3-tier risk assessment
    ├── backtesting_tools.py # Strategy management
    ├── search_tools.py    # Web search tools
    ├── report_tools.py    # Report retrieval
    └── api_tools.py       # API wrapper tools
```

## 🔧 MCP Tools

### Risk Assessment (`tools/risk_tools.py`)

Three-tier risk analysis:
| Tier | Perspective | Description |
|------|-------------|-------------|
| No-Risk | Conservative | Preserves capital, minimal exposure |
| Neutral | Balanced | Moderate risk/reward tradeoff |
| Aggressive | Risk-On | Maximum exposure for potential gains |

### Backtesting (`tools/backtesting_tools.py`)

| Tool | Description |
|------|-------------|
| `list_strategies` | Get all strategies with metrics |
| `get_strategy_metrics` | Metrics for specific strategy |
| `search_strategies` | Semantic search by description |
| `create_strategy` | Generate from natural language |
| `compare_strategies` | Side-by-side comparison |

### Web Search (`tools/search_tools.py`)

| Tool | Description |
|------|-------------|
| `web_search` | DuckDuckGo search with query decomposition |
| `smart_search` | Multi-query search for complex questions |

### Reports (`tools/report_tools.py`)

| Tool | Description |
|------|-------------|
| `get_facilitator_report` | Bull-Bear debate conclusion |
| `get_debate_summary` | Full debate transcript |
| `get_symbol_reports` | All reports for a symbol |

## 🚀 Quick Start

### Environment Variables

```bash
# LLM
OPENAI_API_KEY=your_key
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_MODEL_AGENT=openai/gpt-4o-mini

# MCP Server
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=9004

# Redis (for Mem0)
REDIS_URL=rediss://...  # Upstash
# OR
MEM0_REDIS_HOST=redis
MEM0_REDIS_PORT=6379
```

### Run MCP Server

```bash
python server.py
```

Server starts on `http://0.0.0.0:9004/mcp`

### Run Agent (Test Mode)

```bash
python langgraph_agent.py --test
```

## 📡 API Endpoints

Integrated into the main FastAPI server (`unified-api`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/strategist/status` | GET | Check if Strategist is ready |
| `/strategist/chat` | POST | Send message, get response |
| `/strategist/chat/stream` | POST | SSE streaming response |
| `/strategist/new` | POST | Start new conversation |
| `/strategist/memory/{user_id}` | GET | Get user's stored memories |
| `/strategist/memory/{user_id}` | DELETE | Clear user memories |
| `/strategist/threads/{user_id}` | GET | Get current thread info |

### Chat Request

```bash
curl -X POST http://localhost:8000/strategist/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What trading strategies are available?",
    "user_id": "user123",
    "room_id": "optional_websocket_room"
  }'
```

### Streaming Response

```javascript
const eventSource = new EventSource('/strategist/chat/stream', {
  method: 'POST',
  body: JSON.stringify({
    message: "Find the best strategy by Sharpe ratio",
    user_id: "user123"
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.event === 'chunk') {
    console.log(data.content);
  } else if (data.event === 'done') {
    console.log('Complete:', data.full_response);
  }
};
```

## 🧠 Mem0 Memory

Persistent memory for user preferences and past interactions:

```python
from mem0 import Memory

# Auto-stores user context
memory.add("User prefers momentum strategies", user_id="user123")

# Retrieved during conversations
memories = memory.get_all(user_id="user123")
```

### Memory Storage

Uses Redis as vector store (via RediSearch):
```python
config = {
    "vector_store": {
        "provider": "redis",
        "config": {
            "redis_url": os.getenv("REDIS_URL")
        }
    }
}
```

## 📡 WebSocket Events

When `room_id` is provided, events are published to Redis Pub/Sub:

| Event Type | Description |
|------------|-------------|
| `strategist_thinking` | Agent is processing |
| `strategist_chunk` | Streaming response chunk |
| `strategist_tool_call` | Tool being invoked |
| `strategist_done` | Response complete |

## 🔄 LangGraph ReAct Loop

```
User Input
    │
    ▼
┌─────────────────┐
│ Load Memories   │◄──── Mem0 Redis
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reasoning       │
│ (LLM decides)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│ Tool  │ │ Final │
│ Call  │ │Answer │
└───┬───┘ └───────┘
    │
    ▼
┌─────────────────┐
│ MCP Server      │
│ (Execute Tool)  │
└────────┬────────┘
         │
         ▼
    Loop back to Reasoning
```

## 🧪 Testing

```bash
# Test MCP server connectivity
curl http://localhost:9004/mcp

# Test agent (interactive)
python langgraph_agent.py

# Test with sample queries
python langgraph_agent.py --test
```

## 📚 Related

- [Bull-Bear Debate](../bullbear/evaluation/README.md) - Debate system
- [Backtesting API](../api/backtesting_api.py) - Strategy endpoints
- [RAG API](../api/rag_api.py) - Document retrieval
