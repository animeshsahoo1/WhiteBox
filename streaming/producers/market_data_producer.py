"""
Hybrid Market Data Producer
- First sends historical OHLCV data for a configurable period
- Then continues with real-time updates every interval

Configuration via environment variables:
- MARKET_HISTORICAL_PERIOD: How much historical data to send first (default: "1d")
- MARKET_HISTORICAL_INTERVAL: Interval for historical data (default: "1m")
- MARKET_DATA_INTERVAL: Seconds between real-time updates (default: 60)
- STOCKS: Comma-separated list of symbols
"""
import os
import time
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# Try importing yfinance for historical data
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not available - historical data disabled")

# Import base producer
try:
    from producers.base_producer import BaseProducer
except ImportError:
    from base_producer import BaseProducer

# Import Kafka utils
try:
    from utils.kafka_utils import get_kafka_producer, send_to_kafka
except ImportError:
    try:
        from streaming.utils.kafka_utils import get_kafka_producer, send_to_kafka
    except ImportError:
        get_kafka_producer = None
        send_to_kafka = None


class MarketDataProducer(BaseProducer):
    """
    Hybrid producer that sends historical data first, then real-time updates.
    
    Flow:
    1. On startup, fetch historical OHLCV data for each symbol
    2. Send all historical candles to Kafka (oldest first)
    3. Track the last timestamp sent per symbol
    4. Switch to real-time mode: fetch current quotes every interval
    5. Only send data newer than last sent timestamp
    """
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,GOOGL,MSFT').split(',')
        fetch_interval = int(os.getenv('MARKET_DATA_INTERVAL', '60'))
        
        super().__init__(
            kafka_topic='market-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        # Historical data config from environment
        self.historical_period = os.getenv('MARKET_HISTORICAL_PERIOD', '1d')
        self.historical_interval = os.getenv('MARKET_HISTORICAL_INTERVAL', '1m')
        
        # Track last sent timestamp per symbol (for dedup)
        self.last_sent_timestamps: Dict[str, datetime] = {}
        
        # Track if historical data has been sent
        self.historical_sent = False
        
        # API Keys for real-time
        self.fmp_key = os.getenv('FMP_API_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        
        print(f"=" * 60)
        print(f"🚀 Hybrid Market Data Producer")
        print(f"=" * 60)
        print(f"📊 Symbols: {', '.join(stocks)}")
        print(f"📅 Historical Period: {self.historical_period}")
        print(f"⏱️  Historical Interval: {self.historical_interval}")
        print(f"🔄 Real-time Interval: {fetch_interval}s")
        print(f"=" * 60)
    
    def setup_sources(self):
        """Setup data sources for real-time mode."""
        # FMP for real-time quotes
        if self.fmp_key:
            self.register_source("FMP", self._fetch_realtime_fmp, priority=0)
        
        # Finnhub as fallback
        if self.finnhub_key:
            try:
                import finnhub
                self.finnhub_client = finnhub.Client(api_key=self.finnhub_key)
                self.register_source("Finnhub", self._fetch_realtime_finnhub, priority=1)
            except ImportError:
                pass
    
    def send_historical_data(self):
        """Fetch and send historical data for all symbols using yfinance."""
        if not YFINANCE_AVAILABLE:
            print("⚠️ Skipping historical data - yfinance not available")
            return
        
        print(f"\n📚 Sending historical data ({self.historical_period}, {self.historical_interval} interval)...")
        
        for symbol in self.stocks:
            try:
                print(f"\n  📈 {symbol}: Fetching historical data...")
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=self.historical_period, interval=self.historical_interval)
                
                if df.empty:
                    print(f"  ⚠️ {symbol}: No historical data available")
                    continue
                
                df = df.reset_index()
                timestamp_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                
                candles_sent = 0
                for _, row in df.iterrows():
                    ts = row[timestamp_col]
                    if hasattr(ts, 'isoformat'):
                        timestamp_str = ts.isoformat()
                    else:
                        timestamp_str = str(ts)
                    
                    # Format as market-data message
                    message = {
                        'symbol': symbol,
                        'timestamp': timestamp_str,
                        'sent_at': datetime.now().isoformat(),
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'current_price': float(row['Close']),
                        'previous_close': float(row['Open']),  # Approximate
                        'change': float(row['Close'] - row['Open']),
                        'change_percent': float((row['Close'] - row['Open']) / row['Open'] * 100) if row['Open'] != 0 else 0,
                        'volume': float(row['Volume']),
                        'data_source': 'yfinance_historical'
                    }
                    
                    # Send to Kafka
                    self._send_message(message)
                    candles_sent += 1
                    
                    # Track last timestamp
                    if hasattr(ts, 'timestamp'):
                        self.last_sent_timestamps[symbol] = ts
                    
                    # Small delay to avoid overwhelming Kafka
                    time.sleep(0.01)
                
                print(f"  ✅ {symbol}: Sent {candles_sent} historical candles")
                
            except Exception as e:
                print(f"  ❌ {symbol}: Error fetching historical data - {e}")
        
        print(f"\n✅ Historical data send complete!")
        self.historical_sent = True
    
    def _send_message(self, message: Dict[str, Any]):
        """Send a message to Kafka using singleton producer."""
        try:
            # === OPTIMIZATION: Use singleton producer from kafka_utils ===
            from utils.kafka_utils import get_kafka_producer, send_to_kafka
            producer = get_kafka_producer()
            if producer:
                send_to_kafka(producer, self.kafka_topic, message, silent=True)
        except Exception as e:
            print(f"  ⚠️ Kafka send error: {e}")
    
    def _fetch_realtime_fmp(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time quote from FMP."""
        try:
            url = "https://financialmodelingprep.com/stable/quote"
            params = {"symbol": symbol, "apikey": self.fmp_key}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data or not isinstance(data, list) or len(data) == 0:
                return None
            
            quote = data[0]
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'current_price': quote.get('price'),
                'high': quote.get('dayHigh'),
                'low': quote.get('dayLow'),
                'open': quote.get('open'),
                'previous_close': quote.get('previousClose'),
                'change': quote.get('change'),
                'change_percent': quote.get('changesPercentage'),
                'volume': quote.get('volume'),
                'data_source': 'FMP'
            }
        except Exception as e:
            print(f"  ⚠️ FMP error for {symbol}: {e}")
            return None
    
    def _fetch_realtime_finnhub(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time quote from Finnhub."""
        try:
            quote = self.finnhub_client.quote(symbol)
            
            if not quote or quote.get('c') == 0:
                return None
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'current_price': quote['c'],
                'high': quote['h'],
                'low': quote['l'],
                'open': quote['o'],
                'previous_close': quote['pc'],
                'change': quote['c'] - quote['pc'],
                'change_percent': ((quote['c'] - quote['pc']) / quote['pc']) * 100,
                'data_source': 'Finnhub'
            }
        except Exception as e:
            print(f"  ⚠️ Finnhub error for {symbol}: {e}")
            return None
    
    def run(self):
        """Main run loop - sends historical first, then real-time."""
        print(f"\n🚀 Starting Hybrid Market Data Producer...")
        
        # Step 1: Send historical data first
        if not self.historical_sent:
            self.send_historical_data()
        
        # Step 2: Setup real-time sources
        self.setup_sources()
        
        # Step 3: Enter real-time mode
        print(f"\n🔄 Entering real-time mode (every {self.fetch_interval}s)...")
        
        while True:
            try:
                for symbol in self.stocks:
                    # Try each source in priority order
                    data = None
                    for source in sorted(self.sources, key=lambda x: x.priority):
                        if not source.can_use():
                            continue
                        try:
                            data = source.fetch_func(symbol)
                            if data:
                                source.record_success()
                                break
                        except Exception as e:
                            source.record_failure(e)
                            continue
                    
                    if data:
                        # Add sent_at timestamp
                        data['sent_at'] = datetime.now().isoformat()
                        self._send_message(data)
                        print(f"  📤 {symbol}: ${data.get('current_price', 'N/A')}")
                
                time.sleep(self.fetch_interval)
                
            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(5)


def main():
    """Entry point."""
    producer = MarketDataProducer()
    producer.run()


if __name__ == "__main__":
    main()
