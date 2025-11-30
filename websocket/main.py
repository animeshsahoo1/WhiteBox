from fastapi import FastAPI, WebSocket
from app.websocket_manager import ws_manager
from app.event_publisher import publish_agent_status
from app.redis_util import get_async_redis  # Import the function, not the instance

app = FastAPI()

@app.get("/ping")
async def ping():
    publish_agent_status("test", "test", "running")
    return {"status": "ok"}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    WebSocket endpoint for a room.
    Listens to Redis pub/sub and forwards events to frontend.
    """
    print(f"🔌 Attempting WebSocket connection for room: {room_id}")
    
    try:
        await ws_manager.connect(room_id, websocket)
        print(f"✅ WebSocket connected for room: {room_id}")
        
        # Create fresh Redis connection
        redis_async = get_async_redis()
        pubsub = redis_async.pubsub()
        await pubsub.subscribe(f"room:{room_id}")
        print(f"✅ Subscribed to Redis channel: room:{room_id}")
        
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                print(f"📨 Received message: {msg['data']}")
                await ws_manager.broadcast(room_id, msg["data"])
    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print(f"🔌 Closing WebSocket for room: {room_id}")
        ws_manager.disconnect(room_id, websocket)
        try:
            await pubsub.unsubscribe(f"room:{room_id}")
            await pubsub.close()
            await redis_async.close()
        except:
            pass

@app.on_event("startup")
async def startup_event():
    publish_agent_status("test", "test", "starting")