"""
Configuration for Bull-Bear Debate System
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the bull_bear directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


@dataclass
class LLMConfig:
    """LLM Configuration"""
    model: str = "openai/gpt-4o-mini"
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    api_base: str = "https://openrouter.ai/api/v1"
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class MemoryConfig:
    """Mem0 Memory Configuration"""
    embedding_model: str = "all-MiniLM-L6-v2"
    collection_prefix: str = "bullbear"
    mem0_api_key: str = field(default_factory=lambda: os.getenv("MEM0_API_KEY", ""))
    use_local: bool = True  # Use local mem0 if True, cloud if False
    use_mem0: bool = True  # Use mem0 library, else use in-memory fallback


@dataclass
class RAGConfig:
    """RAG Server Configuration"""
    # Default to same server since RAG is at /query endpoint
    base_url: str = field(default_factory=lambda: os.getenv("RAG_SERVER_URL", "http://localhost:8000"))
    timeout: int = 30
    max_retries: int = 3


@dataclass
class ReportsConfig:
    """Reports API Configuration"""
    # Default to same server since Reports are at /reports endpoint
    base_url: str = field(default_factory=lambda: os.getenv("REPORTS_API_URL", "http://localhost:8000"))
    timeout: int = 30


@dataclass
class DebateConfig:
    """Debate Configuration"""
    max_rounds: int = 5
    max_retries_for_unique_point: int = 3
    point_similarity_threshold: float = 0.85
    cache_dir: str = field(default_factory=lambda: os.path.join(os.path.dirname(__file__), "cached_report"))
    debate_dir: str = field(default_factory=lambda: os.path.join(os.path.dirname(__file__), "debate"))
    # Content truncation limits (characters)
    report_summary_limit: int = 500       # For context summaries
    delta_content_limit: int = 3000       # For delta computation
    memory_query_limit: int = 200         # For memory queries
    rag_context_limit: int = 300          # For RAG context building


@dataclass
class BullBearConfig:
    """Main Configuration"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    reports: ReportsConfig = field(default_factory=ReportsConfig)
    debate: DebateConfig = field(default_factory=DebateConfig)


def get_config() -> BullBearConfig:
    """Get default configuration"""
    return BullBearConfig()
