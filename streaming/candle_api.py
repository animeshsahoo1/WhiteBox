"""
Candle Producer API - Simple configuration management via FastAPI

Features:
- Multiple symbols (all use same settings)
- Producer starts automatically on API startup
- Change period, start_date, interval anytime
- Changes trigger immediate re-fetch of all historical candles

Configuration is persisted to candle_config.json
"""

import os
import sys
import json
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))


# ============================================================================
# Yahoo Finance Constraints
# ============================================================================

# Valid intervals supported by Yahoo Finance
VALID_INTERVALS = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"]

# Valid periods supported by Yahoo Finance
VALID_PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

# Maximum lookback days for each interval (Yahoo Finance constraints)
# Intraday data has strict limits; exceeding returns empty DataFrame
INTERVAL_MAX_DAYS = {
    "1m": 7,       # 7 days max
    "2m": 60,      # 60 days max
    "5m": 60,      # 60 days max
    "15m": 60,     # 60 days max
    "30m": 60,     # 60 days max
    "60m": 730,    # ~2 years
    "90m": 60,     # 60 days max
    "1h": 730,     # ~2 years
    "4h": 730,     # ~2 years (same as 1h)
    "1d": None,    # No limit
    "5d": None,    # No limit
    "1wk": None,   # No limit
    "1mo": None,   # No limit
    "3mo": None,   # No limit
}

# Approximate days for each period (for validation)
PERIOD_APPROX_DAYS = {
    "1d": 1,
    "5d": 5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
    "10y": 3650,
    "ytd": 365,  # Approximate
    "max": 10000,  # Very large
}


def validate_interval(interval: str) -> tuple[bool, str]:
    """Validate interval is supported by Yahoo Finance."""
    if interval not in VALID_INTERVALS:
        return False, f"Invalid interval '{interval}'. Valid intervals: {VALID_INTERVALS}"
    return True, ""


def validate_period(period: str) -> tuple[bool, str]:
    """Validate period is supported by Yahoo Finance."""
    if period not in VALID_PERIODS:
        return False, f"Invalid period '{period}'. Valid periods: {VALID_PERIODS}"
    return True, ""


def validate_interval_period_combo(interval: str, period: str) -> tuple[bool, str]:
    """
    Validate that the interval+period combination is valid.
    Yahoo Finance silently returns empty data for invalid combos.
    """
    max_days = INTERVAL_MAX_DAYS.get(interval)
    if max_days is None:
        return True, ""  # No limit for daily+ intervals
    
    period_days = PERIOD_APPROX_DAYS.get(period, 0)
    if period_days > max_days:
        return False, (
            f"Period '{period}' (~{period_days} days) exceeds maximum for interval '{interval}' "
            f"({max_days} days max). Use a shorter period or longer interval."
        )
    return True, ""


def validate_config(interval: str, period: str, start_date: Optional[str] = None) -> tuple[bool, str]:
    """
    Full validation of interval, period, and their combination.
    Returns (is_valid, error_message).
    """
    # Validate interval
    valid, msg = validate_interval(interval)
    if not valid:
        return False, msg
    
    # If using start_date, we can't easily validate without knowing the date
    # But we can still check the interval is valid
    if start_date:
        return True, ""
    
    # Validate period
    valid, msg = validate_period(period)
    if not valid:
        return False, msg
    
    # Validate combo
    valid, msg = validate_interval_period_combo(interval, period)
    if not valid:
        return False, msg
    
    return True, ""


# ============================================================================
# Configuration Models
# ============================================================================

