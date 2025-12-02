"""News Agent with Story Clustering and Stateful Report Generation"""

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


# Import PostgreSQL save function
try:
    from redis_cache import save_report_to_postgres
except ImportError:
    from .redis_cache import save_report_to_postgres

load_dotenv()

# Constants
SIMILARITY_THRESHOLD = 0.65
MERGE_THRESHOLD = 0.80
CLUSTER_EXPIRY_HOURS = 72
MAX_ARTICLES_PER_CLUSTER = 10


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
        return [0.0] * 1536


def cosine_similarity(vec1: list, vec2: list) -> float:
    vec1_np, vec2_np = np.array(vec1), np.array(vec2)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    return float(np.dot(vec1_np, vec2_np) / norm_product) if norm_product > 0 else 0.0


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
        prompt = f"Synthesize these headlines about {company} into ONE headline (max 12 words):\n\n{titles}\n\nHeadline:"
        
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
        
        prompt = f"""# {company} News Digest

Stories:
{clusters_text}

For each story, write 1 sentence explaining the development. Format:
### [number]. [headline]
**Articles**: [count]
[1-sentence summary]

End with: *Timestamp: {timestamp} UTC*"""
        
        return [{"role": "user", "content": prompt}]


def process_news_stream(
    news_table: pw.Table, 
    reports_directory: str = "./reports/news",
    knowledge_base_dir: str = "/app/knowledge_base"
) -> tuple[pw.Table, pw.Table]:
    """Process news stream with story clustering and stateful report generation."""
    
    cluster_manager = NewsClusterManager(reports_directory)
    news_kb = get_news_knowledge_base(knowledge_base_dir)

    # STEP 1: Enrich with embeddings and store in KB
    @pw.udf
    def enrich_news(symbol: str, title: str, description: str, timestamp: str) -> pw.Json:
        combined = f"{title} {description}"
        news_kb.store_article(symbol, combined, timestamp)
        embedding = get_embedding(combined)
        return pw.Json({
            "combined_text": combined,
            "embedding": embedding
        })

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
        embedding=pw.this.enriched["embedding"]
    )

    # STEP 2: Story Clustering with Stateful Reducer
    @pw.reducers.stateful_many
    def story_cluster_reducer(state: Optional[dict], batch: list[tuple[list, int]]) -> dict:
        if state is None:
            state = {'clusters': {}, 'next_cluster_id': 1}
        
        clusters = state.get('clusters', {})
        now_iso = datetime.now(timezone.utc).isoformat()

        for row, count in batch:
            if count <= 0:
                continue
            
            symbol, timestamp, title, desc, source, url, pub, text, emb_json = row
            try:
                embedding = list(emb_json.as_list()) if hasattr(emb_json, 'as_list') else list(emb_json)
            except:
                continue
            
            article = {'title': title, 'description': desc, 'source': source, 'timestamp': timestamp}
            
            # Find best matching cluster
            best_id, best_sim = None, 0.0
            for cid, cdata in clusters.items():
                sim = cosine_similarity(embedding, cdata['centroid'])
                if sim > best_sim:
                    best_id, best_sim = cid, sim
            
            if best_id and best_sim >= SIMILARITY_THRESHOLD:
                c = clusters[best_id]
                n = len(c['articles'])
                c['centroid'] = [(c['centroid'][k] * n + embedding[k]) / (n + 1) for k in range(len(embedding))]
                c['articles'] = sorted(c['articles'] + [article], key=lambda a: a.get('timestamp', ''), reverse=True)[:MAX_ARTICLES_PER_CLUSTER]
                c['last_updated'] = now_iso
                c['needs_headline_update'] = True
            else:
                new_id = str(state['next_cluster_id'])
                clusters[new_id] = {
                    'centroid': embedding, 'headline': title,
                    'articles': [article], 'first_seen': now_iso,
                    'last_updated': now_iso, 'needs_headline_update': False
                }
                state['next_cluster_id'] += 1
        
        # Merge similar clusters
        cluster_ids = list(clusters.keys())
        for i, cid_i in enumerate(cluster_ids):
            if cid_i not in clusters:
                continue
            for cid_j in cluster_ids[i+1:]:
                if cid_j not in clusters:
                    continue
                if cosine_similarity(clusters[cid_i]['centroid'], clusters[cid_j]['centroid']) >= MERGE_THRESHOLD:
                    ci, cj = clusters[cid_i], clusters[cid_j]
                    ni, nj = len(ci['articles']), len(cj['articles'])
                    ci['centroid'] = [(ci['centroid'][k] * ni + cj['centroid'][k] * nj) / (ni + nj) for k in range(len(ci['centroid']))]
                    ci['articles'] = sorted(ci['articles'] + cj['articles'], key=lambda a: a.get('timestamp', ''), reverse=True)[:MAX_ARTICLES_PER_CLUSTER]
                    ci['last_updated'] = now_iso
                    ci['needs_headline_update'] = True
                    del clusters[cid_j]
        
        # Remove stale clusters
        now = datetime.now(timezone.utc)
        for cid in [c for c, d in clusters.items() if (now - datetime.fromisoformat(d['last_updated'].replace('Z', '+00:00'))).total_seconds() / 3600 > CLUSTER_EXPIRY_HOURS]:
            del clusters[cid]
        
        state['clusters'] = clusters
        return state

    clustered_table = enriched_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        cluster_state=story_cluster_reducer(
            pw.this.symbol, pw.this.timestamp, pw.this.title, pw.this.description,
            pw.this.source, pw.this.url, pw.this.published_at, pw.this.combined_text, pw.this.embedding
        )
    )

    # STEP 3: Extract clusters
    @pw.udf
    def extract_clusters(cluster_state: pw.Json) -> list:
        if cluster_state is None:
            return []
        try:
            state_dict = cluster_state.as_dict()
            return [
                {'cluster_id': int(cid), 'headline': str(cd.get('headline', '')),
                 'articles': list(cd.get('articles', [])), 'first_seen': str(cd.get('first_seen', '')),
                 'last_updated': str(cd.get('last_updated', '')), 'needs_headline_update': bool(cd.get('needs_headline_update', False))}
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

    clusters_exploded = clustered_table.select(
        symbol=pw.this.symbol, cluster_item=extract_clusters(pw.this.cluster_state)
    ).flatten(pw.this.cluster_item).select(
        symbol=pw.this.symbol, cluster_id=get_cluster_id(pw.this.cluster_item),
        headline=get_headline(pw.this.cluster_item), articles_json=get_articles_json(pw.this.cluster_item),
        first_seen=get_first_seen(pw.this.cluster_item), last_updated=get_last_updated(pw.this.cluster_item),
        needs_headline_update=get_needs_update(pw.this.cluster_item)
    )

    # STEP 4: Update Headlines
    @pw.udf
    def update_headline(symbol: str, cluster_id: int, articles_json: str, current: str, needs_update: bool) -> str:
        try:
            articles_list = json.loads(articles_json) if articles_json else []
        except:
            articles_list = []
        
        count = len(articles_list)
        if (needs_update and count >= 3) or (count >= 3 and len(current) < 10):
            return cluster_manager.generate_cluster_headline(symbol, articles_list)
        return current or f"Developing story for {symbol}"
    
    @pw.udf
    def count_articles(articles_json: str) -> int:
        try:
            return len(json.loads(articles_json)) if articles_json else 0
        except:
            return 0

    clusters_with_headlines = clusters_exploded.select(
        symbol=pw.this.symbol, cluster_id=pw.this.cluster_id,
        headline=update_headline(pw.this.symbol, pw.this.cluster_id, pw.this.articles_json, pw.this.headline, pw.this.needs_headline_update),
        article_count=count_articles(pw.this.articles_json),
        first_seen=pw.this.first_seen, last_updated=pw.this.last_updated
    )

    # STEP 5: Stateful Report Generation
    @pw.udf
    def clusters_to_json(t: tuple) -> str:
        return json.dumps([
            {'cluster_id': i[0], 'headline': i[1], 'article_count': i[2], 'first_seen': i[3], 'last_updated': i[4]}
            for i in t
        ])

    clusters_by_symbol = clusters_with_headlines.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        clusters_json=pw.reducers.sorted_tuple(
            pw.make_tuple(pw.this.cluster_id, pw.this.headline, pw.this.article_count, pw.this.first_seen, pw.this.last_updated)
        )
    )
    
    clusters_json_table = clusters_by_symbol.select(
        symbol=pw.this.symbol, clusters_json=clusters_to_json(pw.this.clusters_json)
    )

    @pw.reducers.stateful_many
    def stateful_report_reducer(state: Optional[dict], batch: list[tuple[list, int]]) -> dict:
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
            
            # Detect changes
            prev = state.get('cluster_states', {})
            has_changes = any(
                str(c['cluster_id']) not in prev or
                prev[str(c['cluster_id'])]['article_count'] != c['article_count'] or
                prev[str(c['cluster_id'])]['headline'] != c['headline']
                for c in clusters
            ) or any(cid not in {str(c['cluster_id']) for c in clusters} for cid in prev)
            
            if not has_changes:
                return state
            
            state['update_count'] += 1
            current_report = state.get('report') or cluster_manager._load_report(symbol)
            
            if cluster_manager.has_valid_api_key:
                new_report = cluster_manager.call_llm_sync(cluster_manager.create_report_prompt(symbol, current_report, clusters))
            else:
                company = cluster_manager.symbol_mapping.get(symbol, symbol)
                stories = "\n".join([f"- **{c['headline']}** ({c['article_count']} articles)" for c in clusters])
                new_report = f"# {company} ({symbol}) - News Report\n\n## Active Stories\n{stories}\n\n*Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*"
            
            with open(cluster_manager._get_report_path(symbol), "w", encoding="utf-8") as f:
                f.write(new_report)
            
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

            state['report'] = new_report
            state['cluster_states'] = {str(c['cluster_id']): {'headline': c['headline'], 'article_count': c['article_count']} for c in clusters}
            
        except Exception:
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

    response_table = reports_stateful.select(symbol=pw.this.symbol, response=extract_report(pw.this.report_state))

    cluster_viz_table = clusters_with_headlines.select(
        symbol=pw.this.symbol, cluster_id=pw.this.cluster_id, headline=pw.this.headline,
        article_count=pw.this.article_count, first_seen=pw.this.first_seen,
        last_updated=pw.this.last_updated, timestamp=datetime.now(timezone.utc).isoformat()
    )

    return response_table, cluster_viz_table
