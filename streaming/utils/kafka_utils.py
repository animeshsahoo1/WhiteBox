"""Utility functions for Kafka operations"""
import os
import json
from datetime import datetime
from kafka import KafkaProducer
from dotenv import load_dotenv

load_dotenv()

KAFKA_BROKER = os.getenv('KAFKA_BROKER')

def get_kafka_producer():
    """Create and return a Kafka producer"""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: v
        )
        return producer
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        return None

def send_to_kafka(producer, topic, data):
    """
    Send data to a Kafka topic
    
    Args:
        producer: KafkaProducer instance
        topic: Kafka topic name (string)
        data: Dictionary to send
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Add timestamp metadata
        message_data = {
            'data': data,
            'sent_at': datetime.now().isoformat()
        }
        
        # Convert to JSON and encode
        message = json.dumps(message_data).encode('utf-8')
        
        # Send to Kafka
        producer.send(topic, value=message)
        
        print(f"✓ Sent to Kafka topic '{topic}': {data.get('symbol', 'data')}")
        return True
        
    except Exception as e:
        print(f"✗ Error sending to Kafka: {e}")
        return False