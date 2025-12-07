import pathway as pw
import os
from pathlib import Path
from dotenv import load_dotenv
from consumers.news_consumer import NewsConsumer
from agents.news_agent import process_news_stream


# Schema for demo mode CSV replay
class NewsDataSchema(pw.Schema):
    """Schema for news data stream (used in demo mode)."""
    symbol: str
    news_type: str
    timestamp: str
    title: str
    description: str
    source: str
    url: str
    published_at: str
    data_source: str
    related_to: str
    sent_at: str


def get_news_table(use_dummy: bool):
    """
    Get news data table from either Kafka or demo CSV.
    
    Args:
        use_dummy: If True, use pw.demo.replay_csv() with demo data.
                   If False, use NewsConsumer (Kafka).
    
    Returns:
        pw.Table: News data stream table.
    """
    if use_dummy:
        demo_data_dir = os.getenv("DEMO_DATA_DIR", "/app/streaming/data/demo_data")
        input_rate = float(os.getenv("NEWS_INPUT_RATE", "0.4"))  # rows per second (2.5min = 0.4 rows/sec)
        
        csv_file = Path(demo_data_dir) / "news_data.csv"
        
        if not csv_file.exists():
            raise FileNotFoundError(
                f"Demo data file not found: {csv_file}\n"
                f"Ensure news_data.csv exists in {demo_data_dir}"
            )
        
        print(f"🧪 DUMMY MODE: Replaying from {csv_file} at {input_rate} rows/sec (2.5min interval)")
        return pw.demo.replay_csv(
            str(csv_file),
            schema=NewsDataSchema,
            input_rate=input_rate
        )
    else:
        print("📡 LIVE MODE: Consuming from Kafka topic 'news-data'")
        news_consumer = NewsConsumer()
        return news_consumer.consume()

def main():
    print("=" * 70)
    print("Pathway News Analysis System (Story Clustering Architecture)")
    print("=" * 70)

    # Check for dummy mode (USE_DUMMY_NEWS takes priority over USE_DUMMY)
    use_dummy_news = os.getenv("USE_DUMMY_NEWS")
    if use_dummy_news is not None:
        use_dummy = use_dummy_news.lower() == "true"
    else:
        use_dummy = os.getenv("USE_DUMMY", "false").lower() == "true"
    
    if use_dummy:
        print("🧪 MODE: DUMMY (using demo CSV data)")
    else:
        print("📡 MODE: LIVE (using Kafka streaming)")

    print("Features:")
    print("  • Working memory of story clusters with dynamic headlines")
    print("  • Incremental cluster management using Pathway stateful reducers")
    print("  • Vector embeddings for semantic similarity matching")
    print("  • Reports update as stories develop and connect")
    print("  • News articles stored in knowledge base as JSONL")
    print("=" * 70)

    # Get news data table (either from Kafka or demo CSV)
    news_table = get_news_table(use_dummy)

    # Ensure directories exist
    reports_directory = "/app/reports/news"
    knowledge_base_dir = "/app/knowledge_base"
    os.makedirs(reports_directory, exist_ok=True)
    os.makedirs(knowledge_base_dir, exist_ok=True)
    print(f"📁 Directories ready: {reports_directory}, {knowledge_base_dir}")

    # Process news data and generate AI reports with story clustering
    updated_news_reports, cluster_viz_table = process_news_stream(
        news_table, 
        reports_directory=reports_directory,
        knowledge_base_dir=knowledge_base_dir
    )

    # NOTE: News reports are written to Redis directly by news_agent.py via save_report_to_redis()
    # This also publishes WebSocket events. No observer needed to avoid race conditions.

    # Stream news clusters to Redis for API access (bullish/bearish/neutral endpoint)
    try:
        from redis_cache import get_report_observer
    except ImportError:
        from .redis_cache import get_report_observer
    news_clusters_observer = get_report_observer("news_clusters")
    pw.io.python.write(
        cluster_viz_table,
        news_clusters_observer,
        name="news_clusters_stream",
    )
    print("📤 Streaming news clusters to Redis cache for API")

    # Optional: Write reports to CSV
    output_path = os.path.join(reports_directory, "reports_stream.csv")
    pw.io.csv.write(updated_news_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")

    # Optional: Write cluster visualization data to CSV
    clusters_output_path = os.path.join(reports_directory, "story_clusters.csv")
    pw.io.csv.write(cluster_viz_table, clusters_output_path)
    print(f"📊 Writing story clusters to CSV: {clusters_output_path}")
    
    print(f"📚 News articles stored in knowledge base: {knowledge_base_dir}/<symbol>/jsons/news_articles.jsonl")

    print("\n✅ News pipeline with story clustering initialized. Starting stream processing...")
    
    # Run with or without persistence based on mode
    if use_dummy:
        # Demo mode: no persistence (replay from scratch each time)
        print("🔄 Demo mode: Running without persistence")
        pw.run(monitoring_level=pw.MonitoringLevel.NONE)
    else:
        # Live mode: enable persistence for state recovery
        persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
        os.makedirs(persistence_path, exist_ok=True)
        print(f"💾 Persistence enabled at: {persistence_path}")
        pw.run(
            persistence_config=pw.persistence.Config.simple_config(
                pw.persistence.Backend.filesystem(persistence_path),
                snapshot_interval_ms=30000
            ),
            monitoring_level=pw.MonitoringLevel.NONE
        )

if __name__ == "__main__":
    load_dotenv()
    main()
