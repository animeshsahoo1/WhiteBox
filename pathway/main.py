import pathway as pw
from consumers.news_consumer import NewsConsumer
from consumers.market_data_consumer import MarketDataConsumer
from consumers.sentiment_consumer import SentimentConsumer

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

    print("\n✅ All consumers initialized. Starting stream processing...")
    pw.run()

if __name__ == '__main__':
    main()