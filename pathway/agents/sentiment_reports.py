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
import litellm
from typing import Optional

# Import Redis and PostgreSQL save functions
try:
    from redis_cache import save_report_to_postgres, save_report_to_redis
    from event_publisher import publish_agent_status, publish_report
except ImportError:
    from .redis_cache import save_report_to_postgres, save_report_to_redis
    from .event_publisher import publish_agent_status, publish_report


load_dotenv()

# Default clusters input directory (same as Phase 1 output)
CLUSTERS_INPUT_DIR = os.getenv("SENTIMENT_CLUSTERS_DIR", "/app/reports/sentiment/clusters")

# Report generation interval in seconds (default: 5 minutes)
# Reports will only be generated at most once per interval per symbol
REPORT_GENERATION_INTERVAL = int(os.getenv("REPORT_GENERATION_INTERVAL", "300"))

# Track last report generation time per symbol
_last_report_time: dict[str, float] = {}

# Cache LLM-generated cluster summaries by (symbol, cluster_id) -> (summary, post_count)
# Regenerates when cluster post count changes (any new content added)
_cluster_summary_cache: dict[tuple[str, str], tuple[str, int]] = {}


def _prune_summary_cache():
    """Prune is no longer needed since we update on content change, not TTL."""
    pass  # Kept for compatibility


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
        self.model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not self.model_name.startswith('openrouter/') and not self.model_name.startswith('openai/'):
            self.model_name = f'openrouter/{self.model_name}'
        
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.has_valid_api_key = bool(self.api_key)
        
        if self.has_valid_api_key:
            print(f"✅ Report generator initialized with model: {self.model_name}")
        else:
            print("⚠️ No API key - reports will use fallback format")

    def call_llm_sync(self, messages: list) -> str:
        """Direct synchronous LLM call for use inside reducers."""
        if not self.has_valid_api_key:
            return ""
        try:
            response = litellm.completion(
                model=self.model_name,
                messages=messages,
                api_key=self.api_key,
                api_base="https://openrouter.ai/api/v1",
                temperature=0.3,
                max_tokens=1500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM call error: {e}")
            return ""

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
        
        # Count sentiment types in cluster
        type_counts = {}
        for p in posts:
            if isinstance(p, dict):
                st = p.get('sentiment_type', 'company')
                type_counts[st] = type_counts.get(st, 0) + 1
        
        type_info = ", ".join([f"{count} {stype}" for stype, count in type_counts.items()]) if type_counts else "company posts"
        
        prompt = f"""Write a SHORT headline (max 10-12 words) for this discussion cluster about {company} ({symbol}).

Posts ({len(posts)} total, sentiment: {sentiment_label}):
{post_texts}

Rules:
- Write ONLY the headline, nothing else
- Max 10-12 words, like a news headline
- Capture the main theme/topic
- Be specific about what's being discussed
- Examples: "Investors bullish on Q3 earnings beat" or "Concerns over supply chain delays"

Headline:"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.call_llm_sync(messages)
            # Strip any extra whitespace and limit length
            headline = response.strip() if response else cluster_data.get('summary', '')
            return headline[:150]  # Hard limit to prevent runaway responses
        except Exception as e:
            return cluster_data.get('summary', f"Discussion about {company}")

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
        
        # Analyze sentiment type distribution across all clusters
        total_company = sum(c.get('company_count', c.get('count', 0)) for c in clusters)
        total_sector = sum(c.get('sector_count', 0) for c in clusters)
        total_global = sum(c.get('global_count', 0) for c in clusters)
        
        type_breakdown = f"""Sentiment Sources:
- Company-specific mentions: {total_company} posts
- Sector/Peer influences: {total_sector} posts (competitors, industry trends)
- Global/Macro factors: {total_global} posts (Fed, market-wide, economic)""" if (total_sector > 0 or total_global > 0) else ""
        
        prompt = f"""Generate a sentiment analysis report for {company} ({symbol}).

OVERALL SCORE: {sentiment_label} ({overall_sentiment:.3f})

{type_breakdown}

Active Discussion Clusters:
{cluster_summaries}

GENERATE REPORT:

## SENTIMENT SNAPSHOT
2-3 sentences: Current retail mood, confidence level, any notable shifts

## DOMINANT NARRATIVES
Top 3 themes driving discussion (bullish thesis, bear case, catalyst speculation, etc.)

## RISK SIGNALS
Red flags from crowd chatter: Excessive euphoria? Panic selling mentions? Bag-holder capitulation?

## CONTRARIAN READ
Is crowd sentiment a signal or noise? Historically, extreme readings = reversal warning.

Create a professional report with:
1. Executive summary of sentiment
2. Key themes from clusters (distinguish between company-specific vs sector/macro influences)
3. Notable trends or concerns
4. How sector peers and macro factors are affecting sentiment (if applicable)
5. Brief outlook

250 words max. Trading-relevant insights only."""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.call_llm_sync(messages)
            return response if response else ""
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
        """Generate LLM report from cluster data."""
        
        if cluster_count == 0:
            return ""
        
        # Rate limiting DISABLED - generate report on every update
        print(f"🔄 [{symbol}] Generating report (rate limiting disabled)")
        
        try:
            clusters = clusters_json.as_list() if clusters_json else []
        except Exception:
            clusters = []
        
        if not clusters:
            return ""
        
        # Publish RUNNING status at START of processing (before LLM call)
        try:
            room_id = f"symbol:{symbol}"
            publish_agent_status(room_id, "Sentiment Report Agent", "RUNNING")
        except Exception as e:
            print(f"⚠️ [{symbol}] Failed to publish Sentiment Report Agent status: {e}")
        
        # Prune expired summaries from cache
        _prune_summary_cache()
        
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
            
            # Check if we have a cached LLM summary for this cluster
            cluster_id = str(cluster_dict.get('cluster_id', 0))
            cache_key = (symbol, cluster_id)
            current_count = int(cluster_dict.get('count', 0))
            
            if cache_key in _cluster_summary_cache:
                cached_summary, cached_count = _cluster_summary_cache[cache_key]
                
                # Use cached only if post count hasn't changed
                if current_count == cached_count:
                    cluster_dict['summary'] = cached_summary
                    processed_clusters.append(cluster_dict)
                    continue
            
            # Generate new LLM summary (new cluster or count changed)
            new_summary = report_generator._generate_cluster_summary(
                symbol, 
                cluster_dict.get('cluster_id', 0), 
                cluster_dict
            )
            _cluster_summary_cache[cache_key] = (new_summary, current_count)
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
            # Save report to file
            report_path = report_generator._get_report_path(symbol)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(new_report)
            print(f"📝 [{symbol}] Generated sentiment report")
            
            # Determine sentiment direction
            sentiment_direction = "NEUTRAL"
            if overall_sentiment > 0.1:
                sentiment_direction = "BULLISH"
            elif overall_sentiment < -0.1:
                sentiment_direction = "BEARISH"
            
            # Publish report and COMPLETED status
            try:
                room_id = f"symbol:{symbol}"
                publish_report(room_id, "Sentiment Report Agent", {
                    "symbol": symbol,
                    "report_type": "sentiment_report",
                    "overall_sentiment": round(overall_sentiment, 3),
                    "sentiment_direction": sentiment_direction,
                    "cluster_count": len(processed_clusters),
                    "report_content": new_report
                })
                publish_agent_status(room_id, "Sentiment Report Agent", "COMPLETED")
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to publish Sentiment Report Agent events: {e}")
            
            # Save to Redis for API caching (this is what report_fetch_api reads!)
            try:
                save_report_to_redis(symbol, "sentiment", new_report)
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to cache sentiment report to Redis: {e}")
            
            # Save to PostgreSQL for historical storage
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
            
            # Publish FAILED status
            try:
                room_id = f"symbol:{symbol}"
                publish_agent_status(room_id, "Sentiment Report Agent", "FAILED")
            except:
                pass
        
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
