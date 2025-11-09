import pathway as pw
import os
from dotenv import load_dotenv
from consumers.news_consumer import NewsConsumer
from agents.news_agent import process_news_stream
try:  # Allow running as `python pathway/main_news.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

def main():
    print("=" * 70)
    print("Pathway News Analysis System (Redis-Backed Architecture)")
    print("=" * 70)

    # Initialize consumer
    news_consumer = NewsConsumer()
    news_table = news_consumer.consume()

    # Process news data and generate AI reports
    reports_directory = os.path.join(os.path.dirname(__file__), "reports/news")
    updated_news_reports = process_news_stream(
        news_table, reports_directory=reports_directory
    )

    # Stream updates to Redis cache via pw.io.python observer
    news_observer = get_report_observer("news")
    pw.io.python.write(
        updated_news_reports,
        news_observer,
        name="news_reports_stream",
    )
    print("📤 Streaming news updates to Redis cache via pw.io.python")

    # Optional: Write to CSV
    output_path = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(updated_news_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")

    print("\n✅ News pipeline with redis-backed architecture initialized. Starting stream processing...")
    pw.run()

if __name__ == "__main__":
    load_dotenv()
    main()
