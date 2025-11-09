import pathway as pw
import os
from dotenv import load_dotenv
from consumers.sentiment_consumer import SentimentConsumer
from agents.sentiment_agent import process_sentiment_stream
try:  # Allow running as `python pathway/main_sentiment.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

def main():
    print("=" * 70)
    print("Pathway Sentiment Analysis System (Redis-Backed Architecture)")
    print("=" * 70)

    # Initialize consumer
    sentiment_consumer = SentimentConsumer()
    sentiment_table = sentiment_consumer.consume_flattened()

    # Process sentiment data
    reports_directory = os.path.join(os.path.dirname(__file__), "reports/sentiment")
    updated_sentiment_reports = process_sentiment_stream(
        sentiment_table, reports_directory=reports_directory
    )

    # Stream updates to Redis cache via pw.io.python observer
    sentiment_observer = get_report_observer("sentiment")
    pw.io.python.write(
        updated_sentiment_reports,
        sentiment_observer,
        name="sentiment_reports_stream",
    )
    print("📤 Streaming sentiment updates to Redis cache via pw.io.python")

    # Optional: Write to CSV
    output_path = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(updated_sentiment_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")

    print("\n✅ Sentiment pipeline with redis-backed architecture initialized. Starting stream processing...")
    pw.run()

if __name__ == "__main__":
    load_dotenv()
    main()
