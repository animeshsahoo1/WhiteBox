from fastapi import FastAPI, WebSocket, WebSocketDisconnect  
from app.websocket_manager import ws_manager
from app.event_publisher import publish_agent_status
from app.redis_util import get_async_redis  # Import the function, not the instance

app = FastAPI(title="WebSocket Server", version="1.0.0")


@app.get("/health")
async def health():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "connections": ws_manager.get_connection_count(),
        "rooms": list(ws_manager.rooms.keys())
    }


@app.get("/ping")
async def ping():
    publish_agent_status("test", "test", "running")
    return {"status": "ok"}

@app.websocket("/ws/reports/{symbol}")  # ✅ ADDED: symbol path parameter
async def websocket_reports(websocket: WebSocket, symbol: str):
    room_id = f"symbol:{symbol}"  # ✅ CHANGED: Dynamic room based on symbol
    print(f"🔌 Attempting WebSocket connection for reports - Symbol: {symbol}")
    print(f"✅ WebSocket will be accepted by manager for room: {room_id}")

    try:
        await ws_manager.connect(room_id, websocket)
        print(f"✅ Connected! Active connections in room '{room_id}': {len(ws_manager.rooms.get(room_id, set()))}")

        redis_async = get_async_redis()
        pubsub = redis_async.pubsub()
        
        # ✅ CHANGED: Subscribe to symbol-specific channel
        channel = f"room:{room_id}"  # This becomes "room:symbol:AAPL"
        await pubsub.subscribe(channel)
        print(f"✅ Subscribed to Redis channel: {channel}")
        
        # ✅ ADDED: Send connection confirmation
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "symbol": symbol,
            "message": f"Connected to {symbol} reports"
        })

        async for msg in pubsub.listen():
            print(f"📬 Raw Redis message for {symbol}: {msg}")  # ✅ ADDED: Debug log
            if msg["type"] == "message":
                message_data = msg["data"]
                if isinstance(message_data, bytes):
                    message_data = message_data.decode('utf-8')
                
                print(f"📨 Broadcasting to {symbol} subscribers: {message_data}")
                await ws_manager.broadcast(room_id, message_data)

    except WebSocketDisconnect:
        print(f"❌ WebSocket disconnected for symbol: {symbol}")
    except Exception as e:
        print(f"❌ Error in WebSocket for {symbol}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"🔌 Cleaning up WebSocket for symbol: {symbol}")
        ws_manager.disconnect(room_id, websocket)
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis_async.close()
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    room_id = "alerts"   
    print("🔌 Attempting WebSocket connection for alerts")
    print("✅ WebSocket will be accepted by manager for alerts")
    
    try:
        await ws_manager.connect(room_id, websocket)  # ✅ This accepts the connection
        
        redis_async = get_async_redis()
        pubsub = redis_async.pubsub()
        await pubsub.subscribe("alerts")
        print(f"✅ Subscribed to Redis channel: alerts")
        
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                # Decode if it's bytes
                message_data = msg["data"]
                if isinstance(message_data, bytes):
                    message_data = message_data.decode('utf-8')
                
                print(f"📨 Received from Redis: {message_data}")
                
                # Broadcast to all connected clients in this room
                await ws_manager.broadcast(room_id, message_data)
                
    except WebSocketDisconnect:  # ✅ FIXED: Proper WebSocket disconnect handling (removed duplicate except)
        print("❌ WebSocket disconnected")
    except Exception as e:
        print(f"❌ Error in WebSocket: {e}")
    finally:
        try:
            ws_manager.disconnect(room_id, websocket)
            await pubsub.unsubscribe("alerts")
            await pubsub.close()
            await redis_async.close()
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
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
    
    try:
        # Subscribe to reports channel
        await pubsub.subscribe("reports")
        print(f"✅ Subscribed to Redis channel: reports (filtering for backtesting)")
        
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                try:
                    import json
                    data = json.loads(msg["data"])
                    # Only forward backtesting_metrics events
                    if data.get("type") == "backtesting_metrics":
                        await ws_manager.broadcast(room_id, msg["data"])
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                except Exception as e:
                    print(f"❌ Error broadcasting message: {e}")
                    
    except Exception as e:
        print(f"❌ WebSocket error for backtesting: {e}")
    finally:
        print(f"🔌 Disconnecting backtesting WebSocket")
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

    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "room": room_id,
        "strategy": strategy.upper(),
        "timestamp": datetime.now().isoformat()
    })

    redis_async = get_async_redis()
    pubsub = redis_async.pubsub()
    
    try:
        await pubsub.subscribe(f"room:{room_id}")
        print(f"✅ Subscribed to Redis channel: room:{room_id}")
        
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws_manager.broadcast(room_id, msg["data"])
                
    except Exception as e:
        print(f"❌ WebSocket error for {strategy}: {e}")
    finally:
        print(f"🔌 Disconnecting {strategy} WebSocket")
        ws_manager.disconnect(room_id, websocket)
        await pubsub.unsubscribe(f"room:{room_id}")
        await pubsub.close()
        await redis_async.close()



@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    WebSocket endpoint for a room.
    Listens to Redis pub/sub and forwards events to frontend.
    """
    print(f"🔌 Attempting WebSocket connection for room: {room_id}")
    print(f"✅ WebSocket will be accepted by manager for room: {room_id}")
    
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
