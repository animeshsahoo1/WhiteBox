import pathway as pw
import os
from dotenv import load_dotenv
from consumers.market_data_consumer import MarketDataConsumer
from agents.market_agent import process_market_stream
try:  # Allow running as `python pathway/main_market.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

def main():
    print("=" * 70)
    print("Pathway Market Data Consumer System (Redis-Backed Architecture)")
    print("=" * 70)

    # Initialize consumer
    market_consumer = MarketDataConsumer()
    market_table = market_consumer.consume()

    # Process market data and generate reports
    reports_directory = os.path.join(os.path.dirname(__file__), "reports/market")
    analyzed_reports = process_market_stream(
        market_table, reports_directory=reports_directory
    )

    # Format the output table with symbol and report columns
    updated_market_reports = analyzed_reports.select(
        symbol=pw.this.symbol,
        report=pw.this.llm_analysis,
        window_end=pw.this.window_end
    ).groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        report=pw.reducers.latest(pw.this.report),
        last_updated=pw.reducers.latest(pw.this.window_end)
    )

    # Stream updates to Redis cache via pw.io.python observer
    market_observer = get_report_observer("market")
    pw.io.python.write(
        updated_market_reports,
        market_observer,
        name="market_reports_stream",
    )
    print("📤 Streaming market updates to Redis cache via pw.io.python")

    # Optional: Write analysis results to CSV
    output_path = os.path.join(reports_directory, "market_analysis_stream.csv")
    pw.io.csv.write(updated_market_reports, output_path)
    print(f"📝 Writing analysis stream to CSV: {output_path}")

    print("\n✅ Market pipeline with redis-backed architecture initialized. Starting stream processing...")
    pw.run()

if __name__ == "__main__":
    load_dotenv()
    main()
