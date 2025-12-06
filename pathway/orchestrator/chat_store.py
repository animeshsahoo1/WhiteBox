"""
Chat Store - Redis-based chat persistence layer.

Handles:
- Chat CRUD operations (create, list, get, delete)
- Message history with sliding window
- Automatic summarization of old messages
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

# Redis connection (reuse existing pattern)
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redis_cache import get_redis_client

# Configuration
MAX_MESSAGES_WINDOW = 20  # Keep last 20 messages in full
SUMMARIZE_BATCH = 10      # When limit hit, summarize oldest 10
TITLE_MAX_LENGTH = 50     # Max chars for auto-generated title

# Redis key patterns
CHAT_LIST_KEY = "chat:list"                    # Sorted set of room_ids by timestamp
CHAT_META_PREFIX = "chat:meta:"                # Hash: {title, created_at, updated_at}
CHAT_MESSAGES_PREFIX = "chat:messages:"        # List: serialized messages
CHAT_SUMMARY_PREFIX = "chat:summary:"          # String: running summary

# Summarization LLM (cheap model)
SUMMARIZE_MODEL = os.getenv("SUMMARIZE_MODEL", "google/gemini-2.0-flash-lite-001")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")

_summarize_llm = None

def get_summarize_llm():
    """Get or create summarization LLM (lazy loading)."""
    global _summarize_llm
    if _summarize_llm is None:
        _summarize_llm = ChatOpenAI(
            model=SUMMARIZE_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            temperature=0,
            max_tokens=300
        )
    return _summarize_llm


@dataclass
class ChatMeta:
    """Chat metadata."""
    room_id: str
    title: str
    created_at: str
    updated_at: str


@dataclass
class Message:
    """Simple message format."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", "")
        )
    
    def to_langchain(self):
        """Convert to LangChain message."""
        if self.role == "user":
            return HumanMessage(content=self.content)
        return AIMessage(content=self.content)


