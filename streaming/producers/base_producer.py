"""Enhanced base producer class with multi-source fallback support"""
import time
import signal
import sys
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils.kafka_utils import get_kafka_producer, send_to_kafka


class SourceStatus(Enum):
    """Status of a data source"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class DataSource:
    """Represents a single data source with circuit breaker pattern"""
    
    def __init__(self, name: str, fetch_func: Callable, priority: int = 0):
        """
        Initialize a data source
        
        Args:
            name: Source identifier (e.g., "NewsAPI", "AlphaVantage")
            fetch_func: Function to fetch data from this source
            priority: Lower number = higher priority (0 is highest)
        """
        self.name = name
        self.fetch_func = fetch_func
        self.priority = priority
        self.status = SourceStatus.HEALTHY
        self.failure_count = 0
        self.last_failure = None
        self.last_success = None
        self.cooldown_until = None
        
        # Circuit breaker settings
        self.max_failures = 3  # After 3 failures, mark as FAILED
        self.cooldown_period = 300  # 5 minutes cooldown for rate limits
        self.reset_after = 900  # 15 minutes before retrying failed sources
    
    def can_use(self) -> bool:
        """Check if source is available for use"""
        # Check if source is in cooldown
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        
        # Don't use completely failed sources (they'll auto-reset after timeout)
        if self.status == SourceStatus.FAILED:
            # Check if enough time has passed to retry
            if self.last_failure:
                time_since_failure = (datetime.now() - self.last_failure).total_seconds()
                if time_since_failure < self.reset_after:
                    return False
                else:
                    # Auto-reset after cooldown period
                    self._reset()
        
        return True
    
    def record_success(self):
        """Record successful fetch"""
        self.last_success = datetime.now()
        self.failure_count = 0
        self.status = SourceStatus.HEALTHY
        self.cooldown_until = None
    
    def record_failure(self, error: Exception):
        """Record failed fetch with intelligent error handling"""
        self.last_failure = datetime.now()
        self.failure_count += 1
        
        error_str = str(error).lower()
        
        # Check if rate limited
        if any(keyword in error_str for keyword in ['rate limit', '429', 'too many requests']):
            self.status = SourceStatus.RATE_LIMITED
            self.cooldown_until = datetime.now() + timedelta(seconds=self.cooldown_period)
            print(f"  ⏳ {self.name} rate limited - cooldown until {self.cooldown_until.strftime('%H:%M:%S')}")
        
        # Check if API key invalid or unauthorized
        elif any(keyword in error_str for keyword in ['unauthorized', '401', '403', 'invalid api key', 'api key']):
            self.status = SourceStatus.FAILED
            self.cooldown_until = datetime.now() + timedelta(seconds=self.reset_after)
            print(f"  🔒 {self.name} authentication failed - disabled for {self.reset_after//60} minutes")
        
        # Circuit breaker: too many failures
        elif self.failure_count >= self.max_failures:
            self.status = SourceStatus.FAILED
            self.cooldown_until = datetime.now() + timedelta(seconds=self.reset_after)
            print(f"  ⚡ {self.name} circuit breaker triggered - disabled for {self.reset_after//60} minutes")
        
        # Degraded but still usable
        else:
            self.status = SourceStatus.DEGRADED
            print(f"  ⚠️  {self.name} degraded ({self.failure_count}/{self.max_failures} failures)")
    
    def _reset(self):
        """Reset source to healthy state"""
        self.failure_count = 0
        self.status = SourceStatus.HEALTHY
        self.cooldown_until = None
        print(f"  ♻️  {self.name} auto-reset to healthy state")
    
    def get_status_icon(self) -> str:
        """Get emoji icon for current status"""
        return {
            SourceStatus.HEALTHY: "✅",
            SourceStatus.DEGRADED: "⚠️",
            SourceStatus.FAILED: "❌",
            SourceStatus.RATE_LIMITED: "⏳"
        }.get(self.status, "❓")


class BaseProducer(ABC):
    """Base class for all Kafka producers with multi-source fallback support"""
    
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
        self.scheduler = None
        
        # Multi-source fallback support
        self.sources: List[DataSource] = []
        self.current_source: Optional[DataSource] = None
        
        # Statistics
        self.total_fetches = 0
        self.successful_fetches = 0
        self.failed_fetches = 0
        self.source_usage_count = {}
    
    def register_source(self, name: str, fetch_func: Callable, priority: int = 0):
        """
        Register a data source for fallback support
        
        Args:
            name: Source identifier (e.g., "NewsAPI", "FMP", "WebScraper")
            fetch_func: Function to fetch data (takes stock_symbol as arg, returns data or None)
            priority: Lower number = higher priority (0 is highest, 99 is lowest)
        
        Example:
            self.register_source("NewsAPI", self._fetch_from_newsapi, priority=0)
            self.register_source("AlphaVantage", self._fetch_from_alpha_vantage, priority=1)
            self.register_source("WebScraper", self._fetch_from_web, priority=2)
        """
        source = DataSource(name, fetch_func, priority)
        self.sources.append(source)
        # Sort by priority (lowest number first)
        self.sources.sort(key=lambda s: s.priority)
        self.source_usage_count[name] = 0
        print(f"  📌 Registered source: {name} (priority: {priority})")
    
    def get_available_sources(self) -> List[DataSource]:
        """Get list of available sources, sorted by priority"""
        available = [s for s in self.sources if s.can_use()]
        return sorted(available, key=lambda s: s.priority)
    
    @abstractmethod
    def setup_sources(self):
        """
        Setup and register all data sources
        Must be implemented by child classes
        
        Example implementation:
            def setup_sources(self):
                if self.api_key_1:
                    self.register_source("API1", self._fetch_from_api1, priority=0)
                if self.api_key_2:
                    self.register_source("API2", self._fetch_from_api2, priority=1)
                # Web scraping as fallback
                self.register_source("Scraper", self._fetch_from_scraper, priority=99)
        """
        pass
    
    def fetch_data_with_fallback(self, stock_symbol: str) -> Optional[Any]:
        """
        Fetch data using fallback mechanism across multiple sources
        
        Args:
            stock_symbol: Stock ticker symbol
            
        Returns:
            Data from successful source, or None if all sources failed
        """
        self.total_fetches += 1
        available_sources = self.get_available_sources()
        
        if not available_sources:
            print(f"  ❌ [{stock_symbol}] No available sources")
            # Try to reset sources that might have timed out
            self._check_and_reset_sources()
            self.failed_fetches += 1
            return None
        
        # Try each available source in priority order
        for source in available_sources:
            try:
                # Attempt to fetch data
                data = source.fetch_func(stock_symbol)
                
                if data:
                    # Success!
                    source.record_success()
                    self.source_usage_count[source.name] += 1
                    self.successful_fetches += 1
                    
                    # Log source switch if changed
                    if source != self.current_source:
                        if self.current_source:
                            print(f"  🔄 Switched from {self.current_source.name} to {source.name}")
                        self.current_source = source
                    
                    return data
                else:
                    # Source returned None (no data available, but not an error)
                    print(f"  ℹ️  [{stock_symbol}] {source.name} returned no data")
                    
            except Exception as e:
                # Log the error
                error_msg = str(e)[:100]  # Truncate long error messages
                print(f"  ❌ [{stock_symbol}] {source.name} error: {error_msg}")
                
                # Record the failure (triggers circuit breaker logic)
                source.record_failure(e)
                
                # Continue to next source
                continue
        
        # All sources failed
        print(f"  💀 [{stock_symbol}] All {len(available_sources)} source(s) failed")
        self.failed_fetches += 1
        return None
    
    def _check_and_reset_sources(self):
        """Check if any sources can be reset from cooldown"""
        for source in self.sources:
            if source.status == SourceStatus.FAILED:
                if source.last_failure:
                    time_since_failure = (datetime.now() - source.last_failure).total_seconds()
                    if time_since_failure >= source.reset_after:
                        source._reset()
            
            elif source.cooldown_until and datetime.now() >= source.cooldown_until:
                source.cooldown_until = None
                source.status = SourceStatus.HEALTHY
                print(f"  ♻️  {source.name} cooldown expired - back to healthy")
    
    def fetch_data(self, stock_symbol):
        """
        Fetch data for a stock symbol (legacy compatibility)
        Uses fallback mechanism by default
        
        Args:
            stock_symbol: Stock ticker symbol
            
        Returns:
            dict: Data to send to Kafka, or None if failed
        """
        return self.fetch_data_with_fallback(stock_symbol)
    
    def fetch_and_send(self):
        """Fetch data for all stocks and send to Kafka"""
        print(f"\n[{self.name}] [{datetime.now().strftime('%H:%M:%S')}] Starting fetch cycle...")
        
        # Print source status summary
        self._print_source_status()
        
        # === OPTIMIZATION: Collect all data first, then batch send ===
        all_data = []
        
        for stock in self.stocks:
            try:
                data = self.fetch_data_with_fallback(stock)
                
                if data:
                    # Handle both single items and lists
                    if isinstance(data, list):
                        all_data.extend(data)
                        print(f"  ✅ [{stock}] Fetched {len(data)} items")
                    else:
                        all_data.append(data)
                        print(f"  ✅ [{stock}] Fetched 1 item")
                
                # === OPTIMIZATION: Reduced delay between stocks (0.5s -> 0.1s) ===
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  ❌ [{stock}] Processing error: {e}")
        
        # === OPTIMIZATION: Batch send all data at once ===
        if all_data:
            try:
                from utils.kafka_utils import send_batch_to_kafka
                sent = send_batch_to_kafka(self.producer, self.kafka_topic, all_data)
                print(f"  📤 Batch sent {sent}/{len(all_data)} items to Kafka")
            except ImportError:
                # Fallback to individual sends
                for item in all_data:
                    send_to_kafka(self.producer, self.kafka_topic, item)
        
        # Print summary
        self._print_fetch_summary()
    
    def _print_source_status(self):
        """Print status of all registered sources"""
        if not self.sources:
            return
        
        status_parts = []
        for source in self.sources:
            icon = source.get_status_icon()
            usage = self.source_usage_count.get(source.name, 0)
            status_parts.append(f"{icon} {source.name}({usage})")
        
        print(f"  📊 Sources: {' | '.join(status_parts)}")
    
    def _print_fetch_summary(self):
        """Print fetch statistics summary"""
        success_rate = (self.successful_fetches / self.total_fetches * 100) if self.total_fetches > 0 else 0
        print(f"  📈 Stats: {self.successful_fetches}/{self.total_fetches} successful ({success_rate:.1f}%)")
    
    def setup(self):
        """
        Setup API clients, validate config, etc.
        Calls setup_sources() which must be implemented by child classes
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            print(f"\n🔧 Setting up {self.name}...")
            
            # Call child class implementation to register sources
            self.setup_sources()
            
            if not self.sources:
                print(f"  ⚠️  Warning: No sources registered")
                print(f"  ℹ️  Override setup_sources() to register data sources")
                return False
            
            print(f"  ✅ Registered {len(self.sources)} source(s)")
            return True
            
        except Exception as e:
            print(f"  ❌ Setup failed: {e}")
            return False
    
    def initialize(self):
        """Initialize the producer (called once at startup)"""
        print("=" * 70)
        print(f"Initializing {self.name}")
        print(f"Topic: {self.kafka_topic}")
        print(f"Interval: {self.fetch_interval}s")
        print(f"Stocks: {', '.join(self.stocks)}")
        print("=" * 70)
        
        # Setup sources
        if not self.setup():
            print(f"[{self.name}] ❌ Setup failed")
            return False
        
        # Connect to Kafka
        self.producer = get_kafka_producer()
        if not self.producer:
            print(f"[{self.name}] ❌ Failed to connect to Kafka")
            return False
        
        print(f"[{self.name}] ✅ Ready!\n")
        return True
    
    def cleanup(self):
        """Cleanup resources"""
        if self.producer:
            self.producer.close()
        print(f"\n[{self.name}] ✅ Cleaned up")
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        def signal_handler(sig, frame):
            print(f"\n{'=' * 70}")
            print(f"🛑 Shutting down {self.name}...")
            print("=" * 70)
            
            # Print final statistics
            print(f"\n📊 Final Statistics:")
            print(f"  Total fetches: {self.total_fetches}")
            print(f"  Successful: {self.successful_fetches}")
            print(f"  Failed: {self.failed_fetches}")
            print(f"\n📈 Source Usage:")
            for source_name, count in sorted(self.source_usage_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {source_name}: {count} fetches")
            
            if self.scheduler:
                self.scheduler.shutdown(wait=False)
            self.cleanup()
            print("\n✅ Shutdown complete")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def run(self):
        """
        Run the producer with built-in scheduler.
        This is the main entry point for standalone execution.
        """
        print("=" * 70)
        print(f"{self.name} - Starting...")
        print("=" * 70)
        
        # Initialize producer
        if not self.initialize():
            print(f"❌ Failed to initialize {self.name}")
            sys.exit(1)
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Create and configure scheduler
        self.scheduler = BlockingScheduler()
        
        # Schedule the fetch_and_send job
        self.scheduler.add_job(
            self.fetch_and_send,
            trigger=IntervalTrigger(seconds=self.fetch_interval),
            id=f'{self.name}_job',
            name=self.name,
            max_instances=1
        )
        
        # Run once immediately
        print(f"🚀 Running initial fetch...\n")
        try:
            self.fetch_and_send()
        except Exception as e:
            print(f"⚠️  Initial fetch failed: {e}")
        
        # Start scheduled execution
        print(f"\n{'=' * 70}")
        print(f"✅ Scheduled to run every {self.fetch_interval} seconds")
        print("Press Ctrl+C to stop")
        print("=" * 70 + "\n")
        
        # Start scheduler (blocking - keeps the program running)
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass