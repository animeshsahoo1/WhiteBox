"""News Agent with Story Clustering and Stateful Report Generation

This module supports TWO clustering approaches:
1. CENTROID-BASED: Uses numpy cosine similarity with centroid embeddings per cluster
2. KNN-BASED: Uses Pathway's BruteForceKnn index for neighbor-based clustering

Set CLUSTERING_APPROACH environment variable to switch between them:
- "centroid" (default): Traditional centroid-based clustering
- "knn": Pathway KNN index-based clustering
"""

import os
import pathway as pw
from pathway.xpacks.llm.llms import LiteLLMChat
from datetime import datetime, timezone
from dotenv import load_dotenv
import json
import numpy as np
from typing import Optional
import litellm
import uuid
import hashlib


# Import Redis and PostgreSQL save functions
try:
    from redis_cache import save_report_to_postgres, save_report_to_redis
    from event_publisher import publish_agent_status, publish_report, publish_alert
except ImportError:
    from .redis_cache import save_report_to_postgres, save_report_to_redis
    from .event_publisher import publish_agent_status, publish_report, publish_alert

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================
SIMILARITY_THRESHOLD = 0.65  # Cosine similarity threshold for clustering
MERGE_THRESHOLD = 0.80       # Threshold for merging similar clusters
CLUSTER_EXPIRY_HOURS = 72
MAX_ARTICLES_PER_CLUSTER = 10
EMBEDDING_DIMENSIONS = 1536

# Alert cooldowns (module-level)
_news_alert_cooldowns = {}

