"""
Agentic Memory System for Bull-Bear Debate.
Simplified version adapted from A-mem.
"""
from typing import List, Dict, Optional, Any, Tuple
import uuid
from datetime import datetime
import json
import logging

from .llm_controller import LLMController
from .retrievers import ChromaRetriever

logger = logging.getLogger(__name__)


class MemoryNote:
    """A memory note that represents a single unit of information."""
    
    def __init__(self, 
                 content: str,
                 id: Optional[str] = None,
                 keywords: Optional[List[str]] = None,
                 links: Optional[Dict] = None,
                 retrieval_count: Optional[int] = None,
                 timestamp: Optional[str] = None,
                 last_accessed: Optional[str] = None,
                 context: Optional[str] = None,
                 evolution_history: Optional[List] = None,
                 category: Optional[str] = None,
                 tags: Optional[List[str]] = None):
        self.content = content
        self.id = id or str(uuid.uuid4())
        self.keywords = keywords or []
        self.links = links or []
        self.context = context or "General"
        self.category = category or "Uncategorized"
        self.tags = tags or []
        
        current_time = datetime.now().strftime("%Y%m%d%H%M")
        self.timestamp = timestamp or current_time
        self.last_accessed = last_accessed or current_time
        self.retrieval_count = retrieval_count or 0
        self.evolution_history = evolution_history or []


class AgenticMemorySystem:
    """Core memory system that manages memory notes and their evolution."""
    
    def __init__(self, 
                 model_name: str = 'all-MiniLM-L6-v2',
                 llm_backend: str = "openai",
                 llm_model: str = "gpt-4o-mini",
                 evo_threshold: int = 100,
                 api_key: Optional[str] = None,
                 collection_name: str = "memories"):
        self.memories = {}
        self.model_name = model_name
        self.collection_name = collection_name
        
        self.retriever = ChromaRetriever(
            collection_name=self.collection_name, 
            model_name=self.model_name
        )
        self.llm_controller = LLMController(llm_backend, llm_model, api_key)
        self.evo_cnt = 0
        self.evo_threshold = evo_threshold

    def add_note(self, content: str, time: str = None, **kwargs) -> str:
        """Add a new memory note."""
        if time is not None:
            kwargs['timestamp'] = time
        note = MemoryNote(content=content, **kwargs)
        
        self.memories[note.id] = note
        
        metadata = {
            "id": note.id,
            "content": note.content,
            "keywords": note.keywords,
            "links": note.links,
            "retrieval_count": note.retrieval_count,
            "timestamp": note.timestamp,
            "last_accessed": note.last_accessed,
            "context": note.context,
            "evolution_history": note.evolution_history,
            "category": note.category,
            "tags": note.tags
        }
        self.retriever.add_document(note.content, metadata, note.id)
        return note.id

    def find_related_memories(self, query: str, k: int = 5) -> Tuple[str, List[int]]:
        """Find related memories using ChromaDB retrieval."""
        if not self.memories:
            return "", []
            
        try:
            results = self.retriever.search(query, k)
            memory_str = ""
            indices = []
            
            if 'ids' in results and results['ids'] and len(results['ids']) > 0 and len(results['ids'][0]) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    if i < len(results['metadatas'][0]):
                        metadata = results['metadatas'][0][i]
                        memory_str += f"memory index:{i}\ttalk start time:{metadata.get('timestamp', '')}\tmemory content: {metadata.get('content', '')}\tmemory context: {metadata.get('context', '')}\tmemory keywords: {str(metadata.get('keywords', []))}\tmemory tags: {str(metadata.get('tags', []))}\n"
                        indices.append(i)
                    
            return memory_str, indices
        except Exception as e:
            logger.error(f"Error in find_related_memories: {str(e)}")
            return "", []

    def search_agentic(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for memories using ChromaDB retrieval."""
        if not self.memories:
            return []
            
        try:
            results = self.retriever.search(query, k)
            memories = []
            seen_ids = set()
            
            if ('ids' not in results or not results['ids'] or 
                len(results['ids']) == 0 or len(results['ids'][0]) == 0):
                return []
                
            for i, doc_id in enumerate(results['ids'][0][:k]):
                if doc_id in seen_ids:
                    continue
                    
                if i < len(results['metadatas'][0]):
                    metadata = results['metadatas'][0][i]
                    memory_dict = {
                        'id': doc_id,
                        'content': metadata.get('content', ''),
                        'context': metadata.get('context', ''),
                        'keywords': metadata.get('keywords', []),
                        'tags': metadata.get('tags', []),
                        'timestamp': metadata.get('timestamp', ''),
                        'category': metadata.get('category', 'Uncategorized'),
                        'is_neighbor': False
                    }
                    
                    if 'distances' in results and len(results['distances']) > 0 and i < len(results['distances'][0]):
                        memory_dict['score'] = results['distances'][0][i]
                        
                    memories.append(memory_dict)
                    seen_ids.add(doc_id)
            
            return memories[:k]
        except Exception as e:
            logger.error(f"Error in search_agentic: {str(e)}")
            return []

    def read(self, memory_id: str) -> Optional[MemoryNote]:
        """Retrieve a memory note by its ID."""
        return self.memories.get(memory_id)
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory note by its ID."""
        if memory_id in self.memories:
            self.retriever.delete_document(memory_id)
            del self.memories[memory_id]
            return True
        return False
