"""Utility functions for Kafka operations - Optimized with connection pooling & batching"""
import os
import json
import atexit
from datetime import datetime
from threading import Lock
from typing import Optional, List, Dict, Any
from kafka import KafkaProducer
from dotenv import load_dotenv

load_dotenv()

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:29092')

# === OPTIMIZATION: Connection pooling - reuse single producer instance ===
_producer_instance: Optional[KafkaProducer] = None
_producer_lock = Lock()

# === OPTIMIZATION: Message batching ===
_message_buffer: Dict[str, List[bytes]] = {}  # topic -> messages
_buffer_lock = Lock()
BATCH_SIZE = int(os.getenv('KAFKA_BATCH_SIZE', '10'))  # Flush after N messages
BATCH_TIMEOUT_MS = int(os.getenv('KAFKA_BATCH_TIMEOUT_MS', '1000'))  # Or after N ms


def get_kafka_producer() -> Optional[KafkaProducer]:
    """Get or create a singleton Kafka producer with optimized settings."""
    global _producer_instance
    
    if _producer_instance is not None:
        return _producer_instance
    
    with _producer_lock:
        # Double-check after acquiring lock
        if _producer_instance is not None:
            return _producer_instance
        
        try:
            _producer_instance = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: v,
                # === OPTIMIZATION: Batching & compression settings ===
                batch_size=16384,  # 16KB batch size
                linger_ms=BATCH_TIMEOUT_MS,  # Wait up to 1s to batch messages
                compression_type='lz4',  # Compress messages (matches broker config)
                # === OPTIMIZATION: Reliability settings ===
                acks='all',  # Wait for all replicas (or 1 for speed)
                retries=3,
                retry_backoff_ms=100,
                # === OPTIMIZATION: Memory management ===
                buffer_memory=33554432,  # 32MB buffer
                max_block_ms=5000,  # Block max 5s if buffer full
            )
            print(f"✅ Kafka producer connected to {KAFKA_BROKER}")
            
            # Register cleanup on exit
            atexit.register(_cleanup_producer)
            
            return _producer_instance
        except Exception as e:
            print(f"❌ Failed to connect to Kafka: {e}")
            return None


def _cleanup_producer():
    """Cleanup producer on exit."""
    global _producer_instance
    if _producer_instance:
        try:
            _producer_instance.flush(timeout=5)
            _producer_instance.close(timeout=5)
            print("✅ Kafka producer closed gracefully")
        except Exception as e:
            print(f"⚠️ Error closing Kafka producer: {e}")
        _producer_instance = None


def send_to_kafka(producer: KafkaProducer, topic: str, data: Dict[str, Any], 
                  flush: bool = False, silent: bool = False) -> bool:
    """
    Send data to a Kafka topic with optimized batching.
    
    Args:
        producer: KafkaProducer instance (can be None, will get singleton)
        topic: Kafka topic name
        data: Dictionary to send
        flush: Force immediate send (bypass batching)
        silent: Don't print success message (reduces log spam)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use singleton if no producer provided
        if producer is None:
            producer = get_kafka_producer()
            if producer is None:
                return False
        
        # Add timestamp metadata
        message_data = {
            'data': data,
            'sent_at': datetime.now().isoformat()
        }
        
        # Convert to JSON and encode
        message = json.dumps(message_data).encode('utf-8')
        
        # Send to Kafka (producer handles batching internally)
        future = producer.send(topic, value=message)
        
        # Only flush if explicitly requested
        if flush:
            producer.flush(timeout=5)
        
        if not silent:
            symbol = data.get('symbol', 'data')
            print(f"✓ Sent to Kafka topic '{topic}': {symbol}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error sending to Kafka: {e}")
        return False


def send_batch_to_kafka(producer: KafkaProducer, topic: str, 
                        data_list: List[Dict[str, Any]]) -> int:
    """
    Send multiple messages to Kafka efficiently.
    
    Args:
        producer: KafkaProducer instance
        topic: Kafka topic name
        data_list: List of dictionaries to send
    
    Returns:
        int: Number of messages successfully queued
    """
    if not data_list:
        return 0
    
    if producer is None:
        producer = get_kafka_producer()
        if producer is None:
            return 0
    
    success_count = 0
    for data in data_list:
        if send_to_kafka(producer, topic, data, flush=False, silent=True):
            success_count += 1
    
    # Flush after batch
    try:
        producer.flush(timeout=10)
    except Exception as e:
        print(f"⚠️ Flush error: {e}")
    
    print(f"✓ Sent batch of {success_count}/{len(data_list)} messages to '{topic}'")
    return success_count


def flush_producer():
    """Flush any pending messages in the producer buffer."""
    if _producer_instance:
        try:
            _producer_instance.flush(timeout=10)
        except Exception as e:
            print(f"⚠️ Flush error: {e}")