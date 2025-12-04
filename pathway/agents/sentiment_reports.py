"""
PHASE 2: Sentiment Report Generation Pipeline (SLOW)
=====================================================
This pipeline generates LLM-based reports from cluster files:
1. Watches cluster JSON files written by Phase 1
2. Rate-limits to avoid generating reports too frequently
3. Generates LLM summaries for each cluster
4. Creates comprehensive sentiment reports
5. Exposes reports via Redis API

Input: Cluster files from /app/reports/sentiment/clusters/{symbol}_clusters.json
Output: Reports in Redis cache: sentiment:{symbol}

This runs INDEPENDENTLY from clustering (Phase 1).
Report generation is rate-limited by REPORT_GENERATION_INTERVAL (default: 300s).
"""

import os
import pathway as pw
from pathway.xpacks.llm.llms import LiteLLMChat
from datetime import datetime, timezone
from dotenv import load_dotenv
import json
import time
from typing import Optional

# Import PostgreSQL save function
try:
    from redis_cache import save_report_to_postgres
except ImportError:
    from .redis_cache import save_report_to_postgres


load_dotenv()

# Default clusters input directory (same as Phase 1 output)
CLUSTERS_INPUT_DIR = os.getenv("SENTIMENT_CLUSTERS_DIR", "/app/reports/sentiment/clusters")

# Report generation interval in seconds (default: 5 minutes)
# Reports will only be generated at most once per interval per symbol
REPORT_GENERATION_INTERVAL = int(os.getenv("REPORT_GENERATION_INTERVAL", "300"))

# Track last report generation time per symbol
_last_report_time: dict[str, float] = {}


class SentimentReportGenerator:
    """Generates LLM-based sentiment reports from cluster data."""

    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory
        os.makedirs(reports_directory, exist_ok=True)

        try:
            self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}"))
        except json.JSONDecodeError:
            self.symbol_mapping = {}

        # Setup LLM
        model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not model_name.startswith('openrouter/') and not model_name.startswith('openai/'):
            model_name = f'openrouter/{model_name}'
        
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.has_valid_api_key = bool(api_key)
        
        if self.has_valid_api_key:
            self.llm = LiteLLMChat(
                model=model_name,
                api_key=api_key,
                api_base="https://openrouter.ai/api/v1",
                temperature=0.3,
                max_tokens=1500
            )
            print(f"✅ Report generator initialized with model: {model_name}")
        else:
            self.llm = None
            print("⚠️ No API key - reports will use fallback format")

    def _classify_sentiment(self, score: float) -> str:
        if score >= 0.5:
            return "Strong Bullish 🟢"
        elif score >= 0.15:
            return "Bullish 📈"
        elif score > 0.05:
            return "Slightly Bullish ↗️"
        elif score > -0.05:
            return "Neutral ➡️"
        elif score > -0.15:
            return "Slightly Bearish ↘️"
        elif score > -0.5:
            return "Bearish 📉"
        else:
            return "Strong Bearish 🔴"

    def _generate_cluster_summary(self, symbol: str, cluster_id: int, cluster_data: dict) -> str:
        """Generate LLM summary for a cluster."""
        if not self.has_valid_api_key:
            return cluster_data.get('summary', f"Cluster {cluster_id}")
        
        posts = cluster_data.get('posts', [])
        avg_sentiment = cluster_data.get('avg_sentiment', 0.0)
        
        sample_posts = posts[:5]
        post_texts = "\n".join([
            f"- {p.get('text', '')[:200]}" 
            for p in sample_posts if isinstance(p, dict)
        ])
        
        company = self.symbol_mapping.get(symbol, symbol)
        sentiment_label = self._classify_sentiment(avg_sentiment)
        
        prompt = f"""Summarize this discussion cluster about {company} ({symbol}) in 1-2 sentences.

Posts ({len(posts)} total, sentiment: {sentiment_label}):
{post_texts}

Write a concise summary of the main theme/topic being discussed."""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat_single(messages)
            return response.strip() if response else cluster_data.get('summary', '')
        except Exception as e:
            return cluster_data.get('summary', f"Discussion cluster about {company}")

    def _generate_full_report(self, symbol: str, clusters: list, overall_sentiment: float, current_report: str = "") -> str:
        """Generate full sentiment report from clusters."""
        company = self.symbol_mapping.get(symbol, symbol)
        sentiment_label = self._classify_sentiment(overall_sentiment)
        
        if not self.has_valid_api_key or not clusters:
            # Fallback report
            cluster_text = "\n".join([
                f"- **Cluster {c['cluster_id']}** ({c['count']} posts, sentiment: {c['avg_sentiment']:.2f}): {c.get('summary', '')[:100]}..."
                for c in clusters
            ]) if clusters else "No active clusters"
            
            return f"""# {company} ({symbol}) - Sentiment Report

## Overall Sentiment: {sentiment_label} ({overall_sentiment:.3f})

## Active Discussion Clusters
{cluster_text}

*Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*"""

        # LLM-generated report
        cluster_summaries = "\n".join([
            f"Cluster {c['cluster_id']} ({c['count']} posts, sentiment: {c['avg_sentiment']:.2f}): {c.get('summary', '')}"
            for c in clusters
        ])
        
        prompt = f"""Generate a sentiment analysis report for {company} ({symbol}).

Overall Sentiment: {sentiment_label} ({overall_sentiment:.3f})

Active Discussion Clusters:
{cluster_summaries}

Previous Report (for context):
{current_report[:500] if current_report else 'None'}

Create a professional report with:
1. Executive summary of sentiment
2. Key themes from clusters
3. Notable trends or concerns
4. Brief outlook

Keep it concise (300-400 words)."""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat_single(messages)
            return response.strip() if response else ""
        except Exception as e:
            print(f"Error generating report for {symbol}: {e}")
            return ""

    def _get_report_path(self, symbol: str) -> str:
        return os.path.join(self.reports_directory, f"{symbol}_sentiment.md")

    def _load_report(self, symbol: str) -> str:
        path = self._get_report_path(symbol)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""


