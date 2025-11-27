import pathway as pw
import os
import logging
from dotenv import load_dotenv
from consumers.sentiment_consumer import SentimentConsumer
from agents.sentiment_agent import process_sentiment_stream
try:  # Allow running as `python pathway/main_sentiment.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

# Reduce LiteLLM logging verbosity
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

def main():
    print("=" * 70)
    print("Pathway Sentiment Analysis System (Cluster-Based Architecture)")
    print("=" * 70)
    print("Pipeline: Kafka → Clustering → Summaries → Reports → Redis")
    print("=" * 70)

    # Initialize consumer
    sentiment_consumer = SentimentConsumer()
    sentiment_table = sentiment_consumer.consume_flattened()

    # Process sentiment data with clustering pipeline
    reports_directory = os.path.join(os.path.dirname(__file__), "reports/sentiment")
    
    print("\n📊 Processing Steps:")
    print("  1️⃣  Assign posts to clusters (per-symbol)")
    print("  2️⃣  Generate LLM summaries for each cluster")
    print("  3️⃣  Create reports from cluster summaries")
    print("  4️⃣  Stream to Redis cache")
    print("  5️⃣  Export to visualization pipeline")
    
    updated_sentiment_reports, cluster_viz_table = process_sentiment_stream(
        sentiment_table, reports_directory=reports_directory
    )

    # Stream updates to Redis cache via pw.io.python observer
    sentiment_observer = get_report_observer("sentiment")
    pw.io.python.write(
        updated_sentiment_reports,
        sentiment_observer,
        name="sentiment_reports_stream",
    )
    print("\n📤 Streaming cluster-based sentiment updates to Redis cache")

    # Optional: Write to CSV
    output_path = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(updated_sentiment_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")
    
    # Export cluster visualization data to JSON for dashboard
    viz_directory = os.path.join(reports_directory, "visualizations")
    os.makedirs(viz_directory, exist_ok=True)    
    viz_output = os.path.join(viz_directory, "clusters_data.json")
    pw.io.jsonlines.write(cluster_viz_table, viz_output)
    print(f"📊 Streaming cluster visualizations to: {viz_output}")
    
    # Also stream cluster data to Redis for real-time visualization access
    cluster_observer = get_report_observer("clusters")
    pw.io.python.write(
        cluster_viz_table,
        cluster_observer,
        name="cluster_viz_stream",
    )
    print(f"📡 Streaming cluster data to Redis cache (key prefix: 'clusters:')")

    print("\n✅ Cluster-based sentiment pipeline initialized. Starting stream processing...")
    print("=" * 70)
    
    # Enable Pathway persistence for cluster state
    persistence_path = os.path.join(os.path.dirname(__file__), "sentiment_cluster_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")
    
    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=60000  # Snapshot every 60 seconds
        )
    )

if __name__ == "__main__":
    load_dotenv()
    main()
