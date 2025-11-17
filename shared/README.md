# Shared Utilities

Shared utility functions and helpers used across Phase 2 components.

## Contents

### Kafka Client (`kafka_client.py`)

Utilities for Kafka producer/consumer management:

- `create_kafka_consumer()` - Create configured Kafka consumer
- `create_kafka_producer()` - Create configured Kafka producer
- `produce_message()` - Send message to Kafka topic
- `consume_messages()` - Consume messages in a loop with callback

### LLM Utils (`llm_utils.py`)

OpenAI LLM utilities:

- `create_openai_client()` - Initialize OpenAI client
- `chat_completion()` - Generate chat completion
- `generate_with_system_prompt()` - Helper for system + user prompts
- `extract_json_from_response()` - Extract JSON from markdown code blocks

### Logging Config (`logging_config.py`)

Centralized logging configuration:

- `setup_logging()` - Configure logging for all components
- `get_logger()` - Get logger for specific module

## Usage

```python
from shared.utils import (
    create_kafka_consumer,
    create_openai_client,
    setup_logging
)

# Setup logging
setup_logging(level="INFO", log_file="app.log")

# Create Kafka consumer
consumer = create_kafka_consumer(
    bootstrap_servers="kafka:9092",
    group_id="my-group",
    topics=["my-topic"]
)

# Create OpenAI client
client = create_openai_client(api_key="sk-...")
```

## Installation

These utilities are included when you install phase2 requirements:

```bash
pip install -r phase2/requirements.txt
```

## License

MIT License
