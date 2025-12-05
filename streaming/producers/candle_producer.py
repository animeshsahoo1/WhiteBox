"""
Candle Data Producer - Multi-Symbol, Multi-Interval OHLCV market data

Fetches historical candles from yfinance for all symbol × interval combinations
and streams to Kafka. Supports CSV fallback when yfinance is unavailable.

Sources (priority order):
1. yfinance (live market data)
2. CSV fallback (historical data file)

Configuration via Environment Variables:
    STOCKS: Comma-separated list of symbols (e.g., "AAPL,GOOGL,TSLA")
    INTERVALS: Comma-separated list of intervals (e.g., "1h,1d")
    CANDLE_KAFKA_TOPIC: Kafka topic (default: "candles")
    CANDLE_POLL_INTERVAL: Seconds between polls (default: 60)

Usage:
    STOCKS=AAPL,GOOGL INTERVALS=1h,1d python candle_producer.py
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd

# Add parent for utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.kafka_utils import get_kafka_producer, send_to_kafka

# Optional yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not installed - will use CSV fallback")


# ============================================================================
# YFINANCE CONSTRAINTS
# ============================================================================

# Maximum period allowed for each interval (yfinance limits)
INTERVAL_MAX_PERIOD = {
    "1m": "7d",      # 7 days max
    "2m": "60d",     # 60 days max
    "5m": "60d",     # 60 days max
    "15m": "60d",    # 60 days max
    "30m": "60d",    # 60 days max
    "60m": "2y",     # ~2 years (730 days)
    "90m": "60d",    # 60 days max
    "1h": "2y",      # ~2 years
    "4h": "2y",      # ~2 years (same as 1h)
    "1d": "max",     # No limit
    "5d": "max",     # No limit
    "1wk": "max",    # No limit
    "1mo": "max",    # No limit
}

# Valid intervals
VALID_INTERVALS = list(INTERVAL_MAX_PERIOD.keys())

# State file path - in mounted data directory for persistence
STATE_FILE_PATH = Path(__file__).parent.parent / "data" / "candle_state.json"


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> Dict[str, str]:
    """Load last timestamps from state file. Key: 'symbol:interval' -> timestamp"""
    if STATE_FILE_PATH.exists():
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                data = json.load(f)
                return data.get('last_timestamps', {})
        except Exception as e:
            print(f"⚠️ Error loading state file: {e}")
    return {}


def save_state(last_timestamps: Dict[str, str]) -> None:
    """Save last timestamps to state file."""
    try:
        data = {
            'last_timestamps': last_timestamps,
            'updated_at': datetime.now().isoformat()
        }
        with open(STATE_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving state file: {e}")


def get_state_key(symbol: str, interval: str) -> str:
    """Generate state key for symbol:interval combo."""
    return f"{symbol}:{interval}"


# ============================================================================
# CANDLE PRODUCER
# ============================================================================

class MultiCandleProducer:
    """
    Producer for OHLCV candle data across multiple symbols and intervals.
    
    Produces candles for all symbol × interval combinations using max allowed
    period for each interval (respecting yfinance limits).
    """
    
    def __init__(
        self,
        symbols: List[str],
        intervals: List[str],
        kafka_topic: str = "candles",
        poll_interval: float = 60.0,
        csv_fallback_dir: Optional[str] = None
    ):
        """
        Initialize the multi-candle producer.
        
        Args:
            symbols: List of stock ticker symbols (e.g., ['AAPL', 'GOOGL'])
            intervals: List of candle intervals (e.g., ['1h', '1d'])
            kafka_topic: Kafka topic for candle data
            poll_interval: Seconds between polling for new candles
            csv_fallback_dir: Directory for CSV fallback files
        """
        self.symbols = [s.strip().upper() for s in symbols]
        self.intervals = [i.strip().lower() for i in intervals]
        self.kafka_topic = kafka_topic
        self.poll_interval = poll_interval
        self.csv_fallback_dir = Path(csv_fallback_dir) if csv_fallback_dir else Path(__file__).parent.parent / "data"
        
        # State tracking: {symbol:interval -> last_timestamp}
        self.last_timestamps: Dict[str, str] = load_state()
        
        # Kafka producer (initialized on run)
        self.producer = None
        
        # Statistics
        self.total_candles_sent = 0
        self.candles_per_combo: Dict[str, int] = {}
        
        # Validate intervals
        for interval in self.intervals:
            if interval not in VALID_INTERVALS:
                print(f"⚠️ Invalid interval '{interval}', valid: {VALID_INTERVALS}")
    
    def _fetch_candles_yfinance(self, symbol: str, interval: str) -> List[Dict[str, Any]]:
        """Fetch candles from yfinance with max allowed period."""
        if not YFINANCE_AVAILABLE:
            raise RuntimeError("yfinance not available")
        
        period = INTERVAL_MAX_PERIOD.get(interval, "1mo")
        ticker = yf.Ticker(symbol)
        
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            raise ValueError(f"No data returned for {symbol} @ {interval}")
        
        return self._dataframe_to_candles(df, symbol, interval)
    
    def _fetch_candles_csv(self, symbol: str, interval: str) -> List[Dict[str, Any]]:
        """Fetch candles from CSV fallback."""
        csv_path = self.csv_fallback_dir / f"{symbol}_{interval}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        
        df = pd.read_csv(csv_path)
        return self._dataframe_to_candles(df, symbol, interval)
    
    def _dataframe_to_candles(self, df: pd.DataFrame, symbol: str, interval: str) -> List[Dict[str, Any]]:
        """Convert DataFrame to list of candle dicts."""
        df = df.reset_index()
        
        # Standardize column names
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
        
        df = df[required].copy()
        df['timestamp'] = df['timestamp'].astype(str)
        df['symbol'] = symbol
        df['interval'] = interval
        
        return df.to_dict('records')
    
    def fetch_candles(self, symbol: str, interval: str) -> List[Dict[str, Any]]:
        """Fetch candles with fallback mechanism."""
        # Try yfinance first
        if YFINANCE_AVAILABLE:
            try:
                return self._fetch_candles_yfinance(symbol, interval)
            except Exception as e:
                print(f"  ⚠️ yfinance failed for {symbol}@{interval}: {e}")
        
        # Fallback to CSV
        try:
            return self._fetch_candles_csv(symbol, interval)
        except Exception as e:
            print(f"  ⚠️ CSV fallback failed for {symbol}@{interval}: {e}")
        
        return []
    
    def format_message(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single candle for Kafka."""
        return {
            'timestamp': str(candle['timestamp']),
            'open': float(candle['open']),
            'high': float(candle['high']),
            'low': float(candle['low']),
            'close': float(candle['close']),
            'volume': float(candle['volume']),
            'symbol': candle['symbol'],
            'interval': candle['interval'],
            'source': 'yfinance' if YFINANCE_AVAILABLE else 'csv'
        }
    
    def backfill_all(self, batch_size: int = 100) -> int:
        """Backfill historical candles for all symbol × interval combinations."""
        print("\n" + "=" * 70)
        print("📥 BACKFILLING HISTORICAL CANDLES")
        print("=" * 70)
        
        total_sent = 0
        
        for symbol in self.symbols:
            for interval in self.intervals:
                state_key = get_state_key(symbol, interval)
                last_ts = self.last_timestamps.get(state_key)
                
                print(f"\n📊 {symbol} @ {interval} (period: {INTERVAL_MAX_PERIOD.get(interval, '?')})")
                if last_ts:
                    print(f"   Last timestamp: {last_ts}")
                
                try:
                    candles = self.fetch_candles(symbol, interval)
                    if not candles:
                        print(f"   ⚠️ No candles fetched")
                        continue
                    
                    # Sort by timestamp
                    candles = sorted(candles, key=lambda c: str(c['timestamp']))
                    
                    # Filter to new candles only
                    if last_ts:
                        candles = [c for c in candles if str(c['timestamp']) > last_ts]
                    
                    if not candles:
                        print(f"   ✅ Up to date")
                        continue
                    
                    print(f"   Sending {len(candles)} candles...")
                    
                    for i, candle in enumerate(candles):
                        message = self.format_message(candle)
                        send_to_kafka(self.producer, self.kafka_topic, message)
                        
                        # Update state
                        self.last_timestamps[state_key] = str(candle['timestamp'])
                        total_sent += 1
                        
                        if (i + 1) % batch_size == 0:
                            print(f"   Sent {i + 1}/{len(candles)}...")
                            save_state(self.last_timestamps)
                    
                    # Save state after each symbol×interval
                    save_state(self.last_timestamps)
                    self.candles_per_combo[state_key] = len(candles)
                    print(f"   ✅ Sent {len(candles)} candles")
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
        
        self.total_candles_sent += total_sent
        print(f"\n📊 Backfill complete: {total_sent} total candles sent")
        return total_sent
    
    def poll_for_updates(self) -> int:
        """Poll for new candles across all combinations."""
        new_candles = 0
        
        for symbol in self.symbols:
            for interval in self.intervals:
                state_key = get_state_key(symbol, interval)
                last_ts = self.last_timestamps.get(state_key)
                
                try:
                    candles = self.fetch_candles(symbol, interval)
                    if not candles:
                        continue
                    
                    # Sort and filter
                    candles = sorted(candles, key=lambda c: str(c['timestamp']))
                    if last_ts:
                        candles = [c for c in candles if str(c['timestamp']) > last_ts]
                    
                    for candle in candles:
                        message = self.format_message(candle)
                        send_to_kafka(self.producer, self.kafka_topic, message)
                        self.last_timestamps[state_key] = str(candle['timestamp'])
                        new_candles += 1
                        print(f"📤 {symbol}@{interval}: {candle['timestamp']} | close={candle['close']:.2f}")
                    
                    if candles:
                        save_state(self.last_timestamps)
                        
                except Exception as e:
                    print(f"⚠️ Poll error {symbol}@{interval}: {e}")
        
        self.total_candles_sent += new_candles
        return new_candles
    
    def stream_live(self):
        """Continuously poll for new candles."""
        print(f"\n📡 Starting live stream (poll every {self.poll_interval}s)...")
        
        while True:
            try:
                new_count = self.poll_for_updates()
                if new_count == 0:
                    print(f"⏳ No new candles @ {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"⚠️ Stream error: {e}")
            
            time.sleep(self.poll_interval)
    
    def run(self, backfill: bool = True):
        """Run the producer: connect, backfill, then stream."""
        print("=" * 70)
        print("🚀 MULTI-CANDLE PRODUCER")
        print("=" * 70)
        print(f"  Symbols: {self.symbols}")
        print(f"  Intervals: {self.intervals}")
        print(f"  Combinations: {len(self.symbols) * len(self.intervals)}")
        print(f"  Topic: {self.kafka_topic}")
        print(f"  Poll Interval: {self.poll_interval}s")
        print(f"  yfinance: {'Available' if YFINANCE_AVAILABLE else 'Not available'}")
        print("=" * 70)
        
        # Print interval limits
        print("\n📋 Interval → Max Period:")
        for interval in self.intervals:
            print(f"   {interval}: {INTERVAL_MAX_PERIOD.get(interval, 'unknown')}")
        
        # Connect to Kafka
        self.producer = get_kafka_producer()
        if not self.producer:
            print("❌ Cannot connect to Kafka")
            return
        print(f"\n✅ Connected to Kafka")
        
        # Backfill historical data
        if backfill:
            self.backfill_all()
        
        # Start live streaming
        self.stream_live()


def main():
    """Entry point for multi-candle producer."""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Parse environment variables
    stocks_str = os.getenv("STOCKS", "AAPL,GOOGL")
    intervals_str = os.getenv("INTERVALS", "1h,1d")
    kafka_topic = os.getenv("CANDLE_KAFKA_TOPIC", "candles")
    poll_interval = float(os.getenv("CANDLE_POLL_INTERVAL", "60"))
    no_backfill = os.getenv("CANDLE_NO_BACKFILL", "false").lower() == "true"
    
    # Parse lists
    symbols = [s.strip() for s in stocks_str.split(",") if s.strip()]
    intervals = [i.strip() for i in intervals_str.split(",") if i.strip()]
    
    print("\n🔧 Configuration (from environment):")
    print(f"   STOCKS: {symbols}")
    print(f"   INTERVALS: {intervals}")
    print(f"   CANDLE_KAFKA_TOPIC: {kafka_topic}")
    print(f"   CANDLE_POLL_INTERVAL: {poll_interval}s")
    print(f"   Backfill: {not no_backfill}")
    
    if not symbols:
        print("❌ No symbols specified. Set STOCKS env var.")
        return
    
    if not intervals:
        print("❌ No intervals specified. Set INTERVALS env var.")
        return
    
    producer = MultiCandleProducer(
        symbols=symbols,
        intervals=intervals,
        kafka_topic=kafka_topic,
        poll_interval=poll_interval
    )
    
    producer.run(backfill=not no_backfill)


if __name__ == "__main__":
    main()
