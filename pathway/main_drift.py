"""
Main entry point for Drift Detection Pipeline

Runs the Pathway-based drift detection agent that:
1. Consumes market data from Kafka
2. Detects concept drift using multiple detectors (ADWIN, PageHinkley, ZScore, etc.)
3. Stores drift alerts in Redis for API access

Usage:
    python main_drift.py
    
Environment Variables:
    KAFKA_BROKER: Kafka bootstrap servers (default: kafka:29092)
    MARKET_TOPIC: Kafka topic for market data (default: market-data)
    REDIS_HOST: Redis host (default: redis)
    REDIS_PORT: Redis port (default: 6379)
    USE_DUMMY: Use demo CSV data instead of Kafka (default: false)
    
    # Drift detection thresholds
    DRIFT_SPIKE_THRESHOLD: Z-score threshold for spike detection (default: 3.0)
    DRIFT_GRADUAL_THRESHOLD: MA divergence threshold (default: 0.05)
    DRIFT_VARIANCE_THRESHOLD: Variance change threshold (default: 1.0)
    DRIFT_ADWIN_DELTA: ADWIN sensitivity (default: 0.002)
    DRIFT_PH_THRESHOLD: Page-Hinkley threshold (default: 50)
    DRIFT_ALERT_COOLDOWN: Min updates between alerts (default: 10)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

import pathway as pw
from agents.drift_agent import DriftDetectionAgent


# Schema for demo mode CSV replay (matches DriftConsumer output)
class DriftMarketDataSchema(pw.Schema):
    """Schema for market data used in drift detection (demo mode)."""
    symbol: str
    timestamp: str
    current_price: float
    high: float
    low: float
    open: float
    change_percent: float
    sent_at: str


def get_drift_table():
    """
    Get market data table for drift detection from Kafka.
    
    Returns:
        pw.Table: Market data stream table for drift detection.
    """
    print("📡 LIVE MODE: Consuming from Kafka topic 'market-data'")
    from consumers.drift_consumer import DriftConsumer
    consumer = DriftConsumer()
    return consumer.consume()


def main():
    print("=" * 70)
    print("Pathway Drift Detection Pipeline")
    print("=" * 70)
    print("📡 MODE: LIVE (using Kafka streaming)")
    
    # Configuration from environment
    kafka_broker = os.getenv("KAFKA_BROKER", "kafka:29092")
    market_topic = os.getenv("MARKET_TOPIC", "market-data")
    
    print(f"📡 Kafka Broker: {kafka_broker}")
    print(f"📨 Market Topic: {market_topic}")
    print(f"🔧 Redis: {os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}")
    print()
    
    # Print drift detection configuration
    print("🎯 Drift Detection Configuration:")
    print(f"   - Spike Threshold (Z-score): {os.getenv('DRIFT_SPIKE_THRESHOLD', '3.0')}")
    print(f"   - Gradual Drift Threshold: {os.getenv('DRIFT_GRADUAL_THRESHOLD', '0.05')}")
    print(f"   - Variance Change Threshold: {os.getenv('DRIFT_VARIANCE_THRESHOLD', '1.0')}")
    print(f"   - ADWIN Delta: {os.getenv('DRIFT_ADWIN_DELTA', '0.002')}")
    print(f"   - Page-Hinkley Threshold: {os.getenv('DRIFT_PH_THRESHOLD', '50')}")
    print(f"   - Alert Cooldown: {os.getenv('DRIFT_ALERT_COOLDOWN', '10')} updates")
    print()
    
    # Initialize and run agent
    agent = DriftDetectionAgent(
        kafka_bootstrap=kafka_broker,
        market_topic=market_topic,
    )
    
    print("✅ Drift Detection Agent initialized")
    print("🚀 Starting stream processing...")
    print()
    
    agent.run()


if __name__ == "__main__":
    load_dotenv()
    main()