# WebSocket Event Schemas

## Connection Endpoints

| Endpoint | Subscribes To | Purpose |
|----------|--------------|---------|
| `/ws/symbol:AAPL` | `room:symbol:AAPL` | All events for AAPL (status, reports, debate) |
| `/ws/alerts` | `alerts` | Global alerts from all symbols |
| `/ws/reports` | `reports` | Global report updates |

## Event Types on `room:symbol:{SYMBOL}`

All events have this wrapper structure:
```json
{
  "room_id": "symbol:AAPL",
  "type": "<event_type>",
  "data": { ... }
}
```

---

### 1. `agent_status` - Agent Status Updates

When agents start/complete processing.

```json
{
  "room_id": "symbol:AAPL",
  "type": "agent_status",
  "data": {
    "agent": "Market Agent",
    "status": "RUNNING" | "COMPLETED" | "FAILED" | "THINKING"
  }
}
```

**Agent Names:**
- `"Market Agent"`
- `"News Agent"`
- `"Sentiment Agent"`
- `"Fundamental Agent"`
- `"Bull Agent"`
- `"Bear Agent"`
- `"Facilitator Agent"`
- `"orchestrator"`

---

### 2. `report` - Report Ready Events

When an agent finishes generating a report.

#### Market Report
```json
{
  "room_id": "symbol:AAPL",
  "type": "report",
  "data": {
    "agent": "Market Agent",
    "report": {
      "symbol": "AAPL",
      "report_type": "market",
      "trend": "BULLISH" | "BEARISH" | "NEUTRAL",
      "strength": "STRONG" | "MODERATE" | "WEAK",
      "price": 195.50,
      "change_percent": 1.25
    }
  }
}
```

#### News Report
```json
{
  "room_id": "symbol:AAPL",
  "type": "report",
  "data": {
    "agent": "News Agent",
    "report": {
      "symbol": "AAPL",
      "report_type": "news",
      "cluster_count": 5,
      "new_clusters": 2,
      "update_number": 3
    }
  }
}
```

#### Sentiment Report
```json
{
  "room_id": "symbol:AAPL",
  "type": "report",
  "data": {
    "agent": "Sentiment Agent",
    "report": {
      "symbol": "AAPL",
      "report_type": "sentiment",
      "overall_sentiment": 0.45,
      "sentiment_direction": "BULLISH" | "BEARISH" | "NEUTRAL",
      "cluster_count": 8,
      "total_posts": 150,
      "clusters": [
        {
          "cluster_id": 1,
          "theme": "earnings optimism",
          "sentiment": 0.7,
          "post_count": 25
        }
      ]
    }
  }
}
```

#### Fundamental Report
```json
{
  "room_id": "symbol:AAPL",
  "type": "report",
  "data": {
    "agent": "Fundamental Agent",
    "report": {
      "symbol": "AAPL",
      "report_type": "fundamental",
      "rating": "BUY" | "SELL" | "HOLD" | "N/A"
    }
  }
}
```

---

### 3. `debate_point` - Bull-Bear Debate Points

When Bull or Bear makes a point during debate.

```json
{
  "room_id": "symbol:AAPL",
  "type": "debate_point",
  "data": {
    "party": "bull" | "bear",
    "round": 1,
    "content": "AAPL shows strong momentum with...",
    "confidence": 0.85,
    "supporting_evidence": ["Technical breakout", "Positive earnings"],
    "status": "SPEAKING",
    "point_id": "bull_1_abc123",
    "counter_to": null | "bear_0_xyz789",
    "symbol": "AAPL",
    "timestamp": "2025-12-05T12:30:45.123Z"
  }
}
```

---

### 4. `debate_progress` - Debate Status Updates

```json
{
  "room_id": "symbol:AAPL",
  "type": "debate_progress",
  "data": {
    "current_round": 2,
    "max_rounds": 5,
    "bull_points": 3,
    "bear_points": 2,
    "status": "in_progress" | "completed",
    "symbol": "AAPL",
    "timestamp": "2025-12-05T12:30:45.123Z"
  }
}
```

---

### 5. `recommendation` - Final Facilitator Decision

```json
{
  "room_id": "symbol:AAPL",
  "type": "recommendation",
  "data": {
    "symbol": "AAPL",
    "recommendation": "BUY" | "SELL" | "HOLD",
    "confidence": 0.78,
    "facilitator_report": "Based on the debate, AAPL shows...",
    "timestamp": "2025-12-05T12:30:45.123Z"
  }
}
```

---

### 6. `graph_state` - LangGraph Node Updates

For visualizing the workflow graph.

```json
{
  "room_id": "symbol:AAPL",
  "type": "graph_state",
  "data": {
    "node": "generate_bull_point" | "generate_bear_point" | "facilitator_check" | "tools" | "agent",
    "status": "RUNNING" | "COMPLETED",
    "timestamp": "2025-12-05T12:30:45.123Z"
  }
}
```

---

## Events on `alerts` Channel

Connect to `/ws/alerts` for global alerts.

```json
{
  "type": "alert",
  "symbol": "AAPL",
  "data": {
    "alert_type": "sentiment_spike" | "price_drift" | "news_event",
    "reason": "Sentiment crossed threshold: 0.85",
    "severity": "HIGH" | "MEDIUM" | "LOW",
    "timestamp": "2025-12-05T12:30:45.123Z",
    "trigger_debate": true
  }
}
```

---

## Events on `reports` Channel

Connect to `/ws/reports` for global report notifications.

```json
{
  "type": "market_report" | "news_report" | "sentiment_report" | "fundamental_report",
  "symbol": "AAPL",
  "data": {
    "report_type": "market",
    "symbol": "AAPL",
    "timestamp": "2025-12-05T12:30:45.123Z"
  }
}
```

---

## Frontend Subscription Example

```javascript
// Connect to symbol-specific room
const ws = new WebSocket('wss://your-server/ws/symbol:AAPL');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'agent_status':
      // Update agent status UI
      console.log(`${message.data.agent}: ${message.data.status}`);
      break;
      
    case 'report':
      // Show report ready notification
      console.log(`Report ready from ${message.data.agent}`);
      console.log(message.data.report);
      break;
      
    case 'debate_point':
      // Add to debate timeline
      console.log(`${message.data.party} says: ${message.data.content}`);
      break;
      
    case 'debate_progress':
      // Update progress bar
      console.log(`Round ${message.data.current_round}/${message.data.max_rounds}`);
      break;
      
    case 'recommendation':
      // Show final recommendation
      console.log(`Recommendation: ${message.data.recommendation}`);
      break;
      
    case 'graph_state':
      // Update workflow visualization
      console.log(`Node ${message.data.node}: ${message.data.status}`);
      break;
  }
};
```
