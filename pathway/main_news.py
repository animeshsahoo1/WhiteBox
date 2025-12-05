import pathway as pw
import os
from dotenv import load_dotenv
from consumers.news_consumer import NewsConsumer
from agents.news_agent import process_news_stream
try:  # Allow running as `python pathway/main_news.py` or as module
    from .redis_cache import get_report_observer
except ImportError:  # pragma: no cover - fallback for script execution
    from redis_cache import get_report_observer

def main():
    print("=" * 70)
    print("Pathway News Analysis System (Story Clustering Architecture)")
    print("=" * 70)
    print("Features:")
    print("  • Working memory of story clusters with dynamic headlines")
    print("  • Incremental cluster management using Pathway stateful reducers")
    print("  • Vector embeddings for semantic similarity matching")
    print("  • Reports update as stories develop and connect")
    print("  • News articles stored in knowledge base as JSONL")
    print("=" * 70)

    # Initialize consumer
    news_consumer = NewsConsumer()
    news_table = news_consumer.consume()

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

    # Stream updates to Redis cache via pw.io.python observer
    news_observer = get_report_observer("news")
    pw.io.python.write(
        updated_news_reports,
        news_observer,
        name="news_reports_stream",
    )
    print("📤 Streaming news updates to Redis cache via pw.io.python")

    # Stream news clusters to Redis for API access (bullish/bearish/neutral endpoint)
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

    # Enable Pathway persistence for news clustering state
    persistence_path = os.path.join(os.path.dirname(__file__), "pathway_state")
    os.makedirs(persistence_path, exist_ok=True)
    print(f"💾 Persistence enabled at: {persistence_path}")

    # Optional: Write cluster visualization data to CSV
    clusters_output_path = os.path.join(reports_directory, "story_clusters.csv")
    pw.io.csv.write(cluster_viz_table, clusters_output_path)
    print(f"📊 Writing story clusters to CSV: {clusters_output_path}")
    
    print(f"📚 News articles stored in knowledge base: {knowledge_base_dir}/<symbol>/jsons/news_articles.jsonl")

    print("\n✅ News pipeline with story clustering initialized. Starting stream processing...")
    pw.run(
        persistence_config=pw.persistence.Config.simple_config(
            pw.persistence.Backend.filesystem(persistence_path),
            snapshot_interval_ms=60000  # Snapshot every 60 seconds
        )
    )

if __name__ == "__main__":
    load_dotenv()
    main()
