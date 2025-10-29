"""Base producer class for all data producers"""
import time
from datetime import datetime
from abc import ABC, abstractmethod
from utils.kafka_utils import get_kafka_producer, send_to_kafka

class BaseProducer(ABC):
    """Base class for all Kafka producers"""
    
    def __init__(self, kafka_topic, fetch_interval, stocks=None):
        """
        Initialize base producer
        
        Args:
            kafka_topic: Kafka topic name to send data to
            fetch_interval: How often to fetch data (seconds)
            stocks: List of stock symbols (optional)
        """
        self.kafka_topic = kafka_topic
        self.fetch_interval = fetch_interval
        self.stocks = stocks or []
        self.producer = None
        self.name = self.__class__.__name__
    
    @abstractmethod
    def fetch_data(self, stock_symbol):
        """
        Fetch data for a stock symbol
        Must be implemented by child classes
        
        Args:
            stock_symbol: Stock ticker symbol
            
        Returns:
            dict: Data to send to Kafka, or None if failed
        """
        pass
    
    @abstractmethod
    def setup(self):
        """
        Setup API clients, validate config, etc.
        Must be implemented by child classes
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        pass
    
    def fetch_and_send(self):
        """Fetch data for all stocks and send to Kafka"""
        print(f"[{self.name}] [{datetime.now().strftime('%H:%M:%S')}] Fetching data...")
        
        for stock in self.stocks:
            try:
                data = self.fetch_data(stock)
                if data:
                    send_to_kafka(self.producer, self.kafka_topic, data)
                time.sleep(0.5)  # Small delay between stocks (API rate limiting)
            except Exception as e:
                print(f"[{self.name}] Error processing {stock}: {e}")
    
    def initialize(self):
        """Initialize the producer (called once at startup)"""
        print("=" * 60)
        print(f"Initializing {self.name}")
        print(f"Topic: {self.kafka_topic}")
        print(f"Interval: {self.fetch_interval}s")
        print("=" * 60)
        
        # Setup
        if not self.setup():
            print(f"[{self.name}] ✗ Setup failed")
            return False
        
        # Connect to Kafka
        self.producer = get_kafka_producer()
        if not self.producer:
            print(f"[{self.name}] ✗ Failed to connect to Kafka")
            return False
        
        print(f"[{self.name}] ✓ Ready!")
        return True
    
    def cleanup(self):
        """Cleanup resources"""
        if self.producer:
            self.producer.close()
        print(f"[{self.name}] ✓ Cleaned up")