def assess_news_impact(report: str, symbol: str) -> tuple[bool, str]:
    """
    Use LLM to assess if news is market-moving.
    Returns (is_significant, reason).
    """
    try:
        import litellm
        
        prompt = f"""NEWS IMPACT TRIAGE: {symbol}

HEADLINE & CONTENT:
{report[:2000]}

MARKET-MOVING CRITERIA (flag if ANY apply):
• EARNINGS: Beat/miss, guidance change, margin surprise, revenue acceleration/deceleration
• CORPORATE ACTION: M&A, spinoff, buyback announcement, dividend change, stock split
• MANAGEMENT: CEO/CFO change, board shakeup, insider buying/selling >$1M
• REGULATORY: FDA approval/rejection, antitrust action, SEC investigation, license grant/revoke
• COMPETITIVE: Major contract win/loss, market share shift, new product launch, partnership
• MACRO EXPOSURE: Tariff impact, currency shock, supply chain disruption, geopolitical event

IMPACT: YES or NO
IF YES → CATALYST TYPE: [one of above categories]
MAGNITUDE: HIGH (>5% move potential) | MEDIUM (2-5%) | LOW (<2%)
DIRECTION: BULLISH | BEARISH | UNCERTAIN
REASON: <20 words>"""

        response = litellm.completion(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            temperature=0.0,
            max_tokens=100
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse response
        is_significant = "IMPACT: YES" in result.upper()
        reason = "Significant market news detected"
        
        if "REASON:" in result:
            reason = result.split("REASON:")[-1].strip()
        
        return is_significant, reason
        
    except Exception as e:
        print(f"⚠️ [{symbol}] News impact assessment failed: {e}")
        return False, ""


def trigger_news_alert(symbol: str, report: str, cluster_count: int):
    """Trigger alert when significant news arrives using LLM assessment."""
    
    alerts_enabled = os.getenv("NEWS_ALERT_ENABLED", "true").lower() == "true"
    alert_cooldown = int(os.getenv("NEWS_ALERT_COOLDOWN", "600"))  # 10 min default
    
    if not alerts_enabled:
        return
    
    # Check cooldown
    now = datetime.now()
    last = _news_alert_cooldowns.get(symbol)
    if last and (now - last).total_seconds() < alert_cooldown:
        return
    
    # Use LLM to assess impact
    is_significant, reason = assess_news_impact(report, symbol)
    
    if is_significant:
        print(f"📰 [{symbol}] NEWS ALERT: {reason}")
        try:
            publish_alert(
                symbol=symbol,
                alert_type="news",
                reason=reason,
                severity="high",
                trigger_debate=True
            )
            _news_alert_cooldowns[symbol] = now
        except Exception as e:
            print(f"⚠️ [{symbol}] News alert failed: {e}")


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calculate cosine similarity between two vectors."""
    vec1_np, vec2_np = np.array(vec1), np.array(vec2)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    return float(np.dot(vec1_np, vec2_np) / norm_product) if norm_product > 0 else 0.0


class NewsKnowledgeBase:
    """Stores news articles as JSONL for downstream RAG retrieval."""
    
    def __init__(self, knowledge_base_dir: str = "/app/knowledge_base"):
        self.knowledge_base_dir = knowledge_base_dir
        self._article_hashes = set()
        os.makedirs(knowledge_base_dir, exist_ok=True)
    
    def _get_article_hash(self, text: str) -> str:
        return hashlib.md5(text[:500].encode()).hexdigest()
    
    def _get_news_jsonl_path(self, symbol: str) -> str:
        symbol_dir = os.path.join(self.knowledge_base_dir, symbol, "jsons")
        os.makedirs(symbol_dir, exist_ok=True)
        return os.path.join(symbol_dir, "news_articles.jsonl")
    
    def store_article(self, symbol: str, text: str, timestamp: str) -> bool:
        """Store article if not duplicate. Returns True if stored."""
        article_hash = self._get_article_hash(text)
        if article_hash in self._article_hashes:
            return False
        
        self._article_hashes.add(article_hash)
        article_doc = {"id": str(uuid.uuid4()), "text": text, "timestamp": timestamp, "symbol": symbol}
        
        try:
            with open(self._get_news_jsonl_path(symbol), "a", encoding="utf-8") as f:
                f.write(json.dumps(article_doc) + "\n")
            return True
        except Exception:
            return False
    
    def load_existing_hashes(self, symbol: str):
        """Load existing article hashes to prevent duplicates on restart."""
        jsonl_path = self._get_news_jsonl_path(symbol)
        if os.path.exists(jsonl_path):
            try:
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            article = json.loads(line.strip())
                            self._article_hashes.add(self._get_article_hash(article.get('text', '')))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass


_news_kb = None

def get_news_knowledge_base(kb_dir: str = "/app/knowledge_base") -> NewsKnowledgeBase:
    global _news_kb
    if _news_kb is None:
        _news_kb = NewsKnowledgeBase(kb_dir)
    return _news_kb


def get_embedding(text: str) -> list:
    """Generate embedding using OpenRouter."""
    try:
        response = litellm.embedding(
            model="openai/text-embedding-3-small",
            input=[text],
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1"
        )
        return response.data[0]['embedding']
    except Exception:
        return [0.0] * EMBEDDING_DIMENSIONS


class NewsClusterManager:
    """Manages news story clusters with dynamic headline generation."""
    
    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory
        self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}")) if os.environ.get("STOCK_COMPANY_MAP") else {}
        
        self.model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not self.model_name.startswith(('openrouter/', 'openai/')):
            self.model_name = f'openrouter/{self.model_name}'
        
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or "dummy-key"
        self.has_valid_api_key = self.api_key != "dummy-key"
        
        self.llm = LiteLLMChat(
            model=self.model_name, api_key=self.api_key,
            api_base="https://openrouter.ai/api/v1", temperature=0.0, max_tokens=1000
        )
        os.makedirs(self.reports_directory, exist_ok=True)

    def call_llm_sync(self, messages: list) -> str:
        """Direct synchronous LLM call for use inside reducers."""
        try:
            response = litellm.completion(
                model=self.model_name, messages=messages, api_key=self.api_key,
                api_base="https://openrouter.ai/api/v1", temperature=0.0, max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""

    def _get_report_path(self, symbol: str) -> str:
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "news_report.md")

    def _load_report(self, symbol: str) -> str:
        report_path = self._get_report_path(symbol)
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            company = self.symbol_mapping.get(symbol, symbol)
            return f"# {company} ({symbol}) - News Report\n\n*Awaiting news updates...*"

    def generate_cluster_headline(self, symbol: str, articles: list) -> str:
        """Generate a representative headline for a story cluster."""
        company = self.symbol_mapping.get(symbol, symbol)
        if not articles:
            return f"Developing story about {company}"
        
        titles = "\n".join([f"- {art.get('title', '')}" for art in articles[:8]])
        prompt = f"""HEADLINE SYNTHESIS: {company}

Related headlines:
{titles}

Combine into ONE punchy headline (max 10 words) that captures the core story. Use active voice, be specific."""
        
        if self.has_valid_api_key:
            response = self.call_llm_sync([{"role": "user", "content": prompt}])
            if response:
                return response.strip().strip('"\'')
        return articles[0].get('title', f"Developing story about {company}")

    def create_report_prompt(self, symbol: str, current_report: str, story_clusters: list) -> list[dict]:
        company = self.symbol_mapping.get(symbol, symbol)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        clusters_text = "\n".join([
            f"{i+1}. [{sc['article_count']} articles] {sc['headline']}"
            for i, sc in enumerate(story_clusters)
        ])
        
        prompt = f"""# {company} NEWS DIGEST | {timestamp} UTC

ACTIVE STORIES:
{clusters_text}

FOR EACH STORY:
### [#]. [Headline]
**Coverage Depth**: [X] sources | **Developing**: Yes/No
**What**: One sentence — the core event
**So What**: One sentence — why traders should care (price implication, catalyst timing)

Prioritize by market impact. Skip fluff stories."""
        
        return [{"role": "user", "content": prompt}]


def process_news_stream(
    news_table: pw.Table, 
    reports_directory: str = "./reports/news",
    knowledge_base_dir: str = "/app/knowledge_base"
) -> tuple[pw.Table, pw.Table]:
    """Process news stream with story clustering.
    
    Uses CLUSTERING_APPROACH env var to choose between:
    - "centroid": Traditional centroid-based clustering (default)
    - "knn": Pathway KNN index-based clustering
    """
    
    cluster_manager = NewsClusterManager(reports_directory)
    news_kb = get_news_knowledge_base(knowledge_base_dir)

    # =========================================================================
    # STEP 1: Enrich articles with embeddings and store in knowledge base
    # =========================================================================
    @pw.udf
    def enrich_news(symbol: str, title: str, description: str, timestamp: str) -> pw.Json:
        """Generate embedding and store article in knowledge base."""
        combined = f"{title} {description}"
        news_kb.store_article(symbol, combined, timestamp)
        embedding = get_embedding(combined)
        return pw.Json({
            "combined_text": combined,
            "embedding": embedding
        })
    
    @pw.udf
    def embedding_to_json(enriched: pw.Json) -> str:
        """Extract embedding as JSON string for reducer."""
        emb = enriched["embedding"]
        if hasattr(emb, 'as_list'):
            return json.dumps(list(emb.as_list()))
        return json.dumps(list(emb))

    enriched_table = news_table.select(
        symbol=pw.this.symbol, timestamp=pw.this.timestamp, title=pw.this.title,
        description=pw.this.description, source=pw.this.source, url=pw.this.url,
        published_at=pw.this.published_at,
        enriched=enrich_news(pw.this.symbol, pw.this.title, pw.this.description, pw.this.timestamp)
    ).select(
        symbol=pw.this.symbol, timestamp=pw.this.timestamp, title=pw.this.title,
        description=pw.this.description, source=pw.this.source, url=pw.this.url,
        published_at=pw.this.published_at,
        combined_text=pw.this.enriched["combined_text"].as_str(),
        embedding_json=embedding_to_json(pw.this.enriched)
    )

    # =========================================================================
    # STEP 2: Centroid-based clustering with stateful reducer
    # =========================================================================
    @pw.reducers.stateful_many
    def centroid_cluster_reducer(state: Optional[dict], batch: list[tuple[list, int]]) -> dict:
        """Cluster articles using centroid-based cosine similarity.
        
        State structure:
        {
            'clusters': {
                'cluster_id': {
                    'headline': str,
                    'articles': [{'title': ..., 'description': ..., ...}],
                    'centroid': [float, ...],  # Embedding vector
                    'first_seen': str,
                    'last_updated': str,
                    'needs_headline_update': bool,
                    'links': [str, ...]
                }
            },
            'article_hashes': [...],  # Dedup tracking
            'next_cluster_id': int
        }
        """
        if state is not None and hasattr(state, 'as_dict'):
            state = state.as_dict()
        
        if state is None:
            state = {
                'clusters': {},
                'article_hashes': [],
                'next_cluster_id': 1
            }
        
        # Convert article_hashes from list to set for O(1) lookup
        article_hashes = set(state.get('article_hashes', []))
        clusters = state.get('clusters', {})
        now_iso = datetime.now(timezone.utc).isoformat()

        for row, count in batch:
            if count <= 0:
                continue
            
            # row: [symbol, timestamp, title, desc, source, url, combined_text, embedding_json]
            symbol, timestamp, title, desc, source, url, text, emb_json = row
            
            # Parse embedding
            try:
                embedding = json.loads(emb_json) if isinstance(emb_json, str) else list(emb_json)
            except:
                embedding = [0.0] * EMBEDDING_DIMENSIONS
            
            article = {'title': title, 'description': desc, 'source': source, 'timestamp': timestamp}
            article_link = url if url else None
            article_hash = hashlib.md5(f"{symbol}:{title}:{timestamp}".encode()).hexdigest()
            
            # Skip duplicates
            if article_hash in article_hashes:
                continue
            article_hashes.add(article_hash)
            
            # Find best matching cluster using centroid similarity
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
                # Add to existing cluster
                c = clusters[best_cluster_id]
                c['articles'] = sorted(
                    c['articles'] + [article], 
                    key=lambda a: a.get('timestamp', ''), 
                    reverse=True
                )[:MAX_ARTICLES_PER_CLUSTER]
                c['last_updated'] = now_iso
                c['needs_headline_update'] = True
                if article_link:
                    c['links'] = list(set(c.get('links', [])) | {article_link})
            else:
                # Create new cluster with article embedding as initial centroid
                new_id = str(state['next_cluster_id'])
                clusters[new_id] = {
                    'headline': title,
                    'articles': [article],
                    'centroid': embedding,
                    'first_seen': now_iso,
                    'last_updated': now_iso,
                    'needs_headline_update': False,
                    'links': [article_link] if article_link else []
                }
                state['next_cluster_id'] += 1
        
        # =====================================================================
        # MERGE SIMILAR CLUSTERS - ONCE after processing entire batch
        # This is more efficient than merging inside the per-article loop
        # =====================================================================
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
                        # Merge c2 into c1
                        c1['articles'] = sorted(
                            c1['articles'] + c2['articles'],
                            key=lambda a: a.get('timestamp', ''),
                            reverse=True
                        )[:MAX_ARTICLES_PER_CLUSTER]
                        c1['links'] = list(set(c1.get('links', [])) | set(c2.get('links', [])))
                        c1['needs_headline_update'] = True
                        merged.add(cid2)
        
        for cid in merged:
            del clusters[cid]
        
        # Remove stale clusters (older than CLUSTER_EXPIRY_HOURS)
        now = datetime.now(timezone.utc)
        to_remove = []
        for cid, cdata in clusters.items():
            try:
                last_updated = datetime.fromisoformat(cdata['last_updated'].replace('Z', '+00:00'))
                if (now - last_updated).total_seconds() / 3600 > CLUSTER_EXPIRY_HOURS:
                    to_remove.append(cid)
            except:
                pass
        
        for cid in to_remove:
            del clusters[cid]
        
        state['clusters'] = clusters
        state['article_hashes'] = list(article_hashes)  # Convert back to list for JSON
        return state

    clustered_table = enriched_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        cluster_state=centroid_cluster_reducer(
            pw.this.symbol, pw.this.timestamp, pw.this.title, pw.this.description,
            pw.this.source, pw.this.url, pw.this.combined_text, pw.this.embedding_json
        )
    )

    # =========================================================================
    # STEP 3: Extract clusters and update headlines with new centroid embeddings
    # =========================================================================
    @pw.udf
    def extract_clusters(cluster_state: pw.Json) -> list:
        """Extract cluster list from state."""
        if cluster_state is None:
            return []
        try:
            state_dict = cluster_state.as_dict()
            return [
                {'cluster_id': int(cid), 'headline': str(cd.get('headline', '')),
                 'articles': list(cd.get('articles', [])), 'first_seen': str(cd.get('first_seen', '')),
                 'last_updated': str(cd.get('last_updated', '')), 
                 'needs_headline_update': bool(cd.get('needs_headline_update', False)),
                 'links': list(cd.get('links', [])),
                 'centroid': list(cd.get('centroid', []))}
                for cid, cd in state_dict.get('clusters', {}).items()
            ]
        except:
            return []

    @pw.udf
    def get_cluster_id(c: pw.Json) -> int:
        return c["cluster_id"].as_int()
    
    @pw.udf
    def get_headline(c: pw.Json) -> str:
        return c["headline"].as_str() if c["headline"] else ""
    
    @pw.udf
    def get_articles_json(c: pw.Json) -> str:
        return json.dumps(c["articles"].as_list() if c["articles"] else [])
    
    @pw.udf
    def get_first_seen(c: pw.Json) -> str:
        return c["first_seen"].as_str() if c["first_seen"] else ""
    
    @pw.udf
    def get_last_updated(c: pw.Json) -> str:
        return c["last_updated"].as_str() if c["last_updated"] else ""
    
    @pw.udf
    def get_needs_update(c: pw.Json) -> bool:
        return c["needs_headline_update"].as_bool() if c["needs_headline_update"] else False
    
    @pw.udf
    def get_links_json(c: pw.Json) -> str:
        return json.dumps(c["links"].as_list() if c["links"] else [])
    
    @pw.udf
    def get_centroid_json(c: pw.Json) -> str:
        return json.dumps(c["centroid"].as_list() if c["centroid"] else [])

    clusters_exploded = clustered_table.select(
        symbol=pw.this.symbol, cluster_item=extract_clusters(pw.this.cluster_state)
    ).flatten(pw.this.cluster_item).select(
        symbol=pw.this.symbol, cluster_id=get_cluster_id(pw.this.cluster_item),
        headline=get_headline(pw.this.cluster_item), articles_json=get_articles_json(pw.this.cluster_item),
        first_seen=get_first_seen(pw.this.cluster_item), last_updated=get_last_updated(pw.this.cluster_item),
        needs_headline_update=get_needs_update(pw.this.cluster_item),
        links_json=get_links_json(pw.this.cluster_item),
        centroid_json=get_centroid_json(pw.this.cluster_item)
    )

    # Update headlines and regenerate centroid from headline embedding (NOT averaging)
    @pw.udf
    def update_headline_and_centroid(
        symbol: str, cluster_id: int, articles_json: str, 
        current_headline: str, needs_update: bool, current_centroid_json: str
    ) -> pw.Json:
        """Generate new headline and compute its embedding as the new centroid.
        
        Key change: Centroid is now the embedding of the generated headline,
        NOT an average of article embeddings. This makes the cluster representation
        more semantically meaningful.
        """
        try:
            articles_list = json.loads(articles_json) if articles_json else []
        except:
            articles_list = []
        
        count = len(articles_list)
        new_headline = current_headline
        new_centroid = json.loads(current_centroid_json) if current_centroid_json else []
        
        # Update headline if needed (3+ articles and flagged for update)
        if (needs_update and count >= 3) or (count >= 3 and len(current_headline) < 10):
            new_headline = cluster_manager.generate_cluster_headline(symbol, articles_list)
            # Generate FRESH embedding from the new headline as centroid
            new_centroid = get_embedding(new_headline)
        
        if not new_headline:
            new_headline = f"Developing story for {symbol}"
        
        return pw.Json({
            "headline": new_headline,
            "centroid": new_centroid
        })
    
    @pw.udf
    def count_articles(articles_json: str) -> int:
        try:
            return len(json.loads(articles_json)) if articles_json else 0
        except:
            return 0

    clusters_with_headlines = clusters_exploded.select(
        symbol=pw.this.symbol, cluster_id=pw.this.cluster_id,
        headline_data=update_headline_and_centroid(
            pw.this.symbol, pw.this.cluster_id, pw.this.articles_json, 
            pw.this.headline, pw.this.needs_headline_update, pw.this.centroid_json
        ),
        articles_json=pw.this.articles_json,
        links_json=pw.this.links_json,
        first_seen=pw.this.first_seen, 
        last_updated=pw.this.last_updated
    ).select(
        symbol=pw.this.symbol, 
        cluster_id=pw.this.cluster_id,
        headline=pw.this.headline_data["headline"].as_str(),
        article_count=count_articles(pw.this.articles_json),
        articles_json=pw.this.articles_json,
        links_json=pw.this.links_json,
        first_seen=pw.this.first_seen, 
        last_updated=pw.this.last_updated
    )

    # =========================================================================
    # STEP 4: Stateful report generation
    # =========================================================================
    @pw.udf
    def clusters_to_json(t: tuple) -> str:
        return json.dumps([
            {'cluster_id': i[0], 'headline': i[1], 'article_count': i[2], 'first_seen': i[3], 'last_updated': i[4]}
            for i in t
        ])

    clusters_by_symbol = clusters_with_headlines.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        clusters_json=pw.reducers.sorted_tuple(
            pw.make_tuple(pw.this.cluster_id, pw.this.headline, pw.this.article_count, 
                         pw.this.first_seen, pw.this.last_updated)
        )
    )
    
    clusters_json_table = clusters_by_symbol.select(
        symbol=pw.this.symbol, clusters_json=clusters_to_json(pw.this.clusters_json)
    )

    @pw.reducers.stateful_many
    def stateful_report_reducer(state: Optional[dict], batch: list[tuple[list, int]]) -> dict:
        """Generate reports when cluster changes are detected."""
        if state is not None and hasattr(state, 'as_dict'):
            state = state.as_dict()
        
        if state is None:
            state = {'symbol': None, 'report': '', 'cluster_states': {}, 'update_count': 0}
        
        symbol, clusters_json = None, None
        for row, count in batch:
            if count > 0:
                symbol, clusters_json = row[0], row[1]
                state['symbol'] = symbol
        
        if not symbol or not clusters_json:
            return state
        
        try:
            clusters = json.loads(clusters_json)
            if not clusters:
                return state
            
            # Detect changes in clusters
            prev = state.get('cluster_states', {})
            has_changes = any(
                str(c['cluster_id']) not in prev or
                prev[str(c['cluster_id'])]['article_count'] != c['article_count'] or
                prev[str(c['cluster_id'])]['headline'] != c['headline']
                for c in clusters
            ) or any(cid not in {str(c['cluster_id']) for c in clusters} for cid in prev)
            
            if not has_changes:
                return state
            
            # Publish RUNNING status at START of processing (before LLM call)
            try:
                room_id = f"symbol:{symbol}"
                publish_agent_status(room_id, "News Agent", "RUNNING")
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to publish News Agent status: {e}")
            
            state['update_count'] += 1
            current_report = state.get('report') or cluster_manager._load_report(symbol)
            
            if cluster_manager.has_valid_api_key:
                new_report = cluster_manager.call_llm_sync(
                    cluster_manager.create_report_prompt(symbol, current_report, clusters)
                )
            else:
                company = cluster_manager.symbol_mapping.get(symbol, symbol)
                stories = "\n".join([f"- **{c['headline']}** ({c['article_count']} articles)" for c in clusters])
                new_report = f"# {company} ({symbol}) - News Report\n\n## Active Stories\n{stories}\n\n*Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*"
            
            with open(cluster_manager._get_report_path(symbol), "w", encoding="utf-8") as f:
                f.write(new_report)
            print(f"📝 [{symbol}] News report updated (update #{state['update_count']})")
            
            # Calculate new cluster count for reporting
            new_cluster_count = sum(1 for c in clusters if str(c['cluster_id']) not in prev)
            
            # Trigger news alert with LLM-based impact assessment
            trigger_news_alert(symbol, new_report, len(clusters))
            
            # Save to Redis for API caching
            try:
                save_report_to_redis(symbol, "news", new_report)
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to cache news report to Redis: {e}")
            
            # Save to PostgreSQL for historical storage
            try:
                entry = {
                    "symbol": symbol,
                    "report_type": "news",
                    "content": new_report,
                    "last_updated": datetime.utcnow().isoformat(),
                }
                save_report_to_postgres(symbol, "news", entry)
                print(f"✈️ [{symbol}] Saved news report to PostgreSQL")
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to save news to PostgreSQL: {e}")
            
            # Publish report and COMPLETED status
            try:
                room_id = f"symbol:{symbol}"
                publish_report(room_id, "News Agent", {
                    "symbol": symbol,
                    "report_type": "news",
                    "cluster_count": len(clusters),
                    "new_clusters": new_cluster_count,
                    "update_number": state['update_count']
                })
                publish_agent_status(room_id, "News Agent", "COMPLETED")
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to publish News Agent events: {e}")

            state['report'] = new_report
            state['cluster_states'] = {
                str(c['cluster_id']): {'headline': c['headline'], 'article_count': c['article_count']} 
                for c in clusters
            }
            
        except Exception:
            # Publish FAILED status on error
            try:
                if symbol:
                    room_id = f"symbol:{symbol}"
                    publish_agent_status(room_id, "News Agent", "FAILED")
            except:
                pass
        
        return state

    reports_stateful = clusters_json_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        report_state=stateful_report_reducer(pw.this.symbol, pw.this.clusters_json)
    )
    
    @pw.udf
    def extract_report(state: pw.Json) -> str:
        try:
            return str(state.as_dict().get('report', ''))
        except:
            return ""

    response_table = reports_stateful.select(
        symbol=pw.this.symbol, 
        response=extract_report(pw.this.report_state)
    )

    # Cluster visualization table for API
    cluster_viz_table = clusters_with_headlines.select(
        symbol=pw.this.symbol, 
        cluster_id=pw.this.cluster_id, 
        headline=pw.this.headline,
        articles_json=pw.this.articles_json,
        links_json=pw.this.links_json,
        article_count=pw.this.article_count,
        first_seen=pw.this.first_seen,
        last_updated=pw.this.last_updated, 
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    return response_table, cluster_viz_table
