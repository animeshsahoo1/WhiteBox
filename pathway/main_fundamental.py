import pathway as pw
import os
from dotenv import load_dotenv
from consumers.fundamental_data_consumer import FundamentalDataConsumer
from agents.fundamental_agent import process_fundamental_stream
try:  # Allow running as `python pathway/main_fundamental.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

def main():
    print("=" * 70)
    print("Pathway Fundamental Analysis System (Redis-Backed Architecture)")
    print("=" * 70)

    # Initialize consumer
    fundamental_consumer = FundamentalDataConsumer()
    fundamental_table = fundamental_consumer.consume()
    reports_directory = "/app/reports/fundamental"
    
    # Process fundamental data
    updated_fundamental_reports = process_fundamental_stream(
        fundamental_table, reports_directory=reports_directory
    )

    # Stream updates to Redis cache via pw.io.python observer
    fundamental_observer = get_report_observer("fundamental")
    pw.io.python.write(
        updated_fundamental_reports,
        fundamental_observer,
        name="fundamental_reports_stream",
    )
    print("📤 Streaming fundamental updates to Redis cache via pw.io.python")

    # Optional: Write to CSV for logging
    output_path = os.path.join(reports_directory, "fundamental_reports_stream.csv")
    pw.io.csv.write(updated_fundamental_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")

    print("\n✅ Fundamental pipeline with redis-backed architecture initialized. Starting stream processing...")
    pw.run()

if __name__ == "__main__":
    load_dotenv()
    main()