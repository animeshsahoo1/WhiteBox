"""
PHASE 1: Sentiment Clustering Pipeline (FAST)
==============================================
This pipeline processes incoming sentiment data at high speed:
1. Consumes posts from Kafka
2. Clusters posts using centroid-based cosine similarity
3. Calculates VADER sentiment scores
4. Applies time-based decay to sentiment scores
5. Saves cluster data to JSON files (for Phase 2 to read)
6. Exposes real-time sentiment scores via Redis API

Output: 
- JSON files: {CLUSTERS_OUTPUT_DIR}/{symbol}_clusters.json
- Redis key: sentiment_clusters:{symbol} (full cluster data for /sentiment/clusters/{symbol} endpoint)
- Redis hash: clusters:all (individual clusters for /sentiment/clusters endpoint)

This runs INDEPENDENTLY from report generation (Phase 2).
"""

import os
import pathway as pw
from datetime import datetime, timezone
from dotenv import load_dotenv
import json
import numpy as np
from typing import Optional
import litellm
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Event publishing imports
try:
    from redis_cache import get_redis_client
    from event_publisher import publish_agent_status, publish_alert , publish_report
except ImportError:
    from .redis_cache import get_redis_client
    from .event_publisher import publish_agent_status, publish_alert , publish_report


load_dotenv()

# Initialize VADER sentiment analyzer
vader_analyzer = SentimentIntensityAnalyzer()

# =============================================================================
# CONFIGURATION
# =============================================================================
SIMILARITY_THRESHOLD = 0.65
MERGE_THRESHOLD = 0.80
CLUSTER_EXPIRY_HOURS = 48
MAX_POSTS_PER_CLUSTER = 50
EMBEDDING_DIMENSIONS = 1536
SENTIMENT_DECAY_HALF_LIFE = 1800  # 30 minutes

# Default clusters output directory
CLUSTERS_OUTPUT_DIR = os.getenv("SENTIMENT_CLUSTERS_DIR", "/app/reports/sentiment/clusters")

# Alert cooldowns (module-level to persist across UDF calls)
_sentiment_alert_cooldowns = {}

def trigger_sentiment_alert(symbol: str, overall_sentiment: float):
    """Trigger alert if sentiment crosses threshold (pure math, no LLM)."""
    
    alert_min = float(os.getenv("SENTIMENT_ALERT_MIN", "-0.3"))
    alert_max = float(os.getenv("SENTIMENT_ALERT_MAX", "0.3"))
    alerts_enabled = os.getenv("SENTIMENT_ALERT_ENABLED", "true").lower() == "true"
    alert_cooldown = int(os.getenv("SENTIMENT_ALERT_COOLDOWN", "300"))
    
    if not alerts_enabled:
        return
    
    # Check if sentiment crosses thresholds
    if overall_sentiment < alert_min or overall_sentiment > alert_max:
        now = datetime.now()
        last = _sentiment_alert_cooldowns.get(symbol)
        
        if last and (now - last).total_seconds() < alert_cooldown:
            return
        
        # Determine direction and severity
        if overall_sentiment < alert_min:
            direction = "bearish"
            severity = "critical" if overall_sentiment < -0.5 else "high"
        else:
            direction = "bullish"
            severity = "critical" if overall_sentiment > 0.5 else "high"
        
        reason = f"Extreme {direction} sentiment detected ({overall_sentiment:.3f})"
        print(f"🚨 [{symbol}] SENTIMENT ALERT: {reason}")
        
        try:
            publish_alert(
                symbol=symbol,
                alert_type="sentiment",
                reason=reason,
                severity=severity,
                trigger_debate=True
            )
            _sentiment_alert_cooldowns[symbol] = now
            print(f"✅ [{symbol}] Sentiment alert published at {now.isoformat()}")
        except Exception as e:
            print(f"⚠️ [{symbol}] Sentiment alert failed: {e}")


def get_embedding(text: str) -> list:
    """Generate embedding for text using OpenRouter"""
    try:
        response = litellm.embedding(
            model="openai/text-embedding-3-small",
            input=[text],
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1"
        )
        return response.data[0]['embedding']
    except Exception as e:
        return [0.0] * EMBEDDING_DIMENSIONS


def get_vader_sentiment(text: str) -> float:
    """Get sentiment score from VADER (-1 to 1 scale)"""
    try:
        scores = vader_analyzer.polarity_scores(text)
        return scores['compound']
    except Exception:
        return 0.0


