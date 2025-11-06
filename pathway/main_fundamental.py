import pathway as pw
import os
from consumers.fundamental_data_consumer import FundamentalDataConsumer
from agents.fundamental_agent import process_fundamental_stream


def main():
    print("=" * 70)
    print("Pathway Fundamental Analysis System")
    print("=" * 70)

    # Initialize consumer
    fundamental_consumer = FundamentalDataConsumer()

    # Consume data and get table
    fundamental_table = fundamental_consumer.consume()

    # Process fundamental data and generate AI reports
    reports_directory = os.path.join(os.path.dirname(__file__), "reports/fundamental")
    updated_fundamental_reports = process_fundamental_stream(
        fundamental_table, reports_directory=reports_directory
    )

    # Write analysis results to CSV
    output_path = os.path.join(reports_directory, "fundamental_reports_stream.csv")
    pw.io.csv.write(updated_fundamental_reports, output_path)
    print(f"📝 Writing reports stream to: {output_path}")

    print("\n✅ Fundamental consumer initialized. Starting stream processing...")
    pw.run()


if __name__ == "__main__":
    main()
