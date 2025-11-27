"""
Demo Market Data Producer using yfinance historical data.
Streams 1 month of historical data at configurable intervals.
"""

import yfinance as yf
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json


def fetch_and_save_historical_data(
    tickers=["AAPL", "GOOGL"],
    intervals=["1m", "5m", "15m", "30m", "1h"],
    period="1mo",
    output_dir="./demo_data"
):
    """
    Fetch historical data from yfinance and save as CSV files.
    
    Args:
        tickers: List of stock symbols
        intervals: List of intervals ('1m', '5m', '10m', '30m', '1h')
        period: Data period ('1mo', '2mo', '3mo', etc.)
        output_dir: Directory to save CSV files
        
    Note: 
        - 1m data is limited to 7 days by yfinance
        - For longer periods, use 5m, 15m, 30m, 1h, etc.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"🔄 Fetching historical market data from yfinance...")
    print(f"   Tickers: {tickers}")
    print(f"   Intervals: {intervals}")
    print(f"   Period: {period}")
    print(f"   Output: {output_dir}")
    print()
    
    metadata = {}
    
    for ticker in tickers:
        print(f"📊 Processing {ticker}...")
        metadata[ticker] = {}
        
        for interval in intervals:
            try:
                print(f"   Fetching {interval} data...", end=" ")
                
                # Adjust period for 1m data (max 7 days)
                fetch_period = "7d" if interval == "1m" else period
                
                # Fetch data
                stock = yf.Ticker(ticker)
                df = stock.history(period=fetch_period, interval=interval)
                
                if df.empty:
                    print(f"❌ No data returned")
                    continue
                
                # Reset index to get datetime as column
                df.reset_index(inplace=True)
                
                # Rename columns to match our schema
                df.rename(columns={
                    'Datetime': 'timestamp',
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'current_price',
                    'Volume': 'volume'
                }, inplace=True)
                
                # Calculate change and change_percent
                df['previous_close'] = df['current_price'].shift(1).fillna(df['current_price'])
                df['change'] = df['current_price'] - df['previous_close']
                df['change_percent'] = (df['change'] / df['previous_close'] * 100).fillna(0.0)
                
                # Add symbol and sent_at columns
                df['symbol'] = ticker
                df['sent_at'] = df['timestamp']  # Use same timestamp for demo
                
                # Convert timestamp to ISO format string
                df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                df['sent_at'] = df['sent_at'].dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
                
                # Select final columns
                columns = [
                    'symbol', 'timestamp', 'sent_at', 'open', 'high', 'low', 
                    'current_price', 'previous_close', 'change', 'change_percent'
                ]
                df = df[columns]
                
                # Save to CSV
                filename = f"{ticker}_{interval}.csv"
                filepath = output_path / filename
                df.to_csv(filepath, index=False)
                
                # Store metadata
                metadata[ticker][interval] = {
                    'filename': filename,
                    'rows': len(df),
                    'start': df['timestamp'].iloc[0],
                    'end': df['timestamp'].iloc[-1],
                    'price_range': [float(df['low'].min()), float(df['high'].max())]
                }
                
                print(f"✅ {len(df)} rows saved to {filename}")
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    # Save metadata
    metadata_path = output_path / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Data fetch complete! Metadata saved to {metadata_path}")
    return metadata


def print_available_data(metadata_path="./demo_data/metadata.json"):
    """Print summary of available demo data."""
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        print("\n" + "="*70)
        print("📊 AVAILABLE DEMO DATA")
        print("="*70)
        
        for ticker, intervals in metadata.items():
            print(f"\n{ticker}:")
            for interval, info in intervals.items():
                print(f"  {interval:>4s}: {info['rows']:>5d} rows | "
                      f"{info['start']} to {info['end']}")
                print(f"        Price range: ${info['price_range'][0]:.2f} - ${info['price_range'][1]:.2f}")
        
        print("\n" + "="*70)
        
    except FileNotFoundError:
        print(f"⚠️ Metadata file not found: {metadata_path}")
        print("   Run fetch_and_save_historical_data() first!")


if __name__ == "__main__":
    # Fetch historical data for demo
    metadata = fetch_and_save_historical_data(
        tickers=["AAPL", "GOOGL"],
        intervals=["1m", "5m", "15m", "30m", "1h"],
        period="1mo",  # 1 month (limited to 7d for 1m data)
        output_dir="./demo_data"
    )
    
    # Print summary
    print_available_data("./demo_data/metadata.json")
    
    print("\n" + "="*70)
    print("🚀 NEXT STEPS")
    print("="*70)
    print("Run the demo pipeline with:")
    print("  python demo_market_pipeline.py --ticker AAPL --interval 5m --input-rate 10.0")
    print()
    print("Available options:")
    print("  --ticker: AAPL, GOOGL")
    print("  --interval: 1m, 5m, 10m, 30m, 1h")
    print("  --input-rate: Rows per second (e.g., 10.0 = 10 rows/sec)")
    print("="*70)
