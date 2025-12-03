import pathway as pw
import os
import logging
from dotenv import load_dotenv
from consumers.sentiment_consumer import SentimentConsumer
from agents.sentiment_clustering import process_sentiment_clustering
from agents.sentiment_reports import process_sentiment_reports
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
    reports_directory = "/app/reports/sentiment"
    clusters_directory = os.path.join(reports_directory, "clusters")
    
    print("\n📊 Processing Steps:")
    print("  1️⃣  Assign posts to clusters (per-symbol)")
    print("  2️⃣  Calculate VADER sentiment scores")
    print("  3️⃣  Apply time-based sentiment decay")
    print("  4️⃣  Stream to Redis cache")
    print("  5️⃣  Export to visualization pipeline")
    print("  6️⃣  Trigger BullBear alerts if sentiment outside range")
    
    # Phase 1: Fast clustering pipeline
    sentiment_scores_table, cluster_viz_table = process_sentiment_clustering(
        sentiment_table, clusters_directory=clusters_directory
    )
    
    # === SENTIMENT ALERT SYSTEM ===
    # Alerts are triggered inside _save_report_and_alert UDF when reports are saved
    alert_min = float(os.getenv("SENTIMENT_ALERT_MIN", "-0.5"))
    alert_max = float(os.getenv("SENTIMENT_ALERT_MAX", "0.5"))
    alerts_enabled = os.getenv("SENTIMENT_ALERT_ENABLED", "true").lower() == "true"
    alert_cooldown = int(os.getenv("SENTIMENT_ALERT_COOLDOWN", "300"))
    bullbear_url = os.getenv("BULLBEAR_API_URL", "http://localhost:8000")
    
    if alerts_enabled:
        print(f"\n🔔 Sentiment alerts ENABLED (triggered when reports are saved):")
        print(f"   Range: [{alert_min}, {alert_max}] (outside triggers BullBear debate)")
        print(f"   Cooldown: {alert_cooldown}s per symbol")
        print(f"   API: {bullbear_url}/debate/{{symbol}}")
    else:
        print("\n🔕 Sentiment alerts DISABLED (set SENTIMENT_ALERT_ENABLED=true to enable)")

    # Stream updates to Redis cache via pw.io.python observer
    sentiment_observer = get_report_observer("sentiment")
    pw.io.python.write(
        sentiment_scores_table,
        sentiment_observer,
        name="sentiment_scores_stream",
    )
    print("\n📤 Streaming cluster-based sentiment scores to Redis cache")
    
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
    persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
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