class CandleConfig(BaseModel):
    """Configuration model for candle producer."""
    symbols: List[str] = Field(default=["AAPL", "GOOGL"], description="List of stock ticker symbols")
    interval: str = Field(default="1h", description="Candle interval (1m, 5m, 15m, 30m, 1h, 1d)")
    period: str = Field(default="3mo", description="Historical period (1d, 5d, 1mo, 3mo, 6mo, 1y)")
    start_date: Optional[str] = Field(default=None, description="Start date (e.g., '2015-08-02') - overrides period if set")
    kafka_topic: str = Field(default="candles", description="Kafka topic for candle data")
    poll_interval: float = Field(default=60.0, description="Seconds between polling for new candles")
    last_timestamps: Dict[str, str] = Field(default_factory=dict, description="Last sent timestamp per symbol (for freshness)")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class ConfigUpdate(BaseModel):
    """Model for updating configuration."""
    symbols: Optional[List[str]] = Field(default=None, description="List of symbols")
    interval: Optional[str] = Field(default=None, description="Candle interval")
    period: Optional[str] = Field(default=None, description="Historical period")
    start_date: Optional[str] = Field(default=None, description="Start date (set to empty string to clear)")
    poll_interval: Optional[float] = Field(default=None, description="Poll interval in seconds")


class ProducerStatus(BaseModel):
    """Status response model."""
    symbols: List[str]
    interval: str
    period: str
    start_date: Optional[str]
    last_timestamps: Dict[str, str]
    candles_sent: int
    uptime_seconds: float


# ============================================================================
# Configuration Manager
# ============================================================================

CONFIG_PATH = Path(__file__).parent / "candle_config.json"


class ConfigManager:
    """Manages candle producer configuration with file persistence."""
    
    def __init__(self):
        self.config = self._load_config()
        self._lock = threading.Lock()
        self._config_version = 0  # Increments on each change
    
    def _load_config(self) -> CandleConfig:
        """Load configuration from file or create default."""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                    config = CandleConfig(**data)
                    
                    # Validate loaded config
                    is_valid, error_msg = validate_config(
                        config.interval, 
                        config.period, 
                        config.start_date
                    )
                    if not is_valid:
                        print(f"⚠️ Invalid config in file: {error_msg}")
                        print(f"   Resetting to defaults...")
                        config = CandleConfig()
                        self._save_config(config)
                    
                    return config
            except Exception as e:
                print(f"⚠️ Error loading config: {e}, using defaults")
        
        config = CandleConfig()
        self._save_config(config)
        return config
    
    def _save_config(self, config: CandleConfig) -> None:
        """Save configuration to file."""
        config.updated_at = datetime.now(timezone.utc).isoformat()
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config.model_dump(), f, indent=4, default=str)
    
    def get_config(self) -> CandleConfig:
        """Get current configuration."""
        with self._lock:
            return self.config.model_copy()
    
    def get_version(self) -> int:
        """Get current config version (for detecting changes)."""
        with self._lock:
            return self._config_version
    
    def update_config(self, updates: Dict[str, Any]) -> CandleConfig:
        """Update configuration and increment version."""
        with self._lock:
            current_data = self.config.model_dump()
            for key, value in updates.items():
                if value is not None and key in current_data:
                    # Handle empty string for start_date (means clear it)
                    if key == "start_date" and value == "":
                        current_data[key] = None
                    else:
                        current_data[key] = value
            self.config = CandleConfig(**current_data)
            self._config_version += 1  # Signal change to producer
            self._save_config(self.config)
            return self.config.model_copy()
    
    def update_last_timestamp(self, symbol: str, timestamp: str) -> None:
        """Update last timestamp for a symbol (persisted to file)."""
        with self._lock:
            self.config.last_timestamps[symbol] = timestamp
            self._save_config(self.config)
    
    def clear_last_timestamps(self) -> None:
        """Clear all last timestamps (triggers full re-fetch)."""
        with self._lock:
            self.config.last_timestamps = {}
            self._config_version += 1
            self._save_config(self.config)


# ============================================================================
# Multi-Symbol Candle Producer
# ============================================================================

