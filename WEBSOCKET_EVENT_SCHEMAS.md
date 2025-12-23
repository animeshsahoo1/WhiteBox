# WebSocket Event Schemas

## Connection Endpoints

| Endpoint | Redis Channel | Purpose |
|----------|---------------|---------|
| `/ws/reports/{symbol}` | `room:symbol:{symbol}` | All events for a specific symbol |
| `/ws/alerts` | `alerts` | Global alerts from all symbols |
| `/ws/backtesting` | `reports` | Backtesting metrics updates |

## Event Wrapper Structure

All events published to Redis follow this wrapper:
```json
{
  "room_id": "symbol:AAPL",
  "type": "<event_type>",
  "data": { ... }
}
```

---

## Event Types

### 1. `agent_status` - Agent Status Updates

Published when agents start, complete, or fail processing.

```json
{
  "room_id": "symbol:AAPL",
  "type": "agent_status",
  "data": {
    "agent": "Market Agent",
    "status": "RUNNING"
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

**Status Values:**
- `"RUNNING"` - Agent is processing
- `"COMPLETED"` - Agent finished successfully
- `"FAILED"` - Agent encountered an error
- `"THINKING"` - Agent is reasoning

---

### 2. `report` - Report Ready Events

Published when an agent finishes generating a report.

```json
{
  "room_id": "symbol:AAPL",
  "type": "report",
  "data": {
    "agent": "Market Agent",
    "report": { ... }
  }
}
```

#### Market Report
```json
{
  "agent": "Market Agent",
  "report": {
    "symbol": "AAPL",
    "report_type": "market",
    "trend": "BULLISH",
    "strength": "STRONG",
    "price": 195.50,
    "change_percent": 1.25,
    "indicators": {
      "sma_20": 192.30,
      "rsi": 65.4
    }
  }
}
```

#### News Report
```json
{
  "agent": "News Agent",
  "report": {
    "symbol": "AAPL",
    "report_type": "news",
    "cluster_count": 5,
    "new_clusters": 2,
    "update_number": 3
  }
}
```

#### Sentiment Report
```json
{
  "agent": "Sentiment Agent",
  "report": {
    "symbol": "AAPL",
    "report_type": "sentiment",
    "overall_sentiment": 0.45,
    "sentiment_direction": "BULLISH",
    "cluster_count": 8,
    "total_posts": 150
  }
}
```

#### Fundamental Report
```json
{
  "agent": "Fundamental Agent",
  "report": {
    "symbol": "AAPL",
    "report_type": "fundamental",
    "rating": "BUY"
  }
}
```

---

### 3. `debate_point` - Bull-Bear Debate Points

Published when Bull or Bear makes a point during debate.

```json
{
  "room_id": "symbol:AAPL",
  "type": "debate_point",
  "data": {
    "party": "bull",
    "round": 1,
    "content": "AAPL shows strong momentum with...",
    "confidence": 0.85,
    "supporting_evidence": [
      "Technical breakout above 50-day SMA",
      "Positive earnings surprise"
    ],
    "status": "SPEAKING",
    "point_id": "uuid-1234",
    "counter_to": null,
    "symbol": "AAPL",
    "timestamp": "2025-12-07T10:00:00.000Z"
  }
}
```

**Party Values:**
- `"bull"` - Bullish argument
- `"bear"` - Bearish argument

**Status Values:**
- `"SPEAKING"` - Point is being made
- `"COMPLETED"` - Point is finalized

---

### 4. `debate_progress` - Debate Progress Updates

Published to track overall debate progress.

```json
{
  "room_id": "symbol:AAPL",
  "type": "debate_progress",
  "data": {
    "current_round": 2,
    "max_rounds": 3,
    "bull_points": 4,
    "bear_points": 3,
    "status": "in_progress",
    "symbol": "AAPL",
    "timestamp": "2025-12-07T10:05:00.000Z"
  }
}
```

**Status Values:**
- `"in_progress"` - Debate is ongoing
- `"completed"` - Debate has concluded

---

### 5. `recommendation` - Facilitator Recommendation

Published when the facilitator concludes the debate.

```json
{
  "room_id": "symbol:AAPL",
  "type": "recommendation",
  "data": {
    "symbol": "AAPL",
    "recommendation": "BUY",
    "confidence": 0.78,
    "facilitator_report": "After analyzing both perspectives...",
    "timestamp": "2025-12-07T10:10:00.000Z"
  }
}
```

**Recommendation Values:**
- `"BUY"` - Bullish recommendation
- `"SELL"` - Bearish recommendation
- `"HOLD"` - Neutral recommendation

---

### 6. `graph_state` - LangGraph State Updates

Published to visualize the current state of LangGraph workflows.

```json
{
  "room_id": "symbol:AAPL",
  "type": "graph_state",
  "data": {
    "symbol": "AAPL",
    "current_node": "bull_point",
    "current_speaker": "bull",
    "round": 2,
    "total_points": 5,
    "nodes": ["fetch_reports", "bull_point", "bear_point", "facilitator"],
    "active_node": "bull_point",
    "edges": [
      {"from": "fetch_reports", "to": "bull_point"},
      {"from": "bull_point", "to": "bear_point"}
    ],
    "timestamp": "2025-12-07T10:05:00.000Z"
  }
}
```

---

### 7. `alert` - Global Alerts

Published to the global `alerts` channel when significant events occur.

```json
{
  "type": "alert",
  "symbol": "AAPL",
  "data": {
    "alert_type": "sentiment",
    "reason": "Extreme bearish sentiment detected (-0.45)",
    "severity": "high",
    "timestamp": "2025-12-07T10:00:00.000Z",
    "trigger_debate": false
  }
}
```

**Alert Types:**
- `"sentiment"` - Sentiment threshold crossed
- `"news"` - Significant news detected
- `"market"` - Market event (large price move)
- `"fundamental"` - Fundamental change

**Severity Levels:**
- `"low"` - Informational
- `"medium"` - Notable
- `"high"` - Significant (2-5% move potential)
- `"critical"` - Major (>5% move potential)

---

### 8. `backtesting_metrics` - Strategy Metrics Updates

Published when backtesting metrics are updated.

```json
{
  "type": "backtesting_metrics",
  "symbol": "AAPL",
  "data": {
    "strategy": "sma_crossover",
    "symbol": "AAPL",
    "interval": "1d",
    "metrics": {
      "total_trades": 15,
      "win_rate": 0.60,
      "sharpe_ratio": 1.25,
      "max_drawdown": 0.12,
      "profit_factor": 1.85,
      "equity": 12500.00,
      "return_pct": 25.0
    },
    "timestamp": "2025-12-07T10:00:00.000Z"
  }
}
```

---

## Redis Pub/Sub Channels

| Channel Pattern | Description |
|-----------------|-------------|
| `room:symbol:{SYMBOL}` | Symbol-specific events (reports, debate, status) |
| `alerts` | Global alerts from all symbols |
| `reports` | Global report updates (backtesting metrics) |

## JavaScript Client Example

```javascript
// Connect to symbol-specific events
const ws = new WebSocket('ws://localhost:8080/ws/reports/AAPL');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'agent_status':
      console.log(`${data.data.agent}: ${data.data.status}`);
      break;
    case 'report':
      console.log(`New ${data.data.report.report_type} report`);
      break;
    case 'debate_point':
      console.log(`${data.data.party}: ${data.data.content}`);
      break;
    case 'recommendation':
      console.log(`Final: ${data.data.recommendation}`);
      break;
    case 'alert':
      console.log(`⚠️ ${data.data.reason}`);
      break;
  }
};

// Connect to global alerts
const alertsWs = new WebSocket('ws://localhost:8080/ws/alerts');
alertsWs.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log(`🚨 ${alert.symbol}: ${alert.data.reason}`);
};
```

## Python Publisher Example

```python
from event_publisher import (
    publish_agent_status,
    publish_report,
    publish_debate_point,
    publish_recommendation,
    publish_alert
)

# Publish agent status
publish_agent_status("symbol:AAPL", "Market Agent", "RUNNING")

# Publish report
publish_report("symbol:AAPL", "Market Agent", {
    "symbol": "AAPL",
    "report_type": "market",
    "trend": "BULLISH"
})

# Publish debate point
publish_debate_point("symbol:AAPL", {
    "party": "bull",
    "round": 1,
    "content": "Strong technical setup",
    "confidence": 0.8
})

# Publish alert
publish_alert("AAPL", "sentiment", "Extreme sentiment", "high")
```