def apply_sentiment_decay(sentiment: float, last_updated: str) -> float:
    """Apply exponential decay to sentiment score towards neutral (0)."""
    try:
        last_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        elapsed_seconds = (now - last_time).total_seconds()
        decay_factor = 0.5 ** (elapsed_seconds / SENTIMENT_DECAY_HALF_LIFE)
        return sentiment * decay_factor
    except Exception:
        return sentiment


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calculate cosine similarity between two vectors"""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    if norm_product == 0:
        return 0.0
    return float(np.dot(vec1_np, vec2_np) / norm_product)


def process_sentiment_clustering(
    sentiment_table: pw.Table,
    clusters_directory: str = CLUSTERS_OUTPUT_DIR
) -> pw.Table:
    """
    PHASE 1: Fast sentiment clustering pipeline.
    
    Args:
        sentiment_table: Input table with sentiment posts
        clusters_directory: Directory to save cluster JSON files
        
    Returns:
        pw.Table: Clusters table with symbol and clusters_json columns
    """
    os.makedirs(clusters_directory, exist_ok=True)
    
    # =========================================================================
    # STEP 1: Generate embeddings for clustering
    # =========================================================================
    @pw.udf
    def combine_text(title: str, content: str, comments: str) -> str:
        parts = [p for p in [title or "", content or "", comments or ""] if p.strip()]
        return " ".join(parts)[:2000]
    
    @pw.udf
    def generate_embedding_json(text: str) -> str:
        embedding = get_embedding(text)
        return json.dumps(embedding)
    
    enriched_table = sentiment_table.select(
        symbol=pw.this.symbol,
        post_id=pw.this.post_id,
        combined_text=combine_text(
            pw.this.post_title,
            pw.this.post_content,
            pw.this.post_comments
        ),
        post_timestamp=pw.this.post_timestamp,
    ).select(
        pw.this.symbol,
        pw.this.post_id,
        pw.this.combined_text,
        pw.this.post_timestamp,
        embedding_json=generate_embedding_json(pw.this.combined_text)
    )

    # =========================================================================
    # STEP 2: Centroid-based clustering with sentiment tracking
    # =========================================================================
    @pw.reducers.stateful_many
    def centroid_cluster_reducer(state: Optional[dict], batch: list[tuple[list, int]]) -> dict:
        """Cluster posts using centroid-based cosine similarity with sentiment."""
        import hashlib
        
        if state is not None and hasattr(state, 'as_dict'):
            state = state.as_dict()
        
        if state is None:
            state = {
                'clusters': {},
                'post_hashes': [],
                'next_cluster_id': 1,
                'symbol': None
            }
        
        post_hashes = set(state.get('post_hashes', []))
        clusters = state.get('clusters', {})
        now_iso = datetime.now(timezone.utc).isoformat()
        symbol = state.get('symbol')

        for row, count in batch:
            if count <= 0:
                continue
            
            row_symbol, post_id, text, timestamp, emb_json = row
            
            if symbol is None:
                symbol = row_symbol
                state['symbol'] = symbol
            
            try:
                embedding = json.loads(emb_json) if isinstance(emb_json, str) else list(emb_json)
            except Exception:
                embedding = [0.0] * EMBEDDING_DIMENSIONS
            
            # Calculate VADER sentiment
            post_sentiment = get_vader_sentiment(text)
            
            # Extract sentiment_type from combined_text if encoded, otherwise default to 'company'
            # The producer encodes: sentiment_type and related_to in the post data
            post = {
                'post_id': post_id, 
                'text': text[:500], 
                'timestamp': timestamp,
                'sentiment': post_sentiment,
                'sentiment_type': 'company',  # Will be updated when we have access to raw post data
                'related_to': symbol
            }
            post_hash = hashlib.md5(f"{symbol}:{post_id}:{text[:100]}".encode()).hexdigest()
            
            if post_hash in post_hashes:
                continue
            post_hashes.add(post_hash)
            
            # Find best matching cluster
            best_cluster_id = None
            best_similarity = 0.0
            
            for cid, cdata in clusters.items():
                centroid = cdata.get('centroid', [])
                if centroid:
                    sim = cosine_similarity(embedding, centroid)
                    if sim > best_similarity:
                        best_similarity = sim
                        best_cluster_id = cid
            
            if best_cluster_id and best_similarity >= SIMILARITY_THRESHOLD:
                c = clusters[best_cluster_id]
                c['posts'] = sorted(
                    c['posts'] + [post],
                    key=lambda p: p.get('timestamp', ''),
                    reverse=True
                )[:MAX_POSTS_PER_CLUSTER]
                c['count'] = len(c['posts'])
                c['last_updated'] = now_iso
                
                # Update weighted sentiment
                old_sentiment = c.get('avg_sentiment', 0.0)
                decayed_sentiment = apply_sentiment_decay(old_sentiment, c.get('last_updated', now_iso))
                old_weight = c.get('total_weight', c['count'] - 1) * 0.9
                new_weight = 1.0
                total_weight = old_weight + new_weight
                c['avg_sentiment'] = (decayed_sentiment * old_weight + post_sentiment * new_weight) / total_weight if total_weight > 0 else post_sentiment
                c['total_weight'] = total_weight
            else:
                new_id = str(state['next_cluster_id'])
                clusters[new_id] = {
                    'summary': text[:150],  # Initial summary from first post
                    'posts': [post],
                    'centroid': embedding,
                    'created_at': now_iso,
                    'last_updated': now_iso,
                    'count': 1,
                    'avg_sentiment': post_sentiment,
                    'total_weight': 1.0
                }
                state['next_cluster_id'] += 1
        
        # Merge similar clusters
        cluster_ids = list(clusters.keys())
        merged = set()
        for i, cid1 in enumerate(cluster_ids):
            if cid1 in merged:
                continue
            for cid2 in cluster_ids[i+1:]:
                if cid2 in merged:
                    continue
                c1, c2 = clusters.get(cid1), clusters.get(cid2)
                if c1 and c2 and c1.get('centroid') and c2.get('centroid'):
                    sim = cosine_similarity(c1['centroid'], c2['centroid'])
                    if sim >= MERGE_THRESHOLD:
                        c1['posts'] = sorted(
                            c1['posts'] + c2['posts'],
                            key=lambda p: p.get('timestamp', ''),
                            reverse=True
                        )[:MAX_POSTS_PER_CLUSTER]
                        c1['count'] = len(c1['posts'])
                        w1, w2 = c1.get('total_weight', c1['count']), c2.get('total_weight', c2['count'])
                        s1, s2 = c1.get('avg_sentiment', 0.0), c2.get('avg_sentiment', 0.0)
                        if w1 + w2 > 0:
                            c1['avg_sentiment'] = (s1 * w1 + s2 * w2) / (w1 + w2)
                            c1['total_weight'] = w1 + w2
                        merged.add(cid2)
        
        for cid in merged:
            del clusters[cid]
        
        # Remove stale clusters
        now = datetime.now(timezone.utc)
        to_remove = []
        for cid, cdata in clusters.items():
            try:
                last_updated = datetime.fromisoformat(cdata['last_updated'].replace('Z', '+00:00'))
                age_hours = (now - last_updated).total_seconds() / 3600
                if age_hours > CLUSTER_EXPIRY_HOURS and cdata['count'] < 3:
                    to_remove.append(cid)
            except Exception:
                pass
        
        for cid in to_remove:
            del clusters[cid]
        
        state['clusters'] = clusters
        state['post_hashes'] = list(post_hashes)
        return state

    # Group by symbol and cluster
    clustered_table = enriched_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        cluster_state=centroid_cluster_reducer(
            pw.this.symbol,
            pw.this.post_id,
            pw.this.combined_text,
            pw.this.post_timestamp,
            pw.this.embedding_json
        )
    )

    # =========================================================================
    # STEP 3: Extract cluster data and calculate overall sentiment
    # =========================================================================
    @pw.udf
    def extract_clusters_and_save(symbol: str, cluster_state: pw.Json, output_dir: str) -> str:
        """Extract clusters, calculate sentiment, and save to file (read-modify-write)."""
        
        # Publish RUNNING status at START of processing
        room_id = f"symbol:{symbol}"
        try:
            publish_agent_status(room_id, "Sentiment Agent", "RUNNING")
        except Exception as e:
            print(f"⚠️ [{symbol}] Failed to publish Sentiment Agent status: {e}")
        
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{symbol}_clusters.json")
        
        # Get Redis client once for all operations
        try:
            redis_client = get_redis_client()
        except Exception as e:
            print(f"⚠️ [{symbol}] Failed to connect to Redis: {e}")
            redis_client = None
        
        # Load existing state from file
        existing_clusters = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    for c in existing_data.get('clusters', []):
                        existing_clusters[c['cluster_id']] = c
            except Exception:
                pass
        
        # Get new clusters from Pathway state
        new_clusters = {}
        if cluster_state is not None:
            try:
                state_dict = cluster_state.as_dict()
                clusters_dict = state_dict.get('clusters', {})
                for cluster_id, cluster_data in clusters_dict.items():
                    new_clusters[int(cluster_id)] = cluster_data
            except Exception:
                pass
        
        # Merge: update existing with new, add new clusters
        for cluster_id, cluster_data in new_clusters.items():
            raw_sentiment = float(cluster_data.get('avg_sentiment', 0.0))
            last_updated = str(cluster_data.get('last_updated', ''))
            decayed_sentiment = apply_sentiment_decay(raw_sentiment, last_updated)
            count = int(cluster_data.get('count', 0))
            
            existing_clusters[cluster_id] = {
                'cluster_id': cluster_id,
                'summary': str(cluster_data.get('summary', '')),
                'avg_sentiment': decayed_sentiment,
                'count': count,
                'posts': cluster_data.get('posts', []),
                'created_at': str(cluster_data.get('created_at', '')),
                'last_updated': last_updated
            }
        
        # Calculate overall sentiment from all clusters
        clusters_list = list(existing_clusters.values())
        total_weighted_sentiment = 0.0
        total_posts = 0
        
        for cluster in clusters_list:
            count = cluster.get('count', 0)
            total_weighted_sentiment += cluster.get('avg_sentiment', 0.0) * count
            total_posts += count
        
        overall_sentiment = total_weighted_sentiment / total_posts if total_posts > 0 else 0.0
        
        result = {
            'symbol': symbol,
            'overall_sentiment': overall_sentiment,
            'cluster_count': len(clusters_list),
            'total_posts': total_posts,
            'clusters': clusters_list,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Save to file (JSON Lines format - single line for Pathway compatibility)
        try:
            with open(file_path, 'w') as f:
                json.dump(result, f)  # No indent = single line (JSON Lines format)
            print(f"💾 [{symbol}] Saved {len(clusters_list)} clusters to {file_path}")
        except Exception as e:
            print(f"Error saving clusters for {symbol}: {e}")
        
        # Save to Redis for API access
        if redis_client:
            try:
                result_json = json.dumps(result)
                
                # Store in sentiment_clusters:{symbol} for /sentiment/clusters/{symbol} endpoint
                redis_client.set(f"sentiment_clusters:{symbol}", result_json)
                
                # Store individual clusters in clusters:all hash for /sentiment/clusters endpoint
                for cluster in clusters_list:
                    cluster_key = f"{symbol}:{cluster.get('cluster_id', 0)}"
                    cluster_with_symbol = {**cluster, 'symbol': symbol}
                    redis_client.hset("clusters:all", cluster_key, json.dumps(cluster_with_symbol))
                
                print(f"📡 [{symbol}] Cached {len(clusters_list)} clusters to Redis")
            except Exception as e:
                print(f"⚠️ [{symbol}] Redis cache failed: {e}")
        
        # Trigger alert if sentiment crosses threshold
        trigger_sentiment_alert(symbol, overall_sentiment)
        
        # Publish COMPLETED status for clustering phase
        try:
            publish_report(room_id, "Sentiment Agent", {
                "symbol": symbol,
                "report_type": "sentiment",
                "overall_sentiment": round(overall_sentiment, 3),
                "cluster_count": len(clusters_list),
                "total_posts": total_posts,
                "clusters": clusters_list  # Include cluster data for frontend
            })
            publish_agent_status(room_id, "Sentiment Clustering Agent", "COMPLETED")
        except Exception as e:
            print(f"⚠️ [{symbol}] Failed to publish Sentiment Clustering Agent status: {e}")
        
        return json.dumps(result)
    
    # Create output table with cluster data
    output_table = clustered_table.select(
        symbol=pw.this.symbol,
        clusters_json=extract_clusters_and_save(
            pw.this.symbol,
            pw.this.cluster_state,
            clusters_directory
        )
    )
    
    return output_table
