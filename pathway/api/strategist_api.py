"""
Strategist API Router

Provides HTTP endpoints for the LangGraph + Mem0 Strategist agent:
- POST /strategist/chat - Send message and get response
- POST /strategist/chat/stream - SSE streaming response
- POST /strategist/new - Start new conversation
- GET /strategist/history/{user_id} - Get chat history (memories)
- DELETE /strategist/memory/{user_id} - Clear user memories
- GET /strategist/status - Check if Strategist is ready

Integrates with WebSocket for real-time updates via Redis Pub/Sub.
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import event publisher for WebSocket integration
try:
    from event_publisher import publish_event, publish_agent_status
    HAS_EVENT_PUBLISHER = True
except ImportError:
    HAS_EVENT_PUBLISHER = False

router = APIRouter(prefix="/strategist", tags=["Strategist Agent"])

# Global Strategist instance (singleton)
_strategist = None
_strategist_lock = asyncio.Lock()


async def get_strategist():
    """Get or create the Strategist singleton."""
    global _strategist
    
    async with _strategist_lock:
        if _strategist is None:
            from orchestrator.langgraph_agent import Strategist
            _strategist = Strategist()
            await _strategist.initialize()
        return _strategist


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    user_id: str = "default_user"
    room_id: Optional[str] = None  # For WebSocket event publishing


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    message: str
    response: str
    user_id: str
    thread_id: str
    timestamp: str


class NewChatRequest(BaseModel):
    """Request to start new conversation."""
    user_id: str = "default_user"


class NewChatResponse(BaseModel):
    """Response from new chat endpoint."""
    user_id: str
    thread_id: str
    message: str
    timestamp: str


class MemoryResponse(BaseModel):
    """Response with user memories."""
    user_id: str
    memories: list
    count: int
    timestamp: str


class StatusResponse(BaseModel):
    """Strategist status response."""
    status: str
    initialized: bool
    mcp_connected: bool
    timestamp: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def publish_strategist_event(room_id: str, event_type: str, data: dict):
    """Publish event to WebSocket via Redis if available."""
    if HAS_EVENT_PUBLISHER and room_id:
        try:
            from redis_cache import get_redis_client
            redis_client = get_redis_client()
            publish_event(room_id, event_type, data, redis_client)
        except Exception as e:
            print(f"[WARN] Failed to publish event: {e}")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Check Strategist agent status."""
    global _strategist
    
    initialized = _strategist is not None and _strategist._initialized
    mcp_connected = initialized and _strategist.mcp_client is not None
    
    return StatusResponse(
        status="ready" if initialized else "not_initialized",
        initialized=initialized,
        mcp_connected=mcp_connected,
        timestamp=datetime.utcnow().isoformat()
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the Strategist and get a response.
    
    Optionally provide room_id to publish events to WebSocket.
    """
    try:
        strategist = await get_strategist()
        
        # Publish "thinking" event if room_id provided
        if request.room_id:
            publish_strategist_event(request.room_id, "strategist_thinking", {
                "user_id": request.user_id,
                "message": request.message
            })
        
        # Get response from agent
        response = await strategist.chat(request.message, user_id=request.user_id)
        
        # Publish response event
        if request.room_id:
            publish_strategist_event(request.room_id, "strategist_response", {
                "user_id": request.user_id,
                "response": response
            })
        
        return ChatResponse(
            message=request.message,
            response=response,
            user_id=request.user_id,
            thread_id=strategist.thread_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        # Publish error event
        if request.room_id:
            publish_strategist_event(request.room_id, "strategist_error", {
                "error": str(e)
            })
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream a response from the Strategist using Server-Sent Events (SSE).
    
    Returns chunked response as the agent generates it.
    """
    
    async def generate() -> AsyncGenerator[str, None]:
        try:
            strategist = await get_strategist()
            
            # Send start event
            yield f"data: {json.dumps({'event': 'start', 'user_id': request.user_id})}\n\n"
            
            # Publish "thinking" event
            if request.room_id:
                publish_strategist_event(request.room_id, "strategist_thinking", {
                    "user_id": request.user_id,
                    "message": request.message
                })
            
            # Stream response chunks
            full_response = ""
            async for chunk in strategist.stream_chat(request.message, user_id=request.user_id):
                full_response += chunk
                yield f"data: {json.dumps({'event': 'chunk', 'content': chunk})}\n\n"
                
                # Also publish to WebSocket if room_id provided
                if request.room_id:
                    publish_strategist_event(request.room_id, "strategist_chunk", {
                        "content": chunk
                    })
            
            # Send completion event
            yield f"data: {json.dumps({'event': 'done', 'full_response': full_response})}\n\n"
            
            # Publish complete response
            if request.room_id:
                publish_strategist_event(request.room_id, "strategist_response", {
                    "user_id": request.user_id,
                    "response": full_response
                })
                
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/new", response_model=NewChatResponse)
async def new_chat(request: NewChatRequest):
    """
    Start a new conversation thread.
    
    Preserves Mem0 memories but clears conversation history.
    """
    try:
        strategist = await get_strategist()
        strategist.new_conversation()
        
        return NewChatResponse(
            user_id=request.user_id,
            thread_id=strategist.thread_id,
            message="New conversation started. Your memories are preserved.",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/{user_id}", response_model=MemoryResponse)
async def get_memories(user_id: str):
    """
    Get all stored memories for a user.
    
    These are persistent insights learned from past conversations.
    """
    try:
        strategist = await get_strategist()
        memories = await strategist.get_user_memories(user_id)
        
        return MemoryResponse(
            user_id=user_id,
            memories=memories,
            count=len(memories),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/{user_id}")
async def clear_memories(user_id: str):
    """
    Clear all memories for a user.
    
    This permanently deletes learned preferences and history.
    """
    try:
        strategist = await get_strategist()
        success = await strategist.clear_memories(user_id)
        
        if success:
            return {
                "user_id": user_id,
                "message": "All memories cleared successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear memories")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{user_id}")
async def get_user_threads(user_id: str):
    """
    Get conversation thread info for a user.
    
    Note: With MemorySaver, threads are ephemeral (in-memory only).
    """
    try:
        strategist = await get_strategist()
        
        return {
            "user_id": user_id,
            "current_thread": strategist.thread_id,
            "note": "Conversation history is stored in-memory. New threads start fresh but preserve Mem0 memories.",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
