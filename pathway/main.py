import pathway as pw
from consumers.news_consumer import NewsConsumer
from consumers.market_data_consumer import MarketDataConsumer

def main():
    print("=" * 70)
    print("Pathway Kafka Consumer System")
    print("=" * 70)
    
    # Initialize consumers
    news_consumer = NewsConsumer()
    market_consumer = MarketDataConsumer()
    
    # Consume data and get tables
    news_table = news_consumer.consume()
    market_table = market_consumer.consume()

    print("\n✅ All consumers initialized. Starting stream processing...")
    pw.run()

if __name__ == '__main__':
    main()