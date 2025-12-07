"""
PHASE 1: Sentiment Clustering Main
==================================
Fast pipeline for sentiment clustering and scoring.

Runs independently from report generation.
Outputs: 
- JSON files: {CLUSTERS_OUTPUT_DIR}/{symbol}_clusters.json
- Redis key: sentiment_clusters:{symbol} (full cluster data)
- Redis hash: clusters:all (individual clusters for aggregated endpoint)
"""

import pathway as pw
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Reduce logging verbosity
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# Schema for demo mode CSV replay (matches consume_flattened output)
class SentimentDataSchema(pw.Schema):
    """Schema for sentiment data stream (used in demo mode).
    
    Matches the output of SentimentConsumer.consume_flattened().
    """
    symbol: str
    received_at: str
    post_id: str
    ticker_symbol: str
    company_name: str
    subreddit: str
    post_title: str
    post_content: str
    post_comments: str
    sentiment_post_title: float
    sentiment_post_content: float
    sentiment_comments: float
    post_url: str
    num_comments: int
    score: int
    created_utc: str
    match_type: str
    post_timestamp: str
    sentiment_type: str
    related_to: str
    sent_at: str


def get_sentiment_table(use_dummy: bool):
    """
    Get sentiment data table from either Kafka or demo CSV.
    
    Args:
        use_dummy: If True, use pw.demo.replay_csv() with demo data.
                   If False, use SentimentConsumer (Kafka).
    
    Returns:
        pw.Table: Sentiment data stream table (flattened format).
    """
    if use_dummy:
        demo_data_dir = os.getenv("DEMO_DATA_DIR", "/app/streaming/data/demo_data")
        input_rate = float(os.getenv("SENTIMENT_INPUT_RATE", "0.4"))  # rows per second (2.5min = 0.4 rows/sec)
        
        csv_file = Path(demo_data_dir) / "sentiment_data.csv"
        
        if not csv_file.exists():
            raise FileNotFoundError(
                f"Demo data file not found: {csv_file}\n"
                f"Ensure sentiment_data.csv exists in {demo_data_dir}"
            )
        
        print(f"🧪 DUMMY MODE: Replaying from {csv_file} at {input_rate} rows/sec (2.5min interval)")
        return pw.demo.replay_csv(
            str(csv_file),
            schema=SentimentDataSchema,
            input_rate=input_rate
        )
    else:
        print("📡 LIVE MODE: Consuming from Kafka topic 'sentiment-data'")
        from consumers.sentiment_consumer import SentimentConsumer
        sentiment_consumer = SentimentConsumer()
        return sentiment_consumer.consume_flattened()


def main():
    print("=" * 70)
    print("PHASE 1: Sentiment Clustering Pipeline (FAST)")
    print("=" * 70)

    # Check for dummy mode
    use_dummy = os.getenv("USE_DUMMY", "false").lower() == "true"
    if use_dummy:
        print("🧪 MODE: DUMMY (using demo CSV data)")
        print("Pipeline: CSV → Embedding → Clustering → Sentiment → File + Redis")
    else:
        print("📡 MODE: LIVE (using Kafka streaming)")
        print("Pipeline: Kafka → Embedding → Clustering → Sentiment → File + Redis")
    print("=" * 70)

    # Import here to avoid circular imports
    from agents.sentiment_clustering import process_sentiment_clustering
    try:
        from redis_cache import get_report_observer
    except ImportError:
        from .redis_cache import get_report_observer

    # Get sentiment data table (either from Kafka or demo CSV)
    sentiment_table = get_sentiment_table(use_dummy)

    # Clusters output directory
    clusters_directory = os.getenv("SENTIMENT_CLUSTERS_DIR", "/app/reports/sentiment/clusters")
    os.makedirs(clusters_directory, exist_ok=True)
    
    print(f"\n📊 Phase 1 Steps:")
    print(f"  1️⃣  Consume posts from Kafka")
    print(f"  2️⃣  Generate embeddings")
    print(f"  3️⃣  Cluster posts (centroid-based)")
    print(f"  4️⃣  Calculate VADER sentiment with decay")
    print(f"  5️⃣  Save clusters to: {clusters_directory}")
    print(f"  6️⃣  Stream to Redis for fast API access")
    
    # Process clustering - returns clusters table with sentiment scores
    clusters_table = process_sentiment_clustering(
        sentiment_table, 
        clusters_directory=clusters_directory
    )
    
    # Stream cluster data to Redis (includes overall sentiment score)
    clusters_observer = get_report_observer("sentiment_clusters")
    pw.io.python.write(
        clusters_table,
        clusters_observer,
        name="clusters_stream",
    )
    print(f"\n📦 Streaming cluster data to Redis (key: sentiment_clusters:{{symbol}})")
    
    # Write clusters to JSON lines for debugging (outside clusters directory to avoid Phase 2 parsing it)
    debug_dir = "/app/reports/sentiment/debug"
    os.makedirs(debug_dir, exist_ok=True)
    clusters_jsonl = os.path.join(debug_dir, "clusters_stream.jsonl")
    pw.io.jsonlines.write(clusters_table, clusters_jsonl)
    print(f"📝 Writing cluster stream to: {clusters_jsonl}")

    print(f"\n✅ Phase 1 initialized. Starting fast clustering pipeline...")
    print("=" * 70)
    
    # Run with or without persistence based on mode
    if use_dummy:
        # Demo mode: no persistence (replay from scratch each time)
        print("🔄 Demo mode: Running without persistence")
        pw.run(monitoring_level=pw.MonitoringLevel.NONE)
    else:
        # Live mode: enable persistence for state recovery
        persistence_path = os.path.join(os.path.dirname(__file__), "sentiment_phase1_state")
        os.makedirs(persistence_path, exist_ok=True)
        print(f"💾 Persistence enabled at: {persistence_path}")
        pw.run(
            persistence_config=pw.persistence.Config.simple_config(
                pw.persistence.Backend.filesystem(persistence_path),
                snapshot_interval_ms=15000
            ),
            monitoring_level=pw.MonitoringLevel.NONE
        )


if __name__ == "__main__":
    main()
