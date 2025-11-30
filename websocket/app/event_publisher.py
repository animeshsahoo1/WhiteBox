#event_publisher.py

import json
from typing import Any, Dict
from app.redis_client import redis_sync


def publish_event(room_id: str, event_type: str, payload: Dict[str, Any]):
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


def publish_agent_status(room_id: str, agent: str, status: str):
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
    )


def publish_report(room_id: str, agent: str, report: Any):
    """
    Publish a finished report.
    """

    publish_event(
        room_id,
        event_type="report",
        payload={
            "agent": agent,
            "report": report,
        },
    )

if __name__ == "__main__":
    publish_event("test", "test", "test")