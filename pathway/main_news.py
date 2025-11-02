import pathway as pw
import os
from consumers.news_consumer import NewsConsumer
from agents.news_agent import process_news_stream


def main():
    print("=" * 70)
    print("Pathway Kafka Consumer System")
    print("=" * 70)

    # Initialize consumers
    news_consumer = NewsConsumer()

    # Consume data and get tables
    news_table = news_consumer.consume()

    reports_directory = os.path.join(os.path.dirname(__file__), "reports/news")
    updated_news_reports = process_news_stream(
        news_table, reports_directory=reports_directory
    )

    output_path = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(updated_news_reports, output_path)
    print(f"📝 Writing reports stream to: {output_path}")

    print("\n✅ All consumers initialized. Starting stream processing...")
    pw.run()


if __name__ == "__main__":
    main()