class ChatStore:
    """Redis-based chat storage."""
    
    def __init__(self):
        self.redis = get_redis_client()
    
    # =========================================================================
    # CHAT CRUD
    # =========================================================================
    
    def create_chat(self, first_message: str = None) -> ChatMeta:
        """Create a new chat and return its metadata."""
        room_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        # Auto-generate title from first message or use timestamp
        if first_message:
            title = first_message[:TITLE_MAX_LENGTH].strip()
            if len(first_message) > TITLE_MAX_LENGTH:
                title += "..."
        else:
            title = f"Chat {datetime.utcnow().strftime('%b %d, %I:%M %p')}"
        
        meta = ChatMeta(
            room_id=room_id,
            title=title,
            created_at=now,
            updated_at=now
        )
        
        # Save to Redis
        self.redis.hset(f"{CHAT_META_PREFIX}{room_id}", mapping={
            "title": meta.title,
            "created_at": meta.created_at,
            "updated_at": meta.updated_at
        })
        
        # Add to sorted set (score = timestamp for ordering)
        timestamp_score = datetime.utcnow().timestamp()
        self.redis.zadd(CHAT_LIST_KEY, {room_id: timestamp_score})
        
        print(f"✅ Created new chat: {room_id} - '{title}'")
        return meta
    
    def list_chats(self, limit: int = 50, offset: int = 0) -> List[ChatMeta]:
        """List all chats, ordered by most recent first."""
        # Get room_ids from sorted set (reverse order for most recent first)
        room_ids = self.redis.zrevrange(CHAT_LIST_KEY, offset, offset + limit - 1)
        
        chats = []
        for room_id in room_ids:
            meta = self.get_chat_meta(room_id)
            if meta:
                chats.append(meta)
        
        return chats
    
    def get_chat_meta(self, room_id: str) -> Optional[ChatMeta]:
        """Get chat metadata."""
        data = self.redis.hgetall(f"{CHAT_META_PREFIX}{room_id}")
        if not data:
            return None
        
        return ChatMeta(
            room_id=room_id,
            title=data.get("title", "Untitled"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )
    
    def delete_chat(self, room_id: str) -> bool:
        """Delete a chat and all its data."""
        try:
            # Delete all related keys
            self.redis.delete(
                f"{CHAT_META_PREFIX}{room_id}",
                f"{CHAT_MESSAGES_PREFIX}{room_id}",
                f"{CHAT_SUMMARY_PREFIX}{room_id}"
            )
            # Remove from sorted set
            self.redis.zrem(CHAT_LIST_KEY, room_id)
            print(f"🗑️ Deleted chat: {room_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to delete chat: {e}")
            return False
    
    def chat_exists(self, room_id: str) -> bool:
        """Check if a chat exists."""
        return self.redis.exists(f"{CHAT_META_PREFIX}{room_id}") > 0
    
    # =========================================================================
    # MESSAGE OPERATIONS
    # =========================================================================
    
    def get_messages(self, room_id: str) -> List[Message]:
        """Get all messages for a chat (from Redis list)."""
        raw_messages = self.redis.lrange(f"{CHAT_MESSAGES_PREFIX}{room_id}", 0, -1)
        messages = []
        for raw in raw_messages:
            try:
                data = json.loads(raw)
                messages.append(Message.from_dict(data))
            except json.JSONDecodeError:
                continue
        return messages
    
    def get_summary(self, room_id: str) -> str:
        """Get the conversation summary for a chat."""
        return self.redis.get(f"{CHAT_SUMMARY_PREFIX}{room_id}") or ""
    
    def add_message(self, room_id: str, role: str, content: str) -> None:
        """Add a message to the chat."""
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Append to Redis list
        self.redis.rpush(
            f"{CHAT_MESSAGES_PREFIX}{room_id}",
            json.dumps(message.to_dict())
        )
        
        # Update chat metadata
        self.redis.hset(
            f"{CHAT_META_PREFIX}{room_id}",
            "updated_at",
            datetime.utcnow().isoformat()
        )
        
        # Update title if this is the first user message
        if role == "user":
            msg_count = self.redis.llen(f"{CHAT_MESSAGES_PREFIX}{room_id}")
            if msg_count == 1:
                title = content[:TITLE_MAX_LENGTH].strip()
                if len(content) > TITLE_MAX_LENGTH:
                    title += "..."
                self.redis.hset(f"{CHAT_META_PREFIX}{room_id}", "title", title)
        
        # Check if we need to summarize
        self._maybe_summarize(room_id)
    
    def _maybe_summarize(self, room_id: str) -> None:
        """Summarize old messages if we exceed the window limit."""
        msg_count = self.redis.llen(f"{CHAT_MESSAGES_PREFIX}{room_id}")
        
        if msg_count <= MAX_MESSAGES_WINDOW:
            return
        
        # Get oldest messages to summarize
        oldest_raw = self.redis.lrange(
            f"{CHAT_MESSAGES_PREFIX}{room_id}",
            0,
            SUMMARIZE_BATCH - 1
        )
        
        oldest_messages = []
        for raw in oldest_raw:
            try:
                data = json.loads(raw)
                oldest_messages.append(Message.from_dict(data))
            except json.JSONDecodeError:
                continue
        
        if not oldest_messages:
            return
        
        # Generate summary
        try:
            summary = self._summarize_messages(oldest_messages, room_id)
            
            # Get existing summary and prepend
            existing_summary = self.get_summary(room_id)
            if existing_summary:
                new_summary = f"{existing_summary}\n\n{summary}"
            else:
                new_summary = summary
            
            # Save updated summary
            self.redis.set(f"{CHAT_SUMMARY_PREFIX}{room_id}", new_summary)
            
            # Remove summarized messages from list (batched with pipeline)
            pipe = self.redis.pipeline()
            for _ in range(SUMMARIZE_BATCH):
                pipe.lpop(f"{CHAT_MESSAGES_PREFIX}{room_id}")
            pipe.execute()
            
            print(f"📝 Summarized {SUMMARIZE_BATCH} messages for chat {room_id[:8]}...")
            
        except Exception as e:
            print(f"⚠️ Summarization failed: {e}")
    
    def _summarize_messages(self, messages: List[Message], room_id: str) -> str:
        """Generate a summary of messages using LLM."""
        llm = get_summarize_llm()
        
        # Format messages for summarization
        formatted = "\n".join([
            f"{msg.role.upper()}: {msg.content}" for msg in messages
        ])
        
        prompt = f"""Summarize this conversation in 2-3 concise sentences, preserving:
- Key topics discussed
- Important decisions or preferences mentioned
- Relevant data points or symbols mentioned

Conversation:
{formatted}

Summary:"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    
    # =========================================================================
    # CONTEXT BUILDING (for LangGraph)
    # =========================================================================
    
    def get_context_for_agent(self, room_id: str) -> tuple[str, List]:
        """
        Get conversation context for the agent.
        
        Returns:
            (summary, recent_messages_as_langchain)
        """
        summary = self.get_summary(room_id)
        messages = self.get_messages(room_id)
        
        # Convert to LangChain messages
        langchain_messages = [msg.to_langchain() for msg in messages]
        
        return summary, langchain_messages
    
    def get_history_for_api(self, room_id: str) -> Dict[str, Any]:
        """
        Get chat history formatted for API response.
        
        Returns:
            {
                "room_id": str,
                "title": str,
                "messages": [{"role": str, "content": str, "timestamp": str}],
                "summary": str,
                "message_count": int
            }
        """
        meta = self.get_chat_meta(room_id)
        if not meta:
            return None
        
        messages = self.get_messages(room_id)
        summary = self.get_summary(room_id)
        
        return {
            "room_id": room_id,
            "title": meta.title,
            "created_at": meta.created_at,
            "updated_at": meta.updated_at,
            "messages": [msg.to_dict() for msg in messages],
            "summary": summary,
            "message_count": len(messages)
        }


# Singleton instance
_chat_store = None

def get_chat_store() -> ChatStore:
    """Get or create the ChatStore singleton."""
    global _chat_store
    if _chat_store is None:
        _chat_store = ChatStore()
    return _chat_store