def process_sentiment_reports(
    clusters_directory: str = CLUSTERS_INPUT_DIR,
    reports_directory: str = "/app/reports/sentiment"
) -> pw.Table:
    """
    PHASE 2: Report generation pipeline.
    
    Watches cluster files and generates LLM reports.
    
    Args:
        clusters_directory: Directory containing cluster JSON files from Phase 1
        reports_directory: Directory to save generated reports
        
    Returns:
        Table with generated reports
    """
    os.makedirs(clusters_directory, exist_ok=True)
    os.makedirs(reports_directory, exist_ok=True)
    
    report_generator = SentimentReportGenerator(reports_directory)
    
    # =========================================================================
    # Read cluster files from Phase 1 output directory
    # =========================================================================
    print(f"📁 Watching cluster files in: {clusters_directory}")
    
    # Schema for cluster files
    class ClusterFileSchema(pw.Schema):
        symbol: str
        overall_sentiment: float
        cluster_count: int
        total_posts: int
        clusters: pw.Json
        timestamp: str
    
    # Read JSON files from the clusters directory
    clusters_table = pw.io.fs.read(
        clusters_directory,
        format="json",
        schema=ClusterFileSchema,
        mode="streaming",
        with_metadata=True
    )
    
    # =========================================================================
    # Generate reports from cluster data (rate-limited)
    # =========================================================================
    
    # Note: Alerts are now triggered in Phase 1 (sentiment_clustering.py)
    # based on real-time sentiment scores, not report generation.
    
    @pw.udf
    def generate_report_from_clusters(
        symbol: str, 
        overall_sentiment: float, 
        clusters_json: pw.Json,
        cluster_count: int
    ) -> str:
        """Generate LLM report from cluster data (rate-limited)."""
        global _last_report_time
        
        if cluster_count == 0:
            return ""
        
        # Rate limiting: check if enough time has passed since last report
        current_time = time.time()
        last_time = _last_report_time.get(symbol, 0)
        elapsed = current_time - last_time
        
        if elapsed < REPORT_GENERATION_INTERVAL:
            # Not enough time has passed, skip this update
            remaining = REPORT_GENERATION_INTERVAL - elapsed
            print(f"⏳ [{symbol}] Rate limited - next report in {remaining:.0f}s")
            return ""
        
        try:
            clusters = clusters_json.as_list() if clusters_json else []
        except Exception:
            clusters = []
        
        if not clusters:
            return ""
        
        # Update last report time BEFORE generating (to prevent concurrent calls)
        _last_report_time[symbol] = current_time
        print(f"🔄 [{symbol}] Generating report (interval: {REPORT_GENERATION_INTERVAL}s)")
        
        # First, generate summaries for clusters that need them
        processed_clusters = []
        for cluster in clusters:
            if isinstance(cluster, dict):
                cluster_dict = cluster
            else:
                try:
                    cluster_dict = dict(cluster)
                except:
                    continue
            
            # Generate summary if it's just the initial text
            summary = cluster_dict.get('summary', '')
            if len(summary) > 100 or not summary:  # Likely needs regeneration
                new_summary = report_generator._generate_cluster_summary(
                    symbol, 
                    cluster_dict.get('cluster_id', 0), 
                    cluster_dict
                )
                cluster_dict['summary'] = new_summary
            
            processed_clusters.append(cluster_dict)
        
        # Generate full report
        current_report = report_generator._load_report(symbol)
        new_report = report_generator._generate_full_report(
            symbol, 
            processed_clusters, 
            overall_sentiment,
            current_report
        )
        
        if new_report:
            # Save report
            report_path = report_generator._get_report_path(symbol)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(new_report)
            print(f"📝 [{symbol}] Generated sentiment report")
            
            # 2. Save to PostgreSQL for historical storage
            try:
                entry = {
                    "symbol": symbol,
                    "report_type": "sentiment",
                    "content": new_report,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "cluster_data": json.dumps(processed_clusters),
                }
                save_report_to_postgres(symbol, "sentiment", entry)
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to save to PostgreSQL: {e}")

        else:
            # Reset time if generation failed so we retry sooner
            _last_report_time[symbol] = last_time
        
        return new_report
    
    # Generate reports
    reports_table = clusters_table.select(
        symbol=pw.this.symbol,
        response=generate_report_from_clusters(
            pw.this.symbol,
            pw.this.overall_sentiment,
            pw.this.clusters,
            pw.this.cluster_count
        )
    ).filter(pw.this.response != "")
    
    return reports_table
