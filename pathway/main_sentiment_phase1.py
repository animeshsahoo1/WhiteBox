"""
PHASE 1: Sentiment Clustering Main
==================================
Fast pipeline for sentiment clustering and scoring.

Runs independently from report generation.
Outputs: 
- Cluster files in /app/reports/sentiment/clusters/
- Redis: fast_sentiment:{symbol} (real-time scores)
- Redis: sentiment_clusters:{symbol} (cluster data)
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
    print("PHASE 1: Sentiment Clustering Pipeline (FAST)")
    print("=" * 70)
    print("Pipeline: Kafka → Embedding → Clustering → Sentiment → File + Redis")
    print("=" * 70)

    # Import here to avoid circular imports
    from consumers.sentiment_consumer import SentimentConsumer
    from agents.sentiment_clustering import process_sentiment_clustering
    try:
        from redis_cache import get_report_observer
    except ImportError:
        from .redis_cache import get_report_observer

    # Initialize consumer
    sentiment_consumer = SentimentConsumer()
    sentiment_table = sentiment_consumer.consume_flattened()

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
    sentiment_scores_table, clusters_api_table = process_sentiment_clustering(
        sentiment_table, 
        clusters_directory=clusters_directory
    )
    
    # Stream cluster data to Redis (includes overall sentiment score)
    clusters_observer = get_report_observer("sentiment_clusters")
    pw.io.python.write(
        clusters_api_table,
        clusters_observer,
        name="clusters_stream",
    )
    print(f"\n📦 Streaming cluster data to Redis (key: sentiment_clusters:{{symbol}})")
    
    # Write clusters to JSON lines for debugging (outside clusters directory to avoid Phase 2 parsing it)
    debug_dir = "/app/reports/sentiment/debug"
    os.makedirs(debug_dir, exist_ok=True)
    clusters_jsonl = os.path.join(debug_dir, "clusters_stream.jsonl")
    pw.io.jsonlines.write(clusters_api_table, clusters_jsonl)
    print(f"📝 Writing cluster stream to: {clusters_jsonl}")

    print(f"\n✅ Phase 1 initialized. Starting fast clustering pipeline...")
    print("=" * 70)
    
    # Enable persistence
    persistence_path = os.path.join(os.path.dirname(__file__), "sentiment_phase1_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")
    
    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=30000  # Snapshot every 30 seconds
        )
    )


if __name__ == "__main__":
    main()
