# WebSocket Server with Redis Pub/Sub

A real-time WebSocket server built with **FastAPI** that uses **Redis Pub/Sub** to broadcast events to connected clients. Designed for multi-room event streaming (e.g., agent status updates, workflow reports).

---

## Architecture Overview

```
┌─────────────────┐      publish       ┌─────────────────┐
│  Other Services │  ───────────────►  │   Redis Pub/Sub │
│  (Trading Agents│                    │   (Upstash/Local)│
│   Pathway, etc.)│                    └────────┬────────┘
└─────────────────┘                             │
                                                │ subscribe
                                                ▼
                                    ┌─────────────────────┐
                                    │   FastAPI WebSocket │
                                    │       Server        │
                                    └──────────┬──────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                        ┌──────────┐    ┌──────────┐    ┌──────────┐
                        │ Client 1 │    │ Client 2 │    │ Client 3 │
                        │(room:abc)│    │(room:abc)│    │(room:xyz)│
                        └──────────┘    └──────────┘    └──────────┘
```

## File Descriptions

### `main.py`

FastAPI application with:

- **`GET /ping`**: Health check endpoint that also publishes a test event
- **`WS /ws/{room_id}`**: WebSocket endpoint. Clients connect to a room, and receive all events published to `room:{room_id}` on Redis

### `app/redis_util.py`

Configures Redis clients based on environment variables:

- `get_redis_client()`: Returns a **synchronous** Redis client (cached)
- `get_async_redis()`: Returns an **async** Redis client (fresh per connection)

Supports both:

- **Local Redis**: via `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- **Upstash Redis**: via `REDIS_URL` (handles `rediss://` SSL connections)

### `app/redis_client.py`

Simple module that exports `redis_sync` - the synchronous Redis client used for publishing.

### `app/websocket_manager.py`

Manages WebSocket connections per room:

- `connect(room_id, websocket)`: Accept and store connection
- `disconnect(room_id, websocket)`: Remove connection from room
- `broadcast(room_id, message)`: Send message to all clients in a room

### `app/event_publisher.py`

Utility functions for publishing events to Redis:

- `publish_event(room_id, event_type, payload)`: Generic event publisher
- `publish_agent_status(room_id, agent, status)`: Agent status updates
- `publish_report(room_id, agent, report)`: Send completed reports

### `debug_redis.py`

CLI debugging tool to monitor all Redis pub/sub messages on `room:*` channels. Useful for verifying events are being published correctly.

---

## Setup & Running

### Prerequisites

- Docker & Docker Compose
- A `.env` file with your Redis configuration

### Environment Variables

Create a `.env` file in the `websocket/` directory:

```env
# For Upstash Redis (recommended)
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST.upstash.io:6379

# OR for local Redis
# REDIS_HOST=redis
# REDIS_PORT=6379
# REDIS_DB=0
```

### Run with Docker Compose

```bash
# Navigate to the websocket directory
cd websocket

# Build and start the container
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

The WebSocket server will be available at `ws://localhost:8001/ws/{room_id}`

### Test the Connection

```bash
# Health check
curl http://localhost:8001/ping
```

Connect via WebSocket client (e.g., browser console):

```javascript
const ws = new WebSocket("ws://localhost:8001/ws/my-room-id");
ws.onmessage = (event) => console.log("Received:", JSON.parse(event.data));
```

---

## Debugging Redis Pub/Sub

### Run `debug_redis.py`

This tool monitors all messages published to `room:*` channels.

**Inside the Docker container:**

```bash
docker-compose exec fastapi-app python debug_redis.py
```

**Expected output:**

```
🔗 Connected to Upstash Redis
🔍 Monitoring all room:* channels...
📩 room:test-room: {"room_id": "test-room", "type": "agent_status", "data": {"agent": "analyst", "status": "running"}}
📩 room:test-room: {"room_id": "test-room", "type": "report", "data": {"agent": "analyst", "report": {...}}}
```

---

## Publishing Events from Other Services

Import and use `event_publisher.py` in your other services (trading agents, pathway, etc.):

```python
from app.event_publisher import publish_agent_status, publish_report, publish_event

# Notify that an agent started
publish_agent_status("workflow-123", "analyst_agent", "running")

# Send a completed report
publish_report("workflow-123", "analyst_agent", {"summary": "...", "data": {...}})

# Generic event
publish_event("workflow-123", "custom_event", {"key": "value"})
```

---

## Event Message Format

All events follow this JSON structure:

```json
{
  "room_id": "workflow-123",
  "type": "agent_status",
  "data": {
    "agent": "analyst_agent",
    "status": "running"
  }
}
```

### Event Types

| Type           | Description                      |
| -------------- | -------------------------------- |
| `agent_status` | Agent started/completed/failed   |
| `report`       | Agent finished and sent a report |
| _(custom)_     | Any custom event type you define |

---

## Stopping the Server

```bash
# Stop containers
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Troubleshooting

### WebSocket connection fails

- Check if the container is running: `docker ps`
- Verify Redis connection: run `debug_redis.py` and check for errors
- Ensure `.env` file exists with correct `REDIS_URL`

### No messages received

- Confirm events are being published (check `debug_redis.py` output)
- Verify you're connecting to the correct `room_id`
- Check container logs: `docker-compose logs -f fastapi-app`

### SSL errors with Upstash

- Make sure `REDIS_URL` starts with `rediss://` (with double 's')
- The code handles SSL cert verification automatically
