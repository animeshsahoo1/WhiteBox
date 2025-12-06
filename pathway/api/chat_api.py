"""
Chat API Router

Provides HTTP endpoints for ChatGPT-like multi-chat system:
- POST /chat/new           - Create new chat (returns room_id)
- GET  /chat/list          - List all chats with titles/timestamps
- GET  /chat/{room_id}     - Get chat history
- DELETE /chat/{room_id}   - Delete chat
- POST /chat/{room_id}     - Send message and get response

Integrates with LangGraph agent and WebSocket for real-time updates.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import guardrails
from guardrails import guard_input, guard_output

# Import event publisher for WebSocket integration
try:
    from event_publisher import publish_event, publish_agent_status, publish_report
    HAS_EVENT_PUBLISHER = True
except ImportError:
    HAS_EVENT_PUBLISHER = False

router = APIRouter(prefix="/chat", tags=["Chat"])

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

class NewChatResponse(BaseModel):
    """Response from new chat endpoint."""
    room_id: str
    title: str
    created_at: str
    message: str


class ChatListItem(BaseModel):
    """Single chat in list response."""
    room_id: str
    title: str
    created_at: str
    updated_at: str


class ChatListResponse(BaseModel):
    """Response from list chats endpoint."""
    chats: List[ChatListItem]
    count: int


class MessageItem(BaseModel):
    """Single message in history."""
    role: str
    content: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    """Response from get chat history endpoint."""
    room_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[MessageItem]
    summary: str
    message_count: int


class ChatMessageRequest(BaseModel):
    """Request body for sending a message."""
    message: str


class ChatMessageResponse(BaseModel):
    """Response from chat endpoint."""
    room_id: str
    message: str
    response: str
    timestamp: str


class DeleteChatResponse(BaseModel):
    """Response from delete chat endpoint."""
    room_id: str
    deleted: bool
    message: str


class StatusResponse(BaseModel):
    """Chat system status response."""
    status: str
    initialized: bool
    mcp_connected: bool
    timestamp: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def publish_chat_event(room_id: str, event_type: str, data: dict):
    """Publish event to WebSocket via Redis if available."""
    if HAS_EVENT_PUBLISHER and room_id:
        try:
            if event_type == "chat_thinking":
                publish_agent_status(room_id, "Strategist Agent", "THINKING")
            elif event_type == "chat_response":
                publish_report(room_id, "Strategist Agent", data)
                publish_agent_status(room_id, "Strategist Agent", "COMPLETED")
            elif event_type == "chat_error":
                publish_agent_status(room_id, "Strategist Agent", "FAILED")
            else:
                publish_event(room_id, event_type, data)
        except Exception as e:
            print(f"[WARN] Failed to publish event: {e}")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Check chat system status."""
    global _strategist
    
    initialized = _strategist is not None and _strategist._initialized
    mcp_connected = initialized and _strategist.mcp_client is not None
    
    return StatusResponse(
        status="ready" if initialized else "not_initialized",
        initialized=initialized,
        mcp_connected=mcp_connected,
        timestamp=datetime.utcnow().isoformat()
    )


@router.post("/new", response_model=NewChatResponse)
async def create_new_chat():
    """
    Create a new chat session.
    
    Returns a new room_id that can be used for messaging.
    """
    try:
        from orchestrator.chat_store import get_chat_store
        
        store = get_chat_store()
        meta = store.create_chat()
        
        return NewChatResponse(
            room_id=meta.room_id,
            title=meta.title,
            created_at=meta.created_at,
            message="New chat created successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=ChatListResponse)
async def list_chats(limit: int = 50, offset: int = 0):
    """
    List all chats, ordered by most recent first.
    
    Query params:
    - limit: Max number of chats to return (default 50)
    - offset: Pagination offset (default 0)
    """
    try:
        from orchestrator.chat_store import get_chat_store
        
        store = get_chat_store()
        chats = store.list_chats(limit=limit, offset=offset)
        
        return ChatListResponse(
            chats=[
                ChatListItem(
                    room_id=chat.room_id,
                    title=chat.title,
                    created_at=chat.created_at,
                    updated_at=chat.updated_at
                )
                for chat in chats
            ],
            count=len(chats)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{room_id}", response_model=ChatHistoryResponse)
async def get_chat_history(room_id: str):
    """
    Get full chat history for a room.
    
    Returns all messages and the conversation summary.
    """
    try:
        from orchestrator.chat_store import get_chat_store
        
        store = get_chat_store()
        
        if not store.chat_exists(room_id):
            raise HTTPException(status_code=404, detail=f"Chat {room_id} not found")
        
        history = store.get_history_for_api(room_id)
        
        return ChatHistoryResponse(
            room_id=history["room_id"],
            title=history["title"],
            created_at=history["created_at"],
            updated_at=history["updated_at"],
            messages=[
                MessageItem(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg.get("timestamp", "")
                )
                for msg in history["messages"]
            ],
            summary=history["summary"],
            message_count=history["message_count"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{room_id}", response_model=DeleteChatResponse)
async def delete_chat(room_id: str):
    """
    Delete a chat and all its history.
    
    This action is permanent and cannot be undone.
    """
    try:
        from orchestrator.chat_store import get_chat_store
        
        store = get_chat_store()
        
        if not store.chat_exists(room_id):
            raise HTTPException(status_code=404, detail=f"Chat {room_id} not found")
        
        success = store.delete_chat(room_id)
        
        return DeleteChatResponse(
            room_id=room_id,
            deleted=success,
            message="Chat deleted successfully" if success else "Failed to delete chat"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{room_id}", response_model=ChatMessageResponse)
async def send_message(room_id: str, request: ChatMessageRequest):
    """
    Send a message to a chat and get a response.
    
    The message is added to chat history and processed by the Strategist agent.
    Publishes events to WebSocket for real-time updates.
    """
    try:
        from orchestrator.chat_store import get_chat_store
        
        store = get_chat_store()
        
        # Auto-create chat if it doesn't exist
        if not store.chat_exists(room_id):
            # Create new chat with this room_id
            store.redis.hset(f"chat:meta:{room_id}", mapping={
                "title": request.message[:50] + ("..." if len(request.message) > 50 else ""),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })
            store.redis.zadd("chat:list", {room_id: datetime.utcnow().timestamp()})
        
        # ===== INPUT GUARDRAILS =====
        input_guard = guard_input(request.message)
        if not input_guard.allowed:
            return ChatMessageResponse(
                room_id=room_id,
                message=request.message,
                response=input_guard.message,
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Get the strategist agent
        strategist = await get_strategist()
        
        # Publish "thinking" event
        publish_chat_event(room_id, "chat_thinking", {
            "room_id": room_id,
            "message": request.message
        })
        
        # Save user message to history BEFORE processing
        store.add_message(room_id, "user", request.message)
        
        # Get response from agent
        response = await strategist.chat(
            message=request.message,
            room_id=room_id
        )
        
        # ===== OUTPUT GUARDRAILS =====
        output_guard = guard_output(response)
        final_response = output_guard.message
        
        # Save assistant response to history
        store.add_message(room_id, "assistant", final_response)
        
        # Publish response event
        publish_chat_event(room_id, "chat_response", {
            "room_id": room_id,
            "response": final_response
        })
        
        return ChatMessageResponse(
            room_id=room_id,
            message=request.message,
            response=final_response,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        publish_chat_event(room_id, "chat_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
