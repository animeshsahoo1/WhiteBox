import pathway as pw
import os
from consumers.sentiment_consumer import SentimentConsumer
from agents.sentiment_agent import process_sentiment_stream


def main():
    print("=" * 70)
    print("Pathway Sentiment Analysis System")
    print("=" * 70)

    # Initialize consumer
    sentiment_consumer = SentimentConsumer()

    # Consume data and get flattened table
    sentiment_table = sentiment_consumer.consume_flattened()

    reports_directory = os.path.join(os.path.dirname(__file__), "reports/sentiment")
    updated_sentiment_reports = process_sentiment_stream(
        sentiment_table, reports_directory=reports_directory
    )

    output_path = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(updated_sentiment_reports, output_path)
    print(f"📝 Writing reports stream to: {output_path}")

    print("\n✅ Sentiment consumer initialized. Starting stream processing...")
    pw.run()


if __name__ == "__main__":
    main()