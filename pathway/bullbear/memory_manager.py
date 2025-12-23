"""
Memory Manager using mem0 for Bull-Bear Debate
Handles memory storage and retrieval for debate context
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from mem0 import Memory, MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    
from .config import MemoryConfig, get_config

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Memory Manager for Bull-Bear Debate using mem0.
    Handles both local and cloud-based memory storage.
    """
    
    @staticmethod
    def _safe_get_content(item: Any) -> str:
        """
        Safely extract content from a memory item.
        Handles cases where item might be a string or dict.
        """
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return item.get("content", item.get("memory", ""))
        return str(item) if item else ""
    
    @staticmethod
    def _safe_get_metadata(item: Any, key: str, default: Any = None) -> Any:
        """Safely get metadata from a memory item"""
        if isinstance(item, dict):
            return item.get("metadata", {}).get(key, default)
        return default
    
    def __init__(self, config: Optional[MemoryConfig] = None, user_id: str = "bullbear_system"):
        self.config = config or get_config().memory
        self.user_id = user_id
        self._memory = None
        self._initialize_memory()
    
    def _initialize_memory(self):
        """Initialize mem0 memory instance"""
        if not MEM0_AVAILABLE:
            logger.warning("mem0 not installed. Using fallback in-memory storage.")
            self._memory = None
            self._fallback_memory: Dict[str, List[Dict]] = {}
            return
            
        try:
            if self.config.use_local:
                # Local mem0 with custom configuration
                config = {
                    "embedder": {
                        "provider": "huggingface",
                        "config": {
                            "model": self.config.embedding_model
                        }
                    },
                    "vector_store": {
                        "provider": "chroma",
                        "config": {
                            "collection_name": self.config.collection_prefix,
                            "path": os.path.join(os.path.dirname(__file__), ".mem0_data")
                        }
                    }
                }
                self._memory = Memory.from_config(config)
                logger.info("Initialized local mem0 memory")
            else:
                # Cloud mem0
                self._memory = MemoryClient(api_key=self.config.mem0_api_key)
                logger.info("Initialized cloud mem0 memory")
        except Exception as e:
            logger.error(f"Failed to initialize mem0: {e}. Using fallback.")
            self._memory = None
            self._fallback_memory = {}
    
    def add_memory(
        self,
        content: str,
        category: str,
        party: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a memory entry.
        
        Args:
            content: The memory content
            category: Category (e.g., 'debate_point', 'market_insight', 'counter_argument')
            party: The party that created this memory ('bull', 'bear', 'facilitator')
            metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        full_metadata = {
            "category": category,
            "party": party,
            "timestamp": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        
        if self._memory is not None:
            try:
                result = self._memory.add(
                    content,
                    user_id=self.user_id,
                    metadata=full_metadata
                )
                return result.get("id", str(hash(content)))
            except Exception as e:
                logger.error(f"Error adding memory to mem0: {e}")
                
        # Fallback storage
        memory_id = str(hash(content + str(datetime.utcnow())))
        if category not in self._fallback_memory:
            self._fallback_memory[category] = []
        self._fallback_memory[category].append({
            "id": memory_id,
            "content": content,
            "metadata": full_metadata
        })
        return memory_id
    
    def search_memories(
        self,
        query: str,
        category: Optional[str] = None,
        party: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories.
        
        Args:
            query: Search query
            category: Filter by category
            party: Filter by party
            limit: Maximum number of results
            
        Returns:
            List of matching memories
        """
        if self._memory is not None:
            try:
                filters = {}
                if category:
                    filters["category"] = category
                if party:
                    filters["party"] = party
                    
                results = self._memory.search(
                    query,
                    user_id=self.user_id,
                    limit=limit
                )
                
                # Defensive: ensure results are dicts
                if results and not isinstance(results, list):
                    logger.warning(f"mem0 search returned non-list: {type(results)}")
                    results = []
                else:
                    # Filter out non-dict items
                    results = [r for r in results if isinstance(r, dict)]
                
                # Filter by metadata if needed
                if filters:
                    results = [
                        r for r in results
                        if all(r.get("metadata", {}).get(k) == v for k, v in filters.items())
                    ]
                
                return results
            except Exception as e:
                logger.error(f"Error searching mem0: {e}")
        
        # Fallback search (simple keyword matching)
        results = []
        query_lower = query.lower()
        
        categories_to_search = [category] if category else list(self._fallback_memory.keys())
        
        for cat in categories_to_search:
            if cat not in self._fallback_memory:
                continue
            for mem in self._fallback_memory.get(cat, []):
                # Defensive: ensure mem is a dict
                if not isinstance(mem, dict):
                    continue
                if party and self._safe_get_metadata(mem, "party") != party:
                    continue
                content = self._safe_get_content(mem)
                if query_lower in content.lower():
                    results.append(mem)
                    
        return results[:limit]
    
    def get_debate_context(
        self,
        query: str,
        party: str,
        limit: int = 5,
        unified: bool = True
    ) -> List[str]:
        """
        Get relevant debate context for a party.
        
        Args:
            query: The topic/point to get context for
            party: 'bull' or 'bear' (used to prioritize, not filter)
            limit: Maximum memories to return
            unified: If True, search ALL memories (both parties) for cross-learning
            
        Returns:
            List of relevant memory contents with party tags
        """
        if unified:
            # Search all memories without party filter - let mem0 find connections
            memories = self.search_memories(
                query=query,
                party=None,  # Don't filter by party
                limit=limit * 2  # Get more to have variety
            )
            # Tag each memory with its party for context
            results = []
            for m in memories:
                # Defensive: ensure m is a dict
                if not isinstance(m, dict):
                    logger.warning(f"Memory item is not a dict: {type(m)}")
                    continue
                content = self._safe_get_content(m)
                mem_party = self._safe_get_metadata(m, "party", "unknown")
                if content:
                    results.append(f"[{mem_party.upper()}]: {content}")
            return results[:limit]
        else:
            # Original behavior - only same party's memories
            memories = self.search_memories(
                query=query,
                party=party,
                limit=limit
            )
            return [
                self._safe_get_content(m)
                for m in memories 
                if m and isinstance(m, dict)
            ]
    
    def is_point_repeated(
        self,
        point: str,
        party: str,
        threshold: float = 0.85
    ) -> bool:
        """
        Check if a point has been made before by this party.
        
        Args:
            point: The point to check
            party: The party making the point
            threshold: Similarity threshold (0-1)
            
        Returns:
            True if point is too similar to existing points
        """
        existing = self.search_memories(
            query=point,
            category="debate_point",
            party=party,
            limit=5
        )
        
        if not existing:
            return False
            
        # Check similarity (using mem0's built-in similarity if available)
        for mem in existing:
            # Defensive: ensure mem is a dict
            if not isinstance(mem, dict):
                logger.warning(f"Memory item is not a dict in is_point_repeated: {type(mem)}")
                continue
            # If mem0 returns a score, use it
            score = mem.get("score", mem.get("similarity", 0))
            if score >= threshold:
                return True
            
            # Fallback: if no score returned, do simple word overlap check
            if score == 0:
                mem_content = self._safe_get_content(mem).lower()
                point_lower = point.lower()
                # Use word overlap as fallback similarity
                words_mem = set(mem_content.split())
                words_point = set(point_lower.split())
                if words_mem and words_point:
                    overlap = len(words_mem & words_point) / len(words_mem | words_point)
                    if overlap >= threshold:
                        return True
                
        return False
    
    def save_debate_point(
        self,
        point: str,
        party: str,
        counter_to: Optional[str] = None,
        evidence: Optional[List[str]] = None
    ) -> str:
        """
        Save a debate point to memory.
        
        Args:
            point: The debate point content
            party: 'bull' or 'bear'
            counter_to: ID of point being countered (if any)
            evidence: Supporting evidence
            
        Returns:
            Memory ID
        """
        return self.add_memory(
            content=point,
            category="debate_point",
            party=party,
            metadata={
                "counter_to": counter_to,
                "evidence": evidence or []
            }
        )
    
    def save_facilitator_validation(
        self,
        recommendation: str,
        was_correct: bool,
        market_validation: str,
        reasoning: str
    ) -> str:
        """
        Save facilitator prediction vs actual outcome to memory.
        This helps learn from past predictions.
        
        Args:
            recommendation: What the facilitator recommended (BUY/HOLD/SELL)
            was_correct: Whether the prediction was correct
            market_validation: What actually happened in the market
            reasoning: Explanation of why it was correct/incorrect
            
        Returns:
            Memory ID
        """
        content = f"""FACILITATOR PREDICTION OUTCOME:
Recommendation: {recommendation}
Was Correct: {was_correct}
Market Reality: {market_validation}
Reasoning: {reasoning}"""
        
        return self.add_memory(
            content=content,
            category="facilitator_validation",
            party="facilitator",
            metadata={
                "recommendation": recommendation,
                "was_correct": was_correct,
                "market_validation": market_validation
            }
        )
    
    def get_all_points(self, party: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all debate points, optionally filtered by party"""
        return self.search_memories(
            query="",
            category="debate_point",
            party=party,
            limit=100
        )
    
    def get_facilitator_history(self, limit: int = 5) -> List[str]:
        """
        Get history of facilitator predictions and outcomes.
        Useful for learning from past prediction accuracy.
        
        Args:
            limit: Maximum number of validations to return
            
        Returns:
            List of facilitator validation summaries
        """
        memories = self.search_memories(
            query="facilitator prediction outcome recommendation",
            category="facilitator_validation",
            party="facilitator",
            limit=limit
        )
        return [
            self._safe_get_content(m)
            for m in memories 
            if m and isinstance(m, dict)
        ]
    
    def clear_session(self):
        """Clear all memories for this session"""
        if self._memory is not None:
            try:
                self._memory.delete_all(user_id=self.user_id)
            except Exception as e:
                logger.error(f"Error clearing mem0 memories: {e}")
        
        self._fallback_memory = {}
