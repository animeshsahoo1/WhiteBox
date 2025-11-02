import pathway as pw
import os
from consumers.market_data_consumer import MarketDataConsumer
from agents.market_agent import process_market_stream


def main():
    print("=" * 70)
    print("Pathway Market Data Consumer System")
    print("=" * 70)

    # Initialize consumer
    market_consumer = MarketDataConsumer()

    # Consume data and get table
    market_table = market_consumer.consume()

    # Process market data and generate reports
    reports_directory = os.path.join(os.path.dirname(__file__), "reports/market")
    analyzed_market_data = process_market_stream(
        market_table, reports_directory=reports_directory
    )

    # Optional: Write analysis results to CSV
    output_path = os.path.join(os.path.dirname(__file__), "reports/market", "market_analysis_stream.csv")
    pw.io.csv.write(analyzed_market_data, output_path)
    print(f"📝 Writing analysis stream to: {output_path}")

    print("\n✅ Market consumer initialized. Starting stream processing...")
    pw.run()


if __name__ == "__main__":
    main()