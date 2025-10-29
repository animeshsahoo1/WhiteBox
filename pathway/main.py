import pathway as pw
from consumers.news_consumer import NewsConsumer
from consumers.market_data_consumer import MarketDataConsumer
from consumers.sentiment_consumer import SentimentConsumer
from agents.sentiment_report_producer import create_report_reducer

def main():
    print("Pathway Kafka Consumer System")
    
    news_consumer = NewsConsumer()
    market_consumer = MarketDataConsumer()
    sentiment_consumer = SentimentConsumer()
    
    news_table = news_consumer.consume()
    market_table = market_consumer.consume()
    sentiment_table = sentiment_consumer.consume_flattened()

    pw.io.csv.write(market_table, "/app/output/market_data.csv")
    pw.io.csv.write(news_table, "/app/output/news_data.csv")
    pw.io.csv.write(sentiment_table, "/app/output/sentiment_data.csv")
    
    # Generate sentiment reports using OpenAI if enabled
    report_reducer = create_report_reducer(output_dir="/app/reports")
    
    reports_table = sentiment_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        report_content=report_reducer(
            pw.this.symbol, pw.this.post_id, pw.this.ticker_symbol, pw.this.company_name,
            pw.this.subreddit, pw.this.post_title, pw.this.post_content, pw.this.post_comments,
            pw.this.sentiment_post_title, pw.this.sentiment_post_content, pw.this.sentiment_comments,
            pw.this.post_url, pw.this.num_comments, pw.this.score, pw.this.created_utc, pw.this.match_type
        )
    )
    
    pw.run()

if __name__ == '__main__':
    main()