from typing import Dict, Set
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room_id, set()).add(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms.get(room_id, set()).discard(websocket)

    async def broadcast(self, room_id: str, message: dict):
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(message)
            except:
                self.disconnect(room_id, ws)

ws_manager = WebSocketManager()
