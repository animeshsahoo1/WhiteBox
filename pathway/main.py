import pathway as pw
import os
from consumers.news_consumer import NewsConsumer
from agents.news_agent import NewsReportUpdater
from consumers.market_data_consumer import MarketDataConsumer
from consumers.sentiment_consumer import SentimentConsumer
from agents.news_agent import process_news_stream

def main():
    print("=" * 70)
    print("Pathway Kafka Consumer System")
    print("=" * 70)
    
    # Initialize consumers
    news_consumer = NewsConsumer()
    market_consumer = MarketDataConsumer()
    sentiment_consumer = SentimentConsumer()
    
    # Consume data and get tables
    news_table = news_consumer.consume()
    market_table = market_consumer.consume()
    
    # For sentiment, use flattened mode to get individual posts as rows
    sentiment_table = sentiment_consumer.consume_flattened()
    # Alternative: sentiment_table = sentiment_consumer.consume()  # Keeps posts grouped
    reports_directory = os.path.join(os.path.dirname(__file__), "reports")
    updated_news_reports = process_news_stream(news_table, reports_directory=reports_directory)
    pw.debug.compute_and_print(updated_news_reports)

    print("\n✅ All consumers initialized. Starting stream processing...")
    pw.run()

if __name__ == '__main__':
    main()