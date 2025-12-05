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
    
    # ✅ Accept the connection FIRST
    await websocket.accept()
    print(f"✅ WebSocket accepted for room: {room_id}")
    
    try:
        await ws_manager.connect(room_id, websocket)
        
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

@app.websocket("/ws/reports")
async def websocket_reports(websocket: WebSocket):
    room_id = "reports"  
    print("🔌 Attempting WebSocket connection for reports")
    
    # ✅ Accept the connection FIRST
    await websocket.accept()
    print("✅ WebSocket accepted for reports")

    await ws_manager.connect(room_id, websocket)

    redis_async = get_async_redis()
    pubsub = redis_async.pubsub()
    await pubsub.subscribe("reports")
    print(f"✅ Subscribed to Redis channel: reports")

    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws_manager.broadcast(room_id, msg["data"])

    finally:
        ws_manager.disconnect(room_id, websocket)
        await pubsub.unsubscribe("reports")
        await pubsub.close()
        await redis_async.close()

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    room_id = "alerts"   
    print("🔌 Attempting WebSocket connection for alerts")
    
    # ✅ Accept the connection FIRST
    await websocket.accept()
    print("✅ WebSocket accepted for alerts")

    await ws_manager.connect(room_id, websocket)

    redis_async = get_async_redis()
    pubsub = redis_async.pubsub()
    await pubsub.subscribe("alerts")
    print(f"✅ Subscribed to Redis channel: alerts")
    
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws_manager.broadcast(room_id, msg["data"])

    finally:
        ws_manager.disconnect(room_id, websocket)
        await pubsub.unsubscribe("alerts")
        await pubsub.close()
        await redis_async.close()


@app.websocket("/ws/backtesting")
async def websocket_backtesting(websocket: WebSocket):
    """
    WebSocket endpoint for all backtesting metrics updates.
    Subscribes to the 'reports' channel and filters for backtesting_metrics.
    """
    room_id = "backtesting"   
    print("🔌 Attempting WebSocket connection for backtesting")
    
    await ws_manager.connect(room_id, websocket)
    print("✅ WebSocket accepted for backtesting")

    redis_async = get_async_redis()
    pubsub = redis_async.pubsub()
    # Subscribe to reports channel (backtesting publishes there)
    await pubsub.subscribe("reports")
    print(f"✅ Subscribed to Redis channel: reports (filtering for backtesting)")
    
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                try:
                    import json
                    data = json.loads(msg["data"])
                    # Only forward backtesting_metrics events
                    if data.get("type") == "backtesting_metrics":
                        await ws_manager.broadcast(room_id, msg["data"])
                except:
                    pass

    finally:
        ws_manager.disconnect(room_id, websocket)
        await pubsub.unsubscribe("reports")
        await pubsub.close()
        await redis_async.close()


@app.websocket("/ws/backtesting/{strategy}")
async def websocket_backtesting_strategy(websocket: WebSocket, strategy: str):
    """
    WebSocket endpoint for a specific strategy's backtesting updates.
    Subscribes to room:backtesting:{strategy} channel.
    """
    room_id = f"backtesting:{strategy.upper()}"   
    print(f"🔌 Attempting WebSocket connection for backtesting strategy: {strategy}")
    
    await ws_manager.connect(room_id, websocket)
    print(f"✅ WebSocket accepted for backtesting strategy: {strategy}")

    redis_async = get_async_redis()
    pubsub = redis_async.pubsub()
    await pubsub.subscribe(f"room:{room_id}")
    print(f"✅ Subscribed to Redis channel: room:{room_id}")
    
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws_manager.broadcast(room_id, msg["data"])

    finally:
        ws_manager.disconnect(room_id, websocket)
        await pubsub.unsubscribe(f"room:{room_id}")
        await pubsub.close()
        await redis_async.close()