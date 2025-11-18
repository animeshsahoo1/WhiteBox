"""
Demo Market Data Service - Standalone CSV Replay
Runs as a Docker service, reads from CSV files instead of Kafka
"""

import pathway as pw
import os
from pathlib import Path
from dotenv import load_dotenv
from agents.market_agent2 import process_market_stream_with_agents

load_dotenv()


class MarketDataSchema(pw.Schema):
    """Schema for market data stream."""
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


def main():
    """
    Run demo market analysis pipeline using CSV replay.
    Configured via environment variables for Docker deployment.
    """
    
    # Get configuration from environment
    ticker = os.getenv("DEMO_TICKER", "AAPL")
    interval = os.getenv("DEMO_INTERVAL", "5m")
    speedup = float(os.getenv("DEMO_SPEEDUP", "10.0"))
    lookback_minutes = int(os.getenv("MARKET_LOOKBACK_MINUTES", "10"))
    hop_minutes = int(os.getenv("MARKET_HOP_MINUTES", "5"))
    min_data_points = int(os.getenv("MIN_DATA_POINTS", "30"))
    data_dir = os.getenv("DEMO_DATA_DIR", "/app/demo_data")
    
    print("=" * 70)
    print("🚀 DEMO MARKET DATA SERVICE - CSV REPLAY MODE")
    print("=" * 70)
    print(f"📊 Ticker: {ticker}")
    print(f"⏱️  Interval: {interval}")
    print(f"⚡ Speedup: {speedup}x")
    print(f"📈 Window: {lookback_minutes}min lookback, {hop_minutes}min hop")
    print(f"📊 Min Data Points: {min_data_points}")
    print(f"📁 Data Directory: {data_dir}")
    print("=" * 70)
    print()
    
    # Build CSV path
    csv_file = Path(data_dir) / f"{ticker}_{interval}.csv"
    
    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_file}")
        print(f"\n💡 Please ensure CSV files are mounted to /app/demo_data/")
        print(f"   Expected file: {ticker}_{interval}.csv")
        print(f"\n   Available files in {data_dir}:")
        if Path(data_dir).exists():
            for f in Path(data_dir).glob("*.csv"):
                print(f"     - {f.name}")
        return
    
    print(f"✅ Found CSV file: {csv_file}")
    print()
    
    # Read CSV and parse timestamps
    print(f"📡 Loading CSV data and parsing timestamps...")
    import pandas as pd
    
    df = pd.read_csv(csv_file)
    
    # Convert ISO datetime strings to Unix timestamps (seconds)
    df['sent_at_timestamp'] = pd.to_datetime(df['sent_at']).astype('int64') // 10**9
    
    # Save temporary CSV with numeric timestamps
    temp_csv = Path("/tmp") / f"{ticker}_{interval}_timestamped.csv"
    df.to_csv(temp_csv, index=False)
    
    print(f"   Converted timestamps to Unix epoch")
    print(f"   Time range: {df['sent_at'].iloc[0]} to {df['sent_at'].iloc[-1]}")
    print()
    
    # Create streaming table from CSV using Pathway's replay_csv_with_time
    print(f"📡 Creating time-based CSV replay stream...")
    print(f"   Time column: sent_at_timestamp (Unix epoch)")
    print(f"   Speedup: {speedup}x")
    print()
    
    # Define schema with numeric timestamp column
    class MarketDataSchemaWithTimestamp(pw.Schema):
        symbol: str
        timestamp: str
        sent_at: str
        sent_at_timestamp: int  # Numeric timestamp for replay
        open: float
        high: float
        low: float
        current_price: float
        previous_close: float
        change: float
        change_percent: float
    
    market_table = pw.demo.replay_csv_with_time(
        str(temp_csv),
        schema=MarketDataSchemaWithTimestamp,
        time_column="sent_at_timestamp",
        unit="s",
        speedup=speedup
    )
    
    # Remove the numeric timestamp column before processing
    market_table = market_table.select(
        symbol=pw.this.symbol,
        timestamp=pw.this.timestamp,
        sent_at=pw.this.sent_at,
        open=pw.this.open,
        high=pw.this.high,
        low=pw.this.low,
        current_price=pw.this.current_price,
        previous_close=pw.this.previous_close,
        change=pw.this.change,
        change_percent=pw.this.change_percent
    )
    
    # Process market data with multi-agent system
    reports_directory = f"/app/reports/demo/{ticker}_{interval}"
    
    print(f"🤖 Initializing market agent analysis pipeline...")
    print(f"⚙️  Window: {lookback_minutes}min lookback, {hop_minutes}min hop")
    print(f"📁 Reports: {reports_directory}")
    print()
    
    analyzed_table = process_market_stream_with_agents(
        market_table,
        lookback_minutes=lookback_minutes,
        hop_minutes=hop_minutes,
        min_data_points=min_data_points,
        reports_directory=reports_directory
    )
    
    # Write analysis results to CSV
    output_path = os.path.join(reports_directory, "market_analysis_stream.csv")
    pw.io.csv.write(
        analyzed_table.select(
            symbol=pw.this.symbol,
            window_start=pw.this.window_start,
            window_end=pw.this.window_end,
            data_points=pw.this.data_points,
            latest_price=pw.this.latest_price,
            agent_results=pw.this.agent_results
        ),
        output_path
    )
    
    print("\n✅ Demo Service initialized")
    print(f"📁 Reports directory: {reports_directory}/")
    print(f"📝 Analysis stream: {output_path}")
    print("\n🚀 Starting stream processing...")
    print("   Service will run until CSV data is exhausted or container is stopped")
    print()
    
    pw.run()
    
    print("\n✅ CSV replay completed!")


if __name__ == "__main__":
    main()
