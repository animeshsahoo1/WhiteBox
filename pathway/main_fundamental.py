import pathway as pw
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from consumers.fundamental_data_consumer import FundamentalDataConsumer
from agents.fundamental_agent import process_fundamental_stream


# Schema for demo mode CSV replay
class FundamentalDataSchema(pw.Schema):
    """Schema for fundamental data stream (used in demo mode).
    
    JSON fields are read as strings and will be parsed by a UDF.
    """
    symbol: str
    timestamp: str
    profile: str
    peers: str
    income_annual: str
    balance_annual: str
    cashflow_annual: str
    ratios_ttm: str
    growth_annual: str
    scores: str
    grades_consensus: str
    price_target_consensus: str
    dividends: str
    splits: str
    insider_trades: str
    executives: str
    news: str
    sec_filings: str
    web_intelligence: str
    sent_at: str


@pw.udf
def parse_json(json_str: str) -> pw.Json:
    """Parse JSON string to Pathway Json object."""
    try:
        return pw.Json(json.loads(json_str))
    except:
        return pw.Json({})


def get_fundamental_table():
    """
    Get fundamental data table from Kafka.
    
    Returns:
        pw.Table: Fundamental data stream table.
    """
    print("📡 LIVE MODE: Consuming from Kafka topic 'fundamental-data'")
    fundamental_consumer = FundamentalDataConsumer()
    return fundamental_consumer.consume()

def main():
    print("=" * 70)
    print("Pathway Fundamental Analysis System (Redis-Backed Architecture)")
    print("=" * 70)
    print("📡 MODE: LIVE (using Kafka streaming)")

    # Ensure reports directory exists
    reports_directory = "/app/reports/fundamental"
    os.makedirs(reports_directory, exist_ok=True)
    print(f"📁 Reports directory ready: {reports_directory}")

    # Get fundamental data table from Kafka
    fundamental_table = get_fundamental_table()
    
    # Process fundamental data
    updated_fundamental_reports = process_fundamental_stream(
        fundamental_table, reports_directory=reports_directory
    )

    # NOTE: Fundamental reports are written to Redis directly by fundamental_agent.py via save_report_to_redis()
    # This also publishes WebSocket events. No observer needed to avoid race conditions.
    print("📤 Fundamental reports handled by agent")

    # Optional: Write to CSV for logging
    output_path = os.path.join(reports_directory, "fundamental_reports_stream.csv")
    pw.io.csv.write(updated_fundamental_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")

    print("\n✅ Fundamental pipeline with redis-backed architecture initialized. Starting stream processing...")
    
    # Enable persistence for state recovery
    persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")
    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=60000
        ),
        monitoring_level=pw.MonitoringLevel.NONE
    )

if __name__ == "__main__":
    load_dotenv()
    main()