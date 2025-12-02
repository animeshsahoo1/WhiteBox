"""
Candle Data Producer - OHLCV market data for backtesting

Fetches historical candles from yfinance and streams to Kafka.
Supports CSV fallback when yfinance is unavailable.

Sources (priority order):
1. yfinance (live market data)
2. CSV fallback (historical data file)

Usage:
    python candle_producer.py --symbol AAPL --interval 1h --period 1mo
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd

# Add parent for utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.kafka_utils import get_kafka_producer, send_to_kafka
from producers.base_producer import BaseProducer

# Optional yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not installed - will use CSV fallback")


class CandleProducer(BaseProducer):
    """
    Producer for OHLCV candle data.
    
    Supports multiple data sources with automatic fallback:
    - yfinance: Real-time and historical market data
    - CSV: Local fallback for testing/offline
    """
    
    def __init__(
        self,
        symbol: str = "AAPL",
        interval: str = "1h",
        period: str = "1mo",
        csv_path: Optional[str] = None,
        kafka_topic: str = "candles",
        fetch_interval: int = 60
    ):
        """
        Initialize the candle producer.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
            interval: Candle interval ('1m', '5m', '15m', '30m', '1h', '1d')
            period: Historical period ('1d', '5d', '1mo', '3mo', '6mo', '1y')
            csv_path: Path to CSV fallback file
            kafka_topic: Kafka topic for candle data
            fetch_interval: Seconds between fetches
        """
        # Call parent with required args
        super().__init__(
            kafka_topic=kafka_topic,
            fetch_interval=fetch_interval,
            stocks=[symbol]  # Single stock for this producer
        )
        
        self.symbol = symbol
        self.interval = interval
        self.period = period
        self.csv_path = Path(csv_path) if csv_path else Path(__file__).parent.parent / "data" / "candles.csv"
        self.last_timestamp: Optional[str] = None
        self.last_successful_source: Optional[str] = None
    
    def setup_sources(self):
        """Register available data sources with priority."""
        print(f"  Setting up sources for {self.symbol}...")
        
        if YFINANCE_AVAILABLE:
            self.register_source(
                name="yfinance",
                fetch_func=self._fetch_from_yfinance,
                priority=0  # Highest priority
            )
        
        if self.csv_path.exists():
            self.register_source(
                name="csv_fallback",
                fetch_func=self._fetch_from_csv,
                priority=1  # Lower priority
            )
            print(f"  📁 CSV fallback: {self.csv_path}")
        else:
            print(f"  ⚠️ CSV fallback not found: {self.csv_path}")
    
    def _fetch_from_yfinance(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch candles from yfinance."""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=self.period, interval=self.interval)
        
        if df.empty:
            raise ValueError(f"No data returned for {symbol}")
        
        self.last_successful_source = "yfinance"
        return self._dataframe_to_candles(df)
    
    def _fetch_from_csv(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch candles from CSV fallback."""
        df = pd.read_csv(self.csv_path)
        self.last_successful_source = "csv_fallback"
        return self._dataframe_to_candles(df)
    
    def _dataframe_to_candles(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert DataFrame to list of candle dicts."""
        # Standardize column names
        df = df.reset_index()
        
        column_mapping = {
            'Datetime': 'timestamp', 'Date': 'timestamp', 'index': 'timestamp',
            'Open': 'open', 'High': 'high', 'Low': 'low',
            'Close': 'close', 'Volume': 'volume'
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # Ensure required columns exist
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        df = df[required]
        df['timestamp'] = df['timestamp'].astype(str)
        
        return df.to_dict('records')
    
    def format_message(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single candle for Kafka."""
        return {
            'timestamp': str(candle['timestamp']),
            'open': float(candle['open']),
            'high': float(candle['high']),
            'low': float(candle['low']),
            'close': float(candle['close']),
            'volume': float(candle['volume']),
            'symbol': self.symbol,
            'interval': self.interval,
            'source': self.last_successful_source or 'unknown'
        }
    
    def backfill_historical(self, batch_size: int = 50):
        """Backfill all historical candles to Kafka."""
        print(f"\n📥 Backfilling historical candles for {self.symbol}...")
        
        # Fetch using fallback mechanism
        candles = self.fetch_data_with_fallback(self.symbol)
        if not candles:
            print("⚠️ No candles to backfill")
            return 0
        
        total = len(candles)
        print(f"   Sending {total} candles to '{self.kafka_topic}'...")
        
        for i, candle in enumerate(candles):
            message = self.format_message(candle)
            send_to_kafka(self.producer, self.kafka_topic, message)
            
            # Update last timestamp
            self.last_timestamp = str(candle['timestamp'])
            
            if (i + 1) % batch_size == 0:
                print(f"   Sent {i + 1}/{total} candles...")
        
        print(f"✅ Backfill complete: {total} candles sent")
        return total
    
    def stream_live(self, poll_interval: float = 60.0):
        """Continuously poll for new candles."""
        print(f"\n📡 Starting live stream for {self.symbol}...")
        print(f"   Poll interval: {poll_interval}s")
        print(f"   Last timestamp: {self.last_timestamp}")
        
        while True:
            try:
                candles = self.fetch_data_with_fallback(self.symbol)
                
                if candles:
                    # Filter to only new candles
                    if self.last_timestamp:
                        new_candles = [c for c in candles if str(c['timestamp']) > self.last_timestamp]
                    else:
                        new_candles = candles
                    
                    for candle in new_candles:
                        message = self.format_message(candle)
                        send_to_kafka(self.producer, self.kafka_topic, message)
                        self.last_timestamp = str(candle['timestamp'])
                        print(f"📤 New candle: {candle['timestamp']} | close={candle['close']:.2f}")
                
            except Exception as e:
                print(f"⚠️ Polling error: {e}")
            
            time.sleep(poll_interval)
    
    def run(self, backfill: bool = True, poll_interval: float = 60.0):
        """Run the producer: setup, backfill, then stream live."""
        print("=" * 60)
        print(f"🚀 CANDLE PRODUCER - {self.symbol}")
        print("=" * 60)
        print(f"  Symbol: {self.symbol}")
        print(f"  Interval: {self.interval}")
        print(f"  Period: {self.period}")
        print(f"  Topic: {self.kafka_topic}")
        print(f"  CSV Path: {self.csv_path}")
        print("=" * 60)
        
        # Setup (registers sources)
        if not self.setup():
            print("❌ Setup failed - cannot continue")
            return
        
        # Connect to Kafka
        self.producer = get_kafka_producer()
        if not self.producer:
            print("❌ Cannot connect to Kafka")
            return
        
        print(f"✅ Connected to Kafka")
        print(f"  Sources available: {[s.name for s in self.sources]}")
        
        if backfill:
            self.backfill_historical()
        
        self.stream_live(poll_interval)


def main():
    """Entry point for candle producer."""
    from dotenv import load_dotenv
    load_dotenv()
    
    import argparse
    
    # Get symbol from STOCKS env var (first stock) or CANDLE_SYMBOL
    default_symbol = os.getenv("CANDLE_SYMBOL") or os.getenv("STOCKS", "AAPL").split(",")[0].strip()
    
    parser = argparse.ArgumentParser(description="Candle Data Producer")
    parser.add_argument("--symbol", default=default_symbol, help="Stock ticker")
    parser.add_argument("--interval", default=os.getenv("CANDLE_INTERVAL", "1h"), 
                       choices=['1m', '5m', '15m', '30m', '1h', '1d'])
    parser.add_argument("--period", default=os.getenv("CANDLE_PERIOD", "1mo"),
                       choices=['1d', '5d', '1mo', '3mo', '6mo', '1y'])
    parser.add_argument("--topic", default=os.getenv("CANDLE_KAFKA_TOPIC", "candles"))
    parser.add_argument("--poll-interval", type=float, 
                       default=float(os.getenv("CANDLE_POLL_INTERVAL", "60")))
    parser.add_argument("--csv-path", default=os.getenv("CANDLE_CSV_PATH"))
    parser.add_argument("--no-backfill", action="store_true", 
                       default=os.getenv("CANDLE_NO_BACKFILL", "false").lower() == "true",
                       help="Skip historical backfill")
    
    args = parser.parse_args()
    
    print(f"\n🔧 Configuration (from env + args):")
    print(f"   CANDLE_SYMBOL: {args.symbol}")
    print(f"   CANDLE_INTERVAL: {args.interval}")
    print(f"   CANDLE_PERIOD: {args.period}")
    print(f"   CANDLE_KAFKA_TOPIC: {args.topic}")
    print(f"   CANDLE_POLL_INTERVAL: {args.poll_interval}s")
    print(f"   CANDLE_CSV_PATH: {args.csv_path or 'default'}")
    print(f"   Backfill: {not args.no_backfill}")
    
    producer = CandleProducer(
        symbol=args.symbol,
        interval=args.interval,
        period=args.period,
        csv_path=args.csv_path,
        kafka_topic=args.topic
    )
    
    producer.run(backfill=not args.no_backfill, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
