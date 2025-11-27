"""
Demo Market Analysis Pipeline using historical yfinance data.
Streams pre-fetched data and runs the market agent analysis.
"""

import argparse
import pathway as pw
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from agents.market_agent2 import process_market_stream_with_agents


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


def run_demo_pipeline(
    ticker: str = "AAPL",
    interval: str = "5m",
    input_rate: float = 10.0,
    lookback_minutes: int = 10,
    hop_minutes: int = 5,
    min_data_points: int = 30,
    data_dir: str = "./demo_data"
):
    """
    Run the demo market analysis pipeline.
    
    Args:
        ticker: Stock symbol (AAPL, GOOGL)
        interval: Data interval (1m, 5m, 10m, 30m, 1h)
        input_rate: Rows streamed per second
        lookback_minutes: Window duration for analysis
        hop_minutes: How often to generate reports
        min_data_points: Minimum data points per window
        data_dir: Directory containing demo CSV files
    """
    
    data_path = Path(data_dir)
    csv_file = data_path / f"{ticker}_{interval}.csv"
    
    if not csv_file.exists():
        print(f"❌ Data file not found: {csv_file}")
        print(f"\nRun this first to fetch data:")
        print(f"  python streaming/producers/demo_market_producer.py")
        return
    
    print("=" * 70)
    print("🚀 DEMO MARKET ANALYSIS PIPELINE")
    print("=" * 70)
    print(f"📊 Ticker: {ticker}")
    print(f"⏱️  Interval: {interval}")
    print(f"🔄 Input Rate: {input_rate} rows/second")
    print(f"📈 Analysis Window: {lookback_minutes} minutes")
    print(f"⏳ Report Frequency: Every {hop_minutes} minutes")
    print(f"📊 Min Data Points: {min_data_points}")
    print(f"📁 Data Source: {csv_file}")
    print("=" * 70)
    print()
    
    # Create streaming table from CSV
    print(f"📡 Streaming data from {csv_file}...")
    market_table = pw.demo.replay_csv(
        str(csv_file),
        schema=MarketDataSchema,
        input_rate=input_rate
    )
    
    # Run market agent analysis
    print(f"🤖 Starting market agent analysis pipeline...")
    analyzed_table = process_market_stream_with_agents(
        market_table,
        lookback_minutes=lookback_minutes,
        hop_minutes=hop_minutes,
        min_data_points=min_data_points,
        reports_directory=f"./reports/demo/{ticker}_{interval}"
    )
    
    # Run the pipeline
    print(f"\n🏁 Pipeline running... Press Ctrl+C to stop")
    print(f"📝 Reports will be saved to: ./reports/demo/{ticker}_{interval}/")
    print()
    
    pw.run()


def main():
    parser = argparse.ArgumentParser(
        description="Demo Market Analysis Pipeline with historical data"
    )
    
    parser.add_argument(
        "--ticker",
        type=str,
        default="AAPL",
        choices=["AAPL", "GOOGL"],
        help="Stock ticker symbol (default: AAPL)"
    )
    
    parser.add_argument(
        "--interval",
        type=str,
        default="5m",
        choices=["1m", "5m", "10m", "30m", "1h"],
        help="Data interval (default: 5m)"
    )
    
    parser.add_argument(
        "--input-rate",
        type=float,
        default=10.0,
        help="Rows streamed per second (default: 10.0)"
    )
    
    parser.add_argument(
        "--lookback",
        type=int,
        default=10,
        help="Analysis window duration in minutes (default: 10)"
    )
    
    parser.add_argument(
        "--hop",
        type=int,
        default=5,
        help="Report frequency in minutes (default: 5)"
    )
    
    parser.add_argument(
        "--min-points",
        type=int,
        default=30,
        help="Minimum data points per window (default: 30)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="../streaming/producers/demo_data",
        help="Directory containing demo CSV files"
    )
    
    args = parser.parse_args()
    
    # Calculate recommended min_data_points based on interval
    interval_to_seconds = {
        "1m": 60,
        "5m": 300,
        "10m": 600,
        "30m": 1800,
        "1h": 3600
    }
    
    interval_seconds = interval_to_seconds.get(args.interval, 300)
    recommended_points = (args.lookback * 60) // interval_seconds
    
    if args.min_points < recommended_points:
        print(f"⚠️  WARNING: min_points ({args.min_points}) is low for {args.interval} interval")
        print(f"   Recommended: {recommended_points} points for {args.lookback}min window")
        print(f"   Calculation: ({args.lookback} min * 60 sec) / {interval_seconds} sec = {recommended_points}")
        print()
    
    run_demo_pipeline(
        ticker=args.ticker,
        interval=args.interval,
        input_rate=args.input_rate,
        lookback_minutes=args.lookback,
        hop_minutes=args.hop,
        min_data_points=args.min_points,
        data_dir=args.data_dir
    )


if __name__ == "__main__":
    main()
