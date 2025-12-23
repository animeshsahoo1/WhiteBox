# WebSocket Server

Real-time WebSocket server built with **FastAPI** that uses **Redis Pub/Sub** to broadcast events to connected clients. Designed for multi-room event streaming (reports, alerts, debate updates, backtesting metrics).

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PATHWAY SERVICES                            │
│  (Agents, Bull-Bear Debate, Strategist, Backtesting)             │
│                                                                   │
│  publish_event() / publish_agent_status() / publish_report()     │
└──────────────────────────────┬──────────────────────────────────┘
                               │ PUBLISH
                               ▼
                      ┌─────────────────┐
                      │   Redis Pub/Sub │
                      │  (Upstash/Local)│
                      └────────┬────────┘
                               │ SUBSCRIBE
                               ▼
                  ┌─────────────────────────┐
                  │   FastAPI WebSocket     │
                  │        Server           │
                  │    (Port 8080)          │
                  └────────────┬────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Client 1    │   │  Client 2    │   │  Client 3    │
    │ (AAPL room)  │   │ (AAPL room)  │   │ (alerts)     │
    └──────────────┘   └──────────────┘   └──────────────┘
```

## 📁 Structure

```
websocket/
├── main.py                 # FastAPI application + WebSocket endpoints
├── app/
│   ├── websocket_manager.py   # Connection management per room
│   ├── event_publisher.py     # Publish to Redis (for testing)
│   └── redis_util.py          # Redis client configuration
├── debug_redis.py          # CLI tool to monitor Redis pub/sub
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🔌 WebSocket Endpoints

| Endpoint | Redis Channel | Description |
|----------|---------------|-------------|
| `/ws/reports/{symbol}` | `room:symbol:{symbol}` | Symbol-specific events (reports, debate, status) |
| `/ws/alerts` | `alerts` | Global alerts from all symbols |
| `/ws/backtesting` | `reports` | Backtesting metrics updates |

### Connection Example

```javascript
// Connect to AAPL events
const ws = new WebSocket('ws://localhost:8080/ws/reports/AAPL');

ws.onopen = () => {
  console.log('Connected to AAPL room');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.type}:`, data.data);
};

// Connect to global alerts
const alertsWs = new WebSocket('ws://localhost:8080/ws/alerts');
```

## 🚀 Quick Start

### Environment Variables

Create `.env` in the `websocket/` directory:

```bash
# For Upstash Redis (recommended for production)
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST.upstash.io:6379

# OR for local Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

### Docker Deployment

```bash
# From websocket directory
docker compose up -d

# View logs
docker compose logs -f

# Check health
curl http://localhost:8080/health
```

### Local Development

```bash
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

## 📡 API Endpoints

### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "connections": 5,
  "rooms": ["symbol:AAPL", "symbol:GOOGL", "alerts"]
}
```

### Ping (Test Event)

```bash
curl http://localhost:8080/ping
```

Publishes a test event to verify Redis connectivity.

## 📦 Components

### `main.py`

FastAPI application with:
- `GET /health` - Health check with connection stats
- `GET /ping` - Test event publishing
- `WS /ws/reports/{symbol}` - Symbol-specific WebSocket
- `WS /ws/alerts` - Global alerts WebSocket
- `WS /ws/backtesting` - Backtesting metrics WebSocket

### `app/websocket_manager.py`

Manages WebSocket connections per room:
```python
class WebSocketManager:
    async def connect(room_id, websocket)   # Accept and store connection
    def disconnect(room_id, websocket)      # Remove connection from room
    async def broadcast(room_id, message)   # Send to all clients in room
    def get_connection_count()              # Total active connections
```

### `app/redis_util.py`

Configures Redis clients:
- `get_redis_client()` - Synchronous Redis client (cached)
- `get_async_redis()` - Async Redis client (per connection)

Supports:
- **Upstash Redis**: via `REDIS_URL` (handles `rediss://` SSL)
- **Local Redis**: via `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

### `app/event_publisher.py`

Publishing utilities (for testing from websocket service):
```python
publish_event(room_id, event_type, payload)
publish_agent_status(room_id, agent, status)
publish_report(room_id, agent, report)
```

### `debug_redis.py`

CLI tool to monitor Redis pub/sub:
```bash
python debug_redis.py
```

Subscribes to `room:*` and `alerts` channels to verify events.

## 🔄 Event Flow

1. **Pathway Service** publishes event:
   ```python
   from event_publisher import publish_agent_status
   publish_agent_status("symbol:AAPL", "Market Agent", "COMPLETED")
   ```

2. **Redis** receives on channel `room:symbol:AAPL`

3. **WebSocket Server** subscribed to channel, receives message

4. **Broadcast** to all connected clients in room `symbol:AAPL`

5. **Frontend** receives via WebSocket

## 📊 Event Types

See [WEBSOCKET_EVENT_SCHEMAS.md](../WEBSOCKET_EVENT_SCHEMAS.md) for complete event type documentation.

### Quick Reference

| Event Type | Description |
|------------|-------------|
| `agent_status` | Agent started/completed/failed |
| `report` | New report available |
| `debate_point` | Bull/Bear argument |
| `debate_progress` | Debate round progress |
| `recommendation` | Facilitator conclusion |
| `graph_state` | LangGraph visualization |
| `alert` | Significant event notification |

## 🐳 Docker Configuration

### docker-compose.yml

```yaml
services:
  websocket-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=${REDIS_URL}
      # OR
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    networks:
      - stock-network
```

## 🔧 Troubleshooting

### WebSocket Connection Fails

```bash
# Check server is running
curl http://localhost:8080/health

# Check Redis connectivity
docker exec -it pathway-redis redis-cli ping
```

### Events Not Received

```bash
# Monitor Redis pub/sub
python debug_redis.py

# Check if events are being published
docker compose logs -f pathway-unified-api | grep "Published event"
```

### SSL Issues with Upstash

Ensure `REDIS_URL` starts with `rediss://` (double 's' for SSL).

## 📚 Frontend Integration

### React Example

```jsx
import { useEffect, useState } from 'react';

function useSymbolEvents(symbol) {
  const [events, setEvents] = useState([]);
  
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8080/ws/reports/${symbol}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [...prev, data]);
    };
    
    return () => ws.close();
  }, [symbol]);
  
  return events;
}
```

### Connection Confirmation

On connect, the server sends:
```json
{
  "type": "connection",
  "status": "connected",
  "symbol": "AAPL",
  "message": "Connected to AAPL reports"
}
```
