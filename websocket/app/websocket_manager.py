from typing import Dict, Set
from fastapi import WebSocket
import json
import os

DEBUG = os.getenv("DEBUG", "true").lower() == "true"


class WebSocketManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        """Add websocket to room. Does NOT call accept() - caller must accept first."""
        self.rooms.setdefault(room_id, set()).add(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms.get(room_id, set()).discard(websocket)
    
    def get_connection_count(self, room_id: str = None) -> int:
        """Get number of active connections, optionally for a specific room."""
        if room_id:
            return len(self.rooms.get(room_id, set()))
        return sum(len(sockets) for sockets in self.rooms.values())

    async def broadcast(self, room_id: str, message):
        """
        Broadcast message to all websockets in a room.
        message can be either a string (JSON) or a dict.
        """
        # If message is a string (from Redis), parse it to dict
        if isinstance(message, (str, bytes)):
            try:
                message = json.loads(message)
            except:
                print(f"⚠️ Failed to parse message: {message[:100] if message else 'empty'}")
                return
        
        sockets = list(self.rooms.get(room_id, []))
        if not sockets:
            return
        
        if DEBUG:
            print(f"📤 Broadcasting to {len(sockets)} clients in {room_id}")
        
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                if DEBUG:
                    print(f"❌ Failed to send to WebSocket: {e}")
                self.disconnect(room_id, ws)


ws_manager = WebSocketManager()