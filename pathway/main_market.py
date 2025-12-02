import pathway as pw
import os
from dotenv import load_dotenv
from consumers.market_data_consumer import MarketDataConsumer
from agents.market_agent2 import process_market_stream_with_agents
try:  # Allow running as `python pathway/main_market.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

def main():
    print("=" * 70)
    print("Pathway Market Data Consumer System (Multi-Agent + Redis)")
    print("=" * 70)

    # Initialize consumer
    market_consumer = MarketDataConsumer()
    market_table = market_consumer.consume()

    # Process market data with multi-agent system and generate comprehensive reports
    reports_directory = "/app/reports/market"
    
    # Configure sliding window parameters
    lookback_minutes = int(os.getenv("MARKET_LOOKBACK_MINUTES", "10"))
    hop_minutes = int(os.getenv("MARKET_HOP_MINUTES", "5"))
    
    print(f"⚙️  Window Configuration: {lookback_minutes}min lookback, {hop_minutes}min hop")
    
    analyzed_table = process_market_stream_with_agents(
        market_table, 
        lookback_minutes=lookback_minutes,
        hop_minutes=hop_minutes,
        reports_directory=reports_directory
    )

    # Format comprehensive reports for Redis caching
    market_reports = analyzed_table.select(
        symbol=pw.this.symbol,
        report=pw.this.agent_results,
        window_end=pw.this.window_end,
        images=pw.this.images,
        indicators=pw.this.indicators,
        kline_data=pw.this.kline_data
    ).groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        report=pw.reducers.latest(pw.this.report),
        last_updated=pw.reducers.latest(pw.this.window_end),
        images=pw.reducers.latest(pw.this.images),
        indicators=pw.reducers.latest(pw.this.indicators),
        kline_data=pw.reducers.latest(pw.this.kline_data)
    )

    # Stream market reports to Redis cache
    market_observer = get_report_observer("market")
    pw.io.python.write(
        market_reports,
        market_observer,
        name="market_reports_stream",
    )
    print("📤 Streaming market reports to Redis cache")

    # Stream images to Redis cache (separate endpoint)
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

    # Enable Pathway persistence for market state
    persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")

    print("\n✅ Multi-Agent Market Pipeline with Redis initialized")
    print("   - Market reports cached in Redis (key: reports:{SYMBOL})")
    print("   - Indicator images cached in Redis (key: images:{SYMBOL}:{TIMESTAMP})")
    print("   - Endpoint: /api/market/images/{symbol} or /api/market/images/{symbol}/{timestamp}")
    print("\n🚀 Starting stream processing...")
    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=60000  # Snapshot every 60 seconds
        )
    )

if __name__ == "__main__":
    load_dotenv()
    main()
