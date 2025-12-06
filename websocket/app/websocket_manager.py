from typing import Dict, Set
from fastapi import WebSocket
import json

class WebSocketManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room_id, set()).add(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms.get(room_id, set()).discard(websocket)

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
                print(f"⚠️ Failed to parse message: {message}")
                return
        
        for ws in list(self.rooms.get(room_id, [])):
            try:
                print(f"📤 Sending to WebSocket: {message}")
                await ws.send_json(message)
            except Exception as e:
                print(f"❌ Failed to send to WebSocket: {e}")
                self.disconnect(room_id, ws)

ws_manager = WebSocketManager()