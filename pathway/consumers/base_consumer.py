import pathway as pw
from abc import ABC, abstractmethod

class BaseConsumer(ABC):
    """Base class for all Pathway Kafka consumers"""
    
    def __init__(self, topic_name, consumer_group_id=None):
        """
        Initialize base consumer
        
        Args:
            topic_name: Kafka topic to consume from
            consumer_group_id: Consumer group ID (auto-generated if None)
        """
        self.topic_name = topic_name
        self.consumer_group_id = consumer_group_id or f"pathway-{topic_name}-consumer"
        self.rdkafka_settings = {
            "bootstrap.servers": "kafka:29092",
            "group.id": self.consumer_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": "true",
            "auto.commit.interval.ms": "60000",
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