"""
PHASE 2: Sentiment Report Generation Main
=========================================
Slow pipeline for LLM-based report generation.

Reads cluster files from Phase 1 and generates reports.
Outputs:
- Report files in /app/reports/sentiment/
- Redis: sentiment:{symbol} (full reports)
"""

import pathway as pw
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Reduce logging verbosity
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    print("=" * 70)
    print("PHASE 2: Sentiment Report Generation Pipeline (SLOW)")
    print("=" * 70)
    print("Pipeline: Cluster Files → LLM Summaries → Reports → Redis")
    print("=" * 70)

    # Import here to avoid circular imports
    from agents.sentiment_reports import process_sentiment_reports
    try:
        from redis_cache import get_report_observer
    except ImportError:
        from .redis_cache import get_report_observer

    # Directories
    clusters_directory = os.getenv("SENTIMENT_CLUSTERS_DIR", "/app/reports/sentiment/clusters")
    reports_directory = "/app/reports/sentiment"
    
    print(f"\n📊 Phase 2 Steps:")
    print(f"  1️⃣  Watch cluster files in: {clusters_directory}")
    print(f"  2️⃣  Generate LLM summaries for clusters")
    print(f"  3️⃣  Create comprehensive reports")
    print(f"  4️⃣  Save reports to: {reports_directory}")
    print(f"  5️⃣  Stream to Redis for API access")
    print(f"  6️⃣  Trigger BullBear alerts if needed")
    
    # Process reports
    reports_table = process_sentiment_reports(
        clusters_directory=clusters_directory,
        reports_directory=reports_directory
    )
    
    # Stream reports to Redis
    reports_observer = get_report_observer("sentiment")
    pw.io.python.write(
        reports_table,
        reports_observer,
        name="sentiment_reports_stream",
    )
    print(f"\n📤 Streaming reports to Redis (key: sentiment:{{symbol}})")
    
    # Also write reports to CSV for backup
    reports_csv = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(reports_table, reports_csv)
    print(f"📝 Writing reports stream to: {reports_csv}")

    print(f"\n✅ Phase 2 initialized. Watching for cluster updates...")
    print("=" * 70)
    
    # Enable persistence (separate from Phase 1)
    persistence_path = os.path.join(os.path.dirname(__file__), "sentiment_phase2_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")
    
    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=60000  # Snapshot every 60 seconds
        )
    )


if __name__ == "__main__":
    main()
