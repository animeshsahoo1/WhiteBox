"""Bull-Bear Researchers Module."""
from .bull_researcher import create_bull_researcher
from .bear_researcher import create_bear_researcher
from .facilitator import (
    generate_facilitator_report,
    extract_recommendation,
    save_facilitator_report_to_redis,
    start_facilitator_stream,
    stop_facilitator_stream,
    get_facilitator_status,
    is_stream_active,
)
from .tools import retrieve_from_pathway

__all__ = [
    "create_bull_researcher",
    "create_bear_researcher",
    "generate_facilitator_report",
    "extract_recommendation",
    "save_facilitator_report_to_redis",
    "start_facilitator_stream",
    "stop_facilitator_stream",
    "get_facilitator_status",
    "is_stream_active",
    "retrieve_from_pathway",
]
