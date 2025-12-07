import pathway as pw
import os
from pathlib import Path
from dotenv import load_dotenv
from consumers.market_data_consumer import MarketDataConsumer
from agents.market_agent2 import process_market_stream_with_agents


# Schema for demo mode CSV replay
class MarketDataSchema(pw.Schema):
    """Schema for market data stream (used in demo mode)."""
    symbol: str
    timestamp: str
    sent_at: str
    open: float
    high: float
    low: float
    current_price: float
    previous_close: float
    change: float
    change_percent: float


def get_market_table(use_dummy: bool):
    """
    Get market data table from either Kafka or demo CSV.
    
    Args:
        use_dummy: If True, use pw.demo.replay_csv() with demo data.
                   If False, use MarketDataConsumer (Kafka).
    
    Returns:
        pw.Table: Market data stream table.
    """
    if use_dummy:
        demo_data_dir = os.getenv("DEMO_DATA_DIR", "/app/streaming/data/demo_data")
        demo_ticker = os.getenv("DEMO_TICKER", "AAPL")
        demo_interval = os.getenv("DEMO_INTERVAL", "5m")
        input_rate = float(os.getenv("DEMO_INPUT_RATE", "10.0"))  # rows per second
        
        csv_file = Path(demo_data_dir) / f"{demo_ticker}_{demo_interval}.csv"
        
        if not csv_file.exists():
            raise FileNotFoundError(
                f"Demo data file not found: {csv_file}\n"
                f"Run: python streaming/producers/demo_market_producer.py"
            )
        
        print(f"🧪 DUMMY MODE: Replaying from {csv_file} at {input_rate} rows/sec")
        return pw.demo.replay_csv(
            str(csv_file),
            schema=MarketDataSchema,
            input_rate=input_rate
        )
    else:
        print("📡 LIVE MODE: Consuming from Kafka topic 'market-data'")
        market_consumer = MarketDataConsumer()
        return market_consumer.consume()

def main():
    print("=" * 70)
    print("Pathway Market Data Consumer System (Multi-Agent + Redis)")
    print("=" * 70)

    # Check for dummy mode (USE_DUMMY_MARKET takes priority over USE_DUMMY)
    use_dummy_market = os.getenv("USE_DUMMY_MARKET")
    if use_dummy_market is not None:
        use_dummy = use_dummy_market.lower() == "true"
    else:
        use_dummy = os.getenv("USE_DUMMY", "false").lower() == "true"
    
    if use_dummy:
        print("🧪 MODE: DUMMY (using demo CSV data)")
    else:
        print("📡 MODE: LIVE (using Kafka streaming)")

    # Ensure reports directory exists
    reports_directory = "/app/reports/market"
    os.makedirs(reports_directory, exist_ok=True)
    print(f"📁 Reports directory ready: {reports_directory}")

    # Get market data table (either from Kafka or demo CSV)
    market_table = get_market_table(use_dummy)

    # Process market data with multi-agent system and generate comprehensive reports
    
    # Configure sliding window parameters
    lookback_minutes = int(os.getenv("MARKET_LOOKBACK_MINUTES", "10"))
    hop_minutes = int(os.getenv("MARKET_HOP_MINUTES", "5"))
    min_data_points = int(os.getenv("MARKET_MIN_DATA_POINTS", "3"))  # Lower default for sparse data
    
    print(f"⚙️  Window Configuration: {lookback_minutes}min lookback, {hop_minutes}min hop, {min_data_points} min points")
    
    analyzed_table = process_market_stream_with_agents(
        market_table, 
        lookback_minutes=lookback_minutes,
        hop_minutes=hop_minutes,
        min_data_points=min_data_points,
        reports_directory=reports_directory
    )

    # NOTE: Market reports are written to Redis directly by market_agent2.py via save_report_to_redis()
    # This also publishes WebSocket events. No observer needed to avoid race conditions.

    # Stream images to Redis cache (separate endpoint)
    try:
        from redis_cache import get_report_observer
    except ImportError:
        from .redis_cache import get_report_observer
    image_observer = get_report_observer("images")
    pw.io.python.write(
        analyzed_table.select(
            symbol=pw.this.symbol,
            window_start=pw.this.window_start,
            window_end=pw.this.window_end,
            images=pw.this.images
        ),
        image_observer,
        name="market_images_stream",
    )
    print("📤 Streaming indicator images to Redis cache")

    # Optional: Write analysis results to CSV
    output_path = os.path.join(reports_directory, "market_analysis_stream.csv")
    pw.io.csv.write(
        analyzed_table.select(
            symbol=pw.this.symbol,
            window_start=pw.this.window_start,
            window_end=pw.this.window_end,
            data_points=pw.this.data_points,
            latest_price=pw.this.latest_price,
            final_decision=pw.this.agent_results
        ), 
        output_path
    )
    print(f"📝 Writing analysis stream to CSV: {output_path}")

    print("\n✅ Multi-Agent Market Pipeline with Redis initialized")
    print("   - Market reports cached in Redis by agent (key: reports:{SYMBOL})")
    print("   - Indicator images cached in Redis (key: images:{SYMBOL}:{TIMESTAMP})")
    print("   - Endpoint: /api/market/images/{symbol} or /api/market/images/{symbol}/{timestamp}")
    print("\n🚀 Starting stream processing...")
    
    # Run with or without persistence based on mode
    if use_dummy:
        # Demo mode: no persistence (replay from scratch each time)
        print("🔄 Demo mode: Running without persistence")
        pw.run(monitoring_level=pw.MonitoringLevel.NONE)
    else:
        # Live mode: enable persistence for state recovery
        persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
        os.makedirs(persistence_path, exist_ok=True)
        print(f"💾 Persistence enabled at: {persistence_path}")
        pw.run(
            persistence_config=pw.persistence.Config.simple_config(
                pw.persistence.Backend.filesystem(persistence_path),
                snapshot_interval_ms=30000  # Snapshot every 30 seconds
            ),
            monitoring_level=pw.MonitoringLevel.NONE
        )

if __name__ == "__main__":
    load_dotenv()
    main()