class MultiSymbolProducer:
    """Produces candles for multiple symbols with hot-reload config."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.candles_sent = 0
        self.start_time: datetime = datetime.now(timezone.utc)
        self._last_config_version = -1
        self._kafka_producer = None
    
    def _fetch_candles(self, symbol: str, config: CandleConfig, from_timestamp: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch candles for a symbol using yfinance.
        
        Args:
            symbol: Stock ticker
            config: Current config
            from_timestamp: If set, fetch from this date instead of full period
        """
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            
            # Determine start point
            if from_timestamp:
                # Incremental fetch - from last timestamp
                # Parse the stored timestamp and convert to datetime for yfinance
                try:
                    # Handle various timestamp formats (with/without timezone)
                    from dateutil import parser
                    start_dt = parser.parse(from_timestamp)
                    print(f"  📅 {symbol}: Fetching from {start_dt} (incremental)")
                    df = ticker.history(start=start_dt, interval=config.interval)
                except Exception as parse_err:
                    print(f"  ⚠️ {symbol}: Could not parse timestamp '{from_timestamp}': {parse_err}, doing full fetch")
                    df = ticker.history(period=config.period, interval=config.interval)
            elif config.start_date:
                # Full fetch from configured start_date
                print(f"  📅 {symbol}: Fetching from {config.start_date} (full)")
                df = ticker.history(start=config.start_date, interval=config.interval)
            else:
                # Full fetch using period
                print(f"  📅 {symbol}: Fetching last {config.period} (full)")
                df = ticker.history(period=config.period, interval=config.interval)
            
            if df.empty:
                print(f"  ⚠️ {symbol}: No data returned from Yahoo Finance")
                print(f"     This usually means:")
                print(f"     - Invalid symbol (check if '{symbol}' exists)")
                print(f"     - Period too long for interval (interval={config.interval} has lookback limit)")
                print(f"     - Market was closed for the requested period")
                max_days = INTERVAL_MAX_DAYS.get(config.interval)
                if max_days:
                    print(f"     - Max lookback for {config.interval}: {max_days} days")
                return []
            
            # Convert to list of dicts
            df = df.reset_index()
            candles = []
            
            timestamp_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
            
            for _, row in df.iterrows():
                candles.append({
                    'timestamp': str(row[timestamp_col]),
                    'symbol': symbol,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume']),
                    'interval': config.interval
                })
            
            print(f"  ✅ {symbol}: Fetched {len(candles)} candles")
            return candles
            
        except Exception as e:
            print(f"  ❌ {symbol}: Error fetching - {e}")
            return []
    
    def _send_to_kafka(self, candle: Dict[str, Any], topic: str):
        """Send a candle to Kafka."""
        try:
            from utils.kafka_utils import get_kafka_producer, send_to_kafka
            
            if self._kafka_producer is None:
                self._kafka_producer = get_kafka_producer()
            
            if self._kafka_producer:
                send_to_kafka(self._kafka_producer, topic, candle)
                return True
        except Exception as e:
            print(f"  ⚠️ Kafka error: {e}")
        return False
    
    def run_cycle(self, force_full_fetch: bool = False):
        """Run one fetch cycle for all symbols."""
        config = self.config_manager.get_config()
        current_version = self.config_manager.get_version()
        
        # Check if config changed (triggers re-fetch of all historical)
        config_changed = current_version != self._last_config_version
        if config_changed:
            print(f"\n🔄 Config changed! Re-fetching all historical data...")
            self._last_config_version = current_version
            force_full_fetch = True  # Config change = send all candles again
        
        print(f"\n📊 Fetching candles for {len(config.symbols)} symbols...")
        print(f"   Symbols: {', '.join(config.symbols)}")
        print(f"   Interval: {config.interval}")
        print(f"   Period: {config.period}" + (f" (overridden by start_date: {config.start_date})" if config.start_date else ""))
        print(f"   Mode: {'FULL fetch' if force_full_fetch else 'INCREMENTAL fetch'}")
        
        # Fetch and send for all symbols
        for symbol in config.symbols:
            last_ts = config.last_timestamps.get(symbol)
            
            # Decide fetch mode: incremental (from last_ts) or full
            if last_ts and not force_full_fetch:
                # Incremental: fetch only from last timestamp
                candles = self._fetch_candles(symbol, config, from_timestamp=last_ts)
                # Filter out the candle AT last_ts (we already sent it)
                candles = [c for c in candles if c['timestamp'] > last_ts]
            else:
                # Full fetch: get everything based on period/start_date
                candles = self._fetch_candles(symbol, config, from_timestamp=None)
            
            if not candles:
                print(f"  ✓ {symbol}: No new candles")
                continue
            
            # Sort candles by timestamp
            candles = sorted(candles, key=lambda c: c['timestamp'])
            
            # Send candles
            for candle in candles:
                if self._kafka_producer:
                    self._send_to_kafka(candle, config.kafka_topic)
                self.candles_sent += 1
            
            # Update last_timestamp for this symbol (persisted to file)
            latest_ts = candles[-1]['timestamp']
            self.config_manager.update_last_timestamp(symbol, latest_ts)
            print(f"  📤 {symbol}: Sent {len(candles)} candles, last_ts={latest_ts}")
        
        return config.poll_interval
    
    def get_status(self) -> ProducerStatus:
        """Get producer status."""
        config = self.config_manager.get_config()
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        return ProducerStatus(
            symbols=config.symbols,
            interval=config.interval,
            period=config.period,
            start_date=config.start_date,
            last_timestamps=config.last_timestamps,
            candles_sent=self.candles_sent,
            uptime_seconds=uptime
        )


# ============================================================================
# Background Producer Thread
# ============================================================================

def run_producer_loop(producer: MultiSymbolProducer, config_manager: ConfigManager):
    """Background loop that continuously fetches and sends candles."""
    print("\n" + "=" * 60)
    print("🚀 CANDLE PRODUCER STARTED (runs forever)")
    print("=" * 60)
    
    # Connect to Kafka
    try:
        from utils.kafka_utils import get_kafka_producer
        producer._kafka_producer = get_kafka_producer()
        if producer._kafka_producer:
            print("✅ Connected to Kafka")
        else:
            print("⚠️ Kafka not available - will print candles only")
    except Exception as e:
        print(f"⚠️ Kafka connection failed: {e}")
    
    while True:
        try:
            poll_interval = producer.run_cycle()
            
            print(f"\n💤 Sleeping {poll_interval}s until next poll...")
            print(f"   (Change config via API - will trigger re-fetch)")
            
            # Sleep with periodic check for config change
            sleep_start = time.time()
            while True:
                time.sleep(1)
                
                # Check for config change during sleep
                if config_manager.get_version() != producer._last_config_version:
                    print("\n⚡ Config change detected! Interrupting sleep...")
                    break
                
                if time.time() - sleep_start >= poll_interval:
                    break
                    
        except Exception as e:
            print(f"❌ Error in producer loop: {e}")
            time.sleep(5)  # Wait before retrying


# ============================================================================
# FastAPI Application
# ============================================================================

