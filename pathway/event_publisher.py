#event_publisher.py

import json
import os
from datetime import datetime
from typing import Any, Dict
import httpx


def publish_event(room_id: str, event_type: str, payload: Dict[str, Any], redis_sync):
    """
    Publish a workflow event to Redis Pub/Sub.

    Args:
        room_id: Unique workflow room/channel ID
        event_type: A label like "agent_start", "agent_complete", "report_ready"
        payload: Arbitrary data (must be JSON serializable)
    """

    message = {
        "room_id": room_id,
        "type": event_type,
        "data": payload,
    }

    # Redis pub/sub channel
    channel = f"room:{room_id}"

    # Serialize message to JSON
    json_message = json.dumps(message)

    # Publish to Redis
    redis_sync.publish(channel, json_message)

    print(f"📡 Published event → {channel}: {json_message}")


def publish_agent_status(room_id: str, agent: str, status: str, redis_sync):
    """
    Helper function for simple status updates.

    status = "running" / "completed" / "failed"
    """

    publish_event(
        room_id,
        event_type="agent_status",
        payload={
            "agent": agent,
            "status": status,
        },
        redis_sync=redis_sync,
    )


def publish_report(room_id: str, agent: str, report: Any, redis_sync, event_type="report"):
    """
    Publish a finished report.
    """

    publish_event(
        room_id,
        event_type=event_type,
        payload={
            "agent": agent,
            "report": report,
        },
        redis_sync=redis_sync,
    )


def publish_alert(
    symbol: str,
    alert_type: str,
    reason: str,
    severity: str,
    redis_sync,
    trigger_debate: bool = True
):
    """
    Publish an alert to WebSocket and optionally trigger Bull-Bear debate.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        alert_type: "news" | "sentiment" | "drift"
        reason: Human-readable reason for the alert
        severity: "low" | "medium" | "high" | "critical"
        redis_sync: Redis client for pub/sub
        trigger_debate: Whether to trigger Bull-Bear debate
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    alert_payload = {
        "alert_type": alert_type,
        "symbol": symbol,
        "reason": reason,
        "severity": severity,
        "timestamp": timestamp,
    }
    
    # Publish to symbol-specific room
    symbol_room = f"symbol:{symbol}"
    publish_event(symbol_room, "alert", alert_payload, redis_sync)
    
    # Publish to global alerts room
    publish_event("alerts", "alert", alert_payload, redis_sync)
    
    print(f"🚨 ALERT [{alert_type.upper()}] {symbol}: {reason} (severity: {severity})")
    
    # Trigger Bull-Bear debate if enabled
    if trigger_debate:
        bullbear_url = os.getenv("BULLBEAR_API_URL", "http://unified-api:8000")
        try:
            httpx.post(
                f"{bullbear_url}/debate/{symbol}",
                json={"max_rounds": 2, "background": True},
                timeout=10.0
            )
            print(f"✅ [{symbol}] Bull-Bear debate triggered via alert ({alert_type})")
        except Exception as e:
            print(f"⚠️ [{symbol}] Failed to trigger Bull-Bear debate: {e}")


if __name__ == "__main__":
    publish_event("test", "test", "test")