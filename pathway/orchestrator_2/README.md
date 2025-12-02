# Strategist (MCP Server + LangGraph Agent)

A production-ready orchestration layer that provides:
- **MCP Server**: Exposes trading tools via Model Context Protocol
- **Strategist Agent**: LangGraph ReAct agent with Mem0 persistent memory
- **API Integration**: HTTP endpoints via FastAPI + WebSocket real-time events

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Strategist Agent (LangGraph)                 │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │   Mem0      │    │  LangGraph   │    │  MCP Client       │  │
│  │   Memory    │◄───│  Reasoning   │───►│  (Tool Calls)     │  │
│  │   (Redis)   │    │  Loop        │    │                   │  │
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
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  Reports    │    │ Backtesting │    │   Redis     │
    │    API      │    │   Pipeline  │    │   Cache     │
    │  (FastAPI)  │    │  (Pathway)  │    │             │
    └─────────────┘    └─────────────┘    └─────────────┘
```

## API Endpoints

The Strategist is integrated into the main FastAPI server (`reports-api`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/strategist/status` | GET | Check if Strategist is ready |
| `/strategist/chat` | POST | Send message, get response |
| `/strategist/chat/stream` | POST | SSE streaming response |
| `/strategist/new` | POST | Start new conversation |
| `/strategist/memory/{user_id}` | GET | Get user's stored memories |
| `/strategist/memory/{user_id}` | DELETE | Clear user memories |
| `/strategist/threads/{user_id}` | GET | Get current thread info |

### Example: Chat Request

```bash
curl -X POST http://localhost:8000/strategist/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What trading strategies are available?",
    "user_id": "user123",
    "room_id": "optional_websocket_room"
  }'
```

### Example: Streaming Response

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
    console.log(data.content);  // Streaming response chunk
  } else if (data.event === 'done') {
    console.log('Complete:', data.full_response);
  }
};
```

## WebSocket Integration

When `room_id` is provided in chat requests, events are published to Redis Pub/Sub:

| Event Type | Description |
|------------|-------------|
| `strategist_thinking` | Agent is processing the request |
| `strategist_chunk` | Streaming response chunk |
| `strategist_response` | Complete response |
| `strategist_error` | Error occurred |

Frontend can subscribe via the WebSocket server:
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/room123');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle strategist events
};
```
