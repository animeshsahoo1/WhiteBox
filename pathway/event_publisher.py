#event_publisher.py
"""
Event Publisher for Pathway Service
Publishes events to Redis Pub/Sub for WebSocket forwarding to frontend.

Matches websocket/app/event_publisher.py signatures (singleton pattern).
"""

import json
import os
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# SINGLETON REDIS CLIENT
# ============================================================================

_redis_client: Optional[redis.Redis] = None


def get_publisher_redis_client() -> redis.Redis:
    """Get singleton Redis client for publishing events."""
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL")
        if url:
            # Handle Upstash SSL connections (rediss://)
            if url.startswith("rediss://"):
                _redis_client = redis.Redis.from_url(
                    url,
                    decode_responses=True,
                    ssl_cert_reqs=ssl.CERT_NONE
                )
            else:
                _redis_client = redis.Redis.from_url(url, decode_responses=True)
            print("📡 Event publisher using REDIS_URL")
        else:
            # Fallback to host/port config
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", 6379))
            db = int(os.getenv("REDIS_DB", 0))
            _redis_client = redis.Redis(
                host=host, port=port, db=db, decode_responses=True
            )
            print(f"📡 Event publisher using REDIS_HOST={host}:{port}")
    return _redis_client


# ============================================================================
# CORE PUBLISH FUNCTIONS (Match websocket/app/event_publisher.py)
# ============================================================================

def publish_event(room_id: str, event_type: str, payload: Dict[str, Any]):
    """
    Publish a workflow event to Redis Pub/Sub.

    Args:
        room_id: Unique workflow room/channel ID
        event_type: A label like "agent_status", "report", "debate_point"
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
    try:
        get_publisher_redis_client().publish(channel, json_message)
        print(f"📡 Published event → {channel}: {event_type}")
    except Exception as e:
        print(f"⚠️ Failed to publish event to {channel}: {e}")


def publish_agent_status(room_id: str, agent: str, status: str):
    """
    Helper function for simple status updates.

    Args:
        room_id: Room/channel ID
        agent: Agent name (e.g., "Bull Agent", "Analyst Agent")
        status: Status string (e.g., "RUNNING", "COMPLETED", "FAILED")
    """
    publish_event(
        room_id,
        event_type="agent_status",
        payload={
            "agent": agent,
            "status": status,
        },
    )


def publish_report(room_id: str, agent: str, report: Any):
    """
    Publish a finished report.

    Args:
        room_id: Room/channel ID
        agent: Agent name that produced the report
        report: Report data (dict or string)
    """
    publish_event(
        room_id,
        event_type="report",
        payload={
            "agent": agent,
            "report": report,
        },
    )


def publish_alerts(data: Any, symbol: str):
    """
    Publish an alert message to the global alerts channel.

    Args:
        data: Alert data (should include alert_type, reason, severity, etc.)
        symbol: Stock symbol
    """
    message = {
        "type": "alert",
        "symbol": symbol,
        "data": data,
    }

    # Publish to global alerts channel (no room: prefix)
    channel = "alerts"
    json_message = json.dumps(message)

    try:
        get_publisher_redis_client().publish(channel, json_message)
        print(f"🚨 Published alert → {channel}: {symbol}")
    except Exception as e:
        print(f"⚠️ Failed to publish alert: {e}")

    # Also publish to symbol-specific room for users watching that symbol
    symbol_channel = f"room:symbol:{symbol}"
    try:
        get_publisher_redis_client().publish(symbol_channel, json_message)
    except Exception as e:
        print(f"⚠️ Failed to publish to symbol channel: {e}")


def publish_main_reports(report_type: str, symbol: str, data: Any):
    """
    Publish main report messages to the global reports channel.

    Args:
        report_type: Type of report (e.g., "market_report", "news_report")
        symbol: Stock symbol
        data: Report data
    """
    message = {
        "type": report_type,
        "symbol": symbol,
        "data": data,
    }

    # Publish to global reports channel (no room: prefix)
    channel = "reports"
    json_message = json.dumps(message)

    try:
        get_publisher_redis_client().publish(channel, json_message)
        print(f"📡 Published report → {channel}: {report_type} for {symbol}")
    except Exception as e:
        print(f"⚠️ Failed to publish main report: {e}")


# ============================================================================
# DEBATE-SPECIFIC PUBLISH FUNCTIONS
# ============================================================================

def publish_debate_point(
    room_id: str,
    party: str,
    round_num: int,
    content: str,
    confidence: float,
    evidence: List[str] = None
):
    """
    Publish a debate point from Bull or Bear.

    Args:
        room_id: Room/channel ID
        party: "bull" or "bear"
        round_num: Current round number
        content: The argument content
        confidence: Confidence score (0-1)
        evidence: List of supporting evidence
    """
    publish_event(
        room_id,
        event_type="debate_point",
        payload={
            "party": party,
            "round": round_num,
            "content": content,
            "confidence": confidence,
            "supporting_evidence": evidence or [],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def publish_debate_progress(
    room_id: str,
    current_round: int,
    max_rounds: int,
    bull_points: int,
    bear_points: int,
    status: str
):
    """
    Publish debate progress update.

    Args:
        room_id: Room/channel ID
        current_round: Current round number
        max_rounds: Maximum rounds
        bull_points: Number of bull points made
        bear_points: Number of bear points made
        status: "in_progress", "completed", "error"
    """
    publish_event(
        room_id,
        event_type="debate_progress",
        payload={
            "current_round": current_round,
            "max_rounds": max_rounds,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "status": status,
        },
    )


def publish_recommendation(
    room_id: str,
    symbol: str,
    recommendation: str,
    confidence: float,
    facilitator_report: str
):
    """
    Publish final recommendation from facilitator.

    Args:
        room_id: Room/channel ID
        symbol: Stock symbol
        recommendation: "BUY", "SELL", "HOLD"
        confidence: Confidence score (0-1)
        facilitator_report: Full facilitator report text
    """
    publish_event(
        room_id,
        event_type="recommendation",
        payload={
            "symbol": symbol,
            "recommendation": recommendation,
            "confidence": confidence,
            "facilitator_report": facilitator_report,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def publish_graph_state(
    room_id: str,
    nodes: List[Dict[str, Any]],
    active_node: str,
    edges: List[Dict[str, str]]
):
    """
    Publish LangGraph state for visualization.

    Args:
        room_id: Room/channel ID
        nodes: List of node objects with id, label, status
        active_node: ID of currently active node
        edges: List of edge objects with from, to
    """
    publish_event(
        room_id,
        event_type="graph_state",
        payload={
            "nodes": nodes,
            "active_node": active_node,
            "edges": edges,
        },
    )


# ============================================================================
# LEGACY FUNCTION (For backward compatibility during migration)
# ============================================================================

def publish_alert(
    symbol: str,
    alert_type: str,
    reason: str,
    severity: str,
    redis_sync=None,  # Ignored - kept for backward compatibility
    trigger_debate: bool = True
):
    """
    Legacy function - redirects to publish_alerts.
    Kept for backward compatibility during migration.
    """
    import httpx
    
    data = {
        "alert_type": alert_type,
        "reason": reason,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat(),
        "trigger_debate": trigger_debate,
    }
    publish_alerts(data, symbol)

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
    # Test publishing
    print("Testing event publisher...")
    publish_event("test-room", "test_event", {"message": "Hello from pathway!"})
    publish_agent_status("test-room", "Test Agent", "RUNNING")
    publish_alerts({"alert_type": "test", "reason": "Testing"}, "TEST")
    print("✅ Test complete!")