config_manager: Optional[ConfigManager] = None
producer: Optional[MultiSymbolProducer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config_manager, producer
    
    config_manager = ConfigManager()
    producer = MultiSymbolProducer(config_manager)
    
    # Start producer in background thread (runs forever)
    thread = threading.Thread(
        target=run_producer_loop, 
        args=(producer, config_manager),
        daemon=True
    )
    thread.start()
    
    print(f"🚀 Candle API started - producer running in background")
    yield
    print("👋 Candle API shutdown")


app = FastAPI(
    title="Candle Producer API",
    description="Simple multi-symbol candle producer - always running, just update config",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """API info."""
    return {
        "name": "Candle Producer API",
        "version": "2.0.0",
        "description": "Producer runs automatically - just update config to change behavior",
        "endpoints": {
            "GET /config": "View current config",
            "PUT /config": "Update config (triggers immediate re-fetch)",
            "POST /config/validate": "Validate config without applying",
            "GET /constraints": "View Yahoo Finance constraints",
            "GET /status": "View producer status"
        }
    }


class ValidationRequest(BaseModel):
    """Request model for config validation."""
    interval: Optional[str] = None
    period: Optional[str] = None
    start_date: Optional[str] = None


class ValidationResponse(BaseModel):
    """Response model for config validation."""
    valid: bool
    message: str
    interval: str
    period: str
    start_date: Optional[str]
    max_lookback_days: Optional[int] = None


@app.post("/config/validate", response_model=ValidationResponse, tags=["Config"])
async def validate_config_endpoint(request: ValidationRequest):
    """
    Validate a configuration without applying it.
    
    Use this to check if an interval/period combination is valid
    before setting it.
    """
    current = config_manager.get_config()
    
    interval = request.interval or current.interval
    period = request.period or current.period
    start_date = request.start_date if request.start_date is not None else current.start_date
    
    if start_date == "":
        start_date = None
    
    is_valid, error_msg = validate_config(interval, period, start_date)
    
    return ValidationResponse(
        valid=is_valid,
        message=error_msg if not is_valid else "Configuration is valid",
        interval=interval,
        period=period,
        start_date=start_date,
        max_lookback_days=INTERVAL_MAX_DAYS.get(interval)
    )


@app.get("/constraints", tags=["Config"])
async def get_constraints():
    """
    Get Yahoo Finance constraints for intervals and periods.
    
    Useful for understanding what combinations are valid.
    """
    return {
        "valid_intervals": VALID_INTERVALS,
        "valid_periods": VALID_PERIODS,
        "interval_max_days": INTERVAL_MAX_DAYS,
        "period_approx_days": PERIOD_APPROX_DAYS,
        "notes": {
            "intraday_limits": "1m=7days, 2m/5m/15m/30m/90m=60days, 1h/60m/4h=730days (~2yrs)",
            "daily_and_above": "1d, 5d, 1wk, 1mo, 3mo have no lookback limit",
            "start_date": "When using start_date, period is ignored. Be mindful of intraday limits."
        }
    }


@app.get("/config", response_model=CandleConfig, tags=["Config"])
async def get_config():
    """Get current configuration."""
    return config_manager.get_config()


@app.put("/config", response_model=CandleConfig, tags=["Config"])
async def update_config(updates: ConfigUpdate):
    """
    Update configuration.
    
    Changes take effect immediately - producer will re-fetch all 
    historical candles with new settings.
    
    **Validation:**
    - Interval must be one of: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo
    - Period must be one of: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    - Intraday intervals have lookback limits (e.g., 1m = 7 days max, 5m/15m/30m = 60 days max)
    
    Examples:
    - Change period: {"period": "6mo"}
    - Set start date: {"start_date": "2020-01-01"}
    - Clear start date: {"start_date": ""}
    - Change symbols: {"symbols": ["AAPL", "GOOGL", "MSFT"]}
    - Change interval: {"interval": "15m"}
    """
    update_dict = updates.model_dump(exclude_none=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    # Get current config for validation
    current = config_manager.get_config()
    
    # Determine final values after update
    new_interval = update_dict.get("interval", current.interval)
    new_period = update_dict.get("period", current.period)
    new_start_date = update_dict.get("start_date", current.start_date)
    
    # Handle empty string for start_date (means clear it)
    if new_start_date == "":
        new_start_date = None
    
    # Validate the configuration
    is_valid, error_msg = validate_config(new_interval, new_period, new_start_date)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    return config_manager.update_config(update_dict)


@app.get("/status", response_model=ProducerStatus, tags=["Status"])
async def get_status():
    """Get producer status."""
    return producer.get_status()


# ============================================================================
# Main
# ============================================================================

def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    host = os.getenv("CANDLE_API_HOST", "0.0.0.0")
    port = int(os.getenv("CANDLE_API_PORT", "8001"))
    
    print(f"\n🚀 Starting Candle API on http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Producer will start automatically!")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
