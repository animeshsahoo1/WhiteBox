"""
Drift Detection Consumer - Pathway-based Kafka consumer

Consumes market data from Kafka, runs drift detection,
and stores alerts in Redis for the API to read.

This follows the same pattern as other consumers (market_data_consumer, backtesting_consumer).
"""
import pathway as pw
import json
import logging
from datetime import datetime
from typing import Dict, Optional

from consumers.base_consumer import BaseConsumer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DriftConsumer(BaseConsumer):
    """
    Consumer for market data that performs drift detection.
    
    Reads from 'market-data' topic, detects concept drift,
    and outputs drift alerts.
    """
    
    def __init__(self):
        super().__init__(topic_name="market-data")
    
    def get_output_schema(self):
        """Define how to extract market data fields for drift detection"""
        return {
            "symbol": pw.this.data["symbol"].as_str(),
            "timestamp": pw.this.data["timestamp"].as_str(),
            "current_price": pw.this.data["current_price"].as_float(),
            "high": pw.this.data["high"].as_float(),
            "low": pw.this.data["low"].as_float(),
            "open": pw.this.data["open"].as_float(),
            "change_percent": pw.this.data["change_percent"].as_float(),
            "sent_at": pw.this.sent_at
        }