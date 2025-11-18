"""Kafka utilities for Phase 2"""

from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
import logging
import json
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


def create_kafka_consumer(
    bootstrap_servers: str,
    group_id: str,
    topics: list,
    auto_offset_reset: str = 'earliest'
) -> Consumer:
    """
    Create Kafka consumer
    
    Args:
        bootstrap_servers: Kafka bootstrap servers
        group_id: Consumer group ID
        topics: List of topics to subscribe to
        auto_offset_reset: Where to start reading ('earliest' or 'latest')
    
    Returns:
        Configured Kafka Consumer
    """
    
    conf = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': group_id,
        'auto.offset.reset': auto_offset_reset,
        'enable.auto.commit': True,
        'session.timeout.ms': 6000,
    }
    
    consumer = Consumer(conf)
    consumer.subscribe(topics)
    
    logger.info(f"Kafka consumer created: {group_id} -> {topics}")
    
    return consumer


def create_kafka_producer(bootstrap_servers: str) -> Producer:
    """
    Create Kafka producer
    
    Args:
        bootstrap_servers: Kafka bootstrap servers
    
    Returns:
        Configured Kafka Producer
    """
    
    conf = {
        'bootstrap.servers': bootstrap_servers,
        'client.id': 'phase2-producer',
    }
    
    producer = Producer(conf)
    
    logger.info(f"Kafka producer created")
    
    return producer


def produce_message(
    producer: Producer,
    topic: str,
    key: Optional[str],
    value: Dict[str, Any]
) -> bool:
    """
    Produce message to Kafka topic
    
    Args:
        producer: Kafka producer
        topic: Topic name
        key: Message key (optional)
        value: Message value (will be JSON-serialized)
    
    Returns:
        True if successful, False otherwise
    """
    
    try:
        producer.produce(
            topic=topic,
            key=key.encode('utf-8') if key else None,
            value=json.dumps(value).encode('utf-8'),
            callback=lambda err, msg: _delivery_callback(err, msg)
        )
        
        producer.flush()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to produce message to {topic}: {e}")
        return False


def _delivery_callback(err, msg):
    """Callback for message delivery confirmation"""
    
    if err:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")


def consume_messages(
    consumer: Consumer,
    callback: Callable[[Dict[str, Any]], None],
    timeout: float = 1.0
):
    """
    Consume messages from Kafka in a loop
    
    Args:
        consumer: Kafka consumer
        callback: Function to call for each message
        timeout: Poll timeout in seconds
    """
    
    try:
        while True:
            msg = consumer.poll(timeout)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f"Reached end of partition {msg.partition()}")
                else:
                    raise KafkaException(msg.error())
            else:
                # Parse and process message
                try:
                    value = json.loads(msg.value().decode('utf-8'))
                    callback(value)
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
    
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    
    finally:
        consumer.close()
        logger.info("Consumer closed")
