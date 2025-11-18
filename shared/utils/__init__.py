"""Shared utilities for Phase 2"""

from .kafka_client import (
    create_kafka_consumer,
    create_kafka_producer,
    produce_message,
    consume_messages,
)

from .llm_utils import (
    create_openai_client,
    chat_completion,
    generate_with_system_prompt,
    extract_json_from_response,
)

from .logging_config import (
    setup_logging,
    get_logger,
)

__all__ = [
    "create_kafka_consumer",
    "create_kafka_producer",
    "produce_message",
    "consume_messages",
    "create_openai_client",
    "chat_completion",
    "generate_with_system_prompt",
    "extract_json_from_response",
    "setup_logging",
    "get_logger",
]
