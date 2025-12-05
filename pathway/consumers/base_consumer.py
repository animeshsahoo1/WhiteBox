import pathway as pw
from abc import ABC, abstractmethod

class BaseConsumer(ABC):
    """Base class for all Pathway Kafka consumers"""
    
    def __init__(self, topic_name, consumer_group_id=None):
        """
        Initialize base consumer with optimized Kafka settings.
        
        Args:
            topic_name: Kafka topic to consume from
            consumer_group_id: Consumer group ID (auto-generated if None)
        """
        import os
        
        self.topic_name = topic_name
        self.consumer_group_id = consumer_group_id or f"pathway-{topic_name}-consumer"
        
        # Optimized rdkafka settings for better throughput and lower latency
        self.rdkafka_settings = {
            "bootstrap.servers": os.getenv("KAFKA_BROKER", "kafka:29092"),
            "group.id": self.consumer_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": "true",
            "auto.commit.interval.ms": "30000",  # Commit every 30s (was 60s)
            # Performance optimizations
            "fetch.min.bytes": "1024",  # Minimum 1KB per fetch
            "fetch.max.wait.ms": "100",  # Max wait 100ms for fetch
            "fetch.max.bytes": "52428800",  # 50MB max per fetch
            "max.partition.fetch.bytes": "1048576",  # 1MB per partition
            "queued.min.messages": "100000",  # Buffer 100K messages
            "queued.max.messages.kbytes": "65536",  # 64MB message buffer
            # Network optimizations
            "socket.receive.buffer.bytes": "262144",  # 256KB receive buffer
            "reconnect.backoff.ms": "50",  # Faster reconnect
            "reconnect.backoff.max.ms": "1000",
        }
        self.table = None
    
    @abstractmethod
    def get_output_schema(self):
        """
        Define the output schema after processing
        Must be implemented by child classes
        
        Returns:
            dict: Dictionary mapping field names to extraction logic
        """
        pass
    
    def get_kafka_schema(self):
        """
        Define the Kafka message schema (wrapper structure)
        Override if your Kafka messages have different structure
        
        Returns:
            pw.Schema: Schema class for Kafka messages
        """
        class KafkaMessageSchema(pw.Schema):
            data: pw.Json
            sent_at: str
        
        return KafkaMessageSchema
    
    def consume(self):
        """
        Consume messages from Kafka and create Pathway table
        
        Returns:
            pw.Table: Processed Pathway table
        """
        
        # Read raw messages from Kafka
        raw_table = pw.io.kafka.read(
            self.rdkafka_settings,
            topic=self.topic_name,
            format="json",
            schema=self.get_kafka_schema()
        )
        
        # Extract and process data using child class schema
        output_schema = self.get_output_schema()
        self.table = raw_table.select(**output_schema)
        
        print(f"✅ {self.__class__.__name__} initialized successfully")
        return self.table
    
    def get_table(self):
        """Get the processed table"""
        if self.table is None:
            raise RuntimeError("Consumer not initialized. Call consume() first.")
        return self.table