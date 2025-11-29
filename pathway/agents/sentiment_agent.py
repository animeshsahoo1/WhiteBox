import os
import pathway as pw
from pathway.xpacks.llm.llms import LiteLLMChat
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import json
import numpy as np
from typing import Optional
import litellm

load_dotenv()


# Standalone helper functions for embeddings (used in Pathway UDFs)
def get_embedding(text: str) -> list:
    """Generate embedding for text using OpenRouter"""
    try:
        response = litellm.embedding(
            model="openai/text-embedding-3-small",
            input=[text],
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1"
        )
        return response.data[0]['embedding']  # Return as list for JSON serialization
    except Exception as e:
        return [0.0] * 1536  # Fallback


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calculate cosine similarity between two vectors"""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    if norm_product == 0:
        return 0.0
    return float(np.dot(vec1_np, vec2_np) / norm_product)


class SentimentReportUpdater:
    """Maintains and updates sentiment reports for trading agents using cluster summaries."""

    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory

        try:
            self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}"))
        except json.JSONDecodeError:
            print("Warning: Could not parse STOCK_COMPANY_MAP, using empty mapping")
            self.symbol_mapping = {}

        # Use LiteLLM with OpenRouter
        model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not model_name.startswith('openrouter/') and not model_name.startswith('openai/'):
            model_name = f'openrouter/{model_name}'
        
        # Get API key - prefer OPENROUTER_API_KEY for OpenRouter base, fallback to OPENAI_API_KEY
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("⚠️  WARNING: No OPENROUTER_API_KEY or OPENAI_API_KEY found in environment!")
            print("   Sentiment summaries will use fallback templates instead of LLM generation")
            api_key = "dummy-key-for-testing"  # Fallback to prevent immediate crash
        else:
            print(f"✅ Using API key from {'OPENROUTER_API_KEY' if os.environ.get('OPENROUTER_API_KEY') else 'OPENAI_API_KEY'}")
            
        self.llm = LiteLLMChat(
            model=model_name,
            api_key=api_key,
            api_base="https://openrouter.ai/api/v1",
            temperature=0.0,
            max_tokens=1500,
        )
        
        self.has_valid_api_key = api_key != "dummy-key-for-testing"

        os.makedirs(self.reports_directory, exist_ok=True)

    def _get_report_path(self, symbol: str) -> str:
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "sentiment_report.md")

    def _load_report(self, symbol: str) -> str:
        report_path = self._get_report_path(symbol)

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            company_name = self.symbol_mapping.get(symbol, symbol)
            initial_report = f"""# {company_name} ({symbol}) - Social Sentiment Analysis Report

## Summary
No social media data analyzed yet for {company_name}.

## Recent Sentiment Overview
*Awaiting sentiment updates...*

## Sentiment Breakdown
- **Title Sentiment**: N/A
- **Content Sentiment**: N/A
- **Comments Sentiment**: N/A
- **Overall Sentiment**: Neutral

## Key Discussion Points
*No posts analyzed yet*

## Trading Signals
- **Signal**: HOLD
- **Confidence**: N/A
- **Reasoning**: Insufficient data

---
*This report is automatically updated by the AI Trading Agent*
*Last Analysis: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(initial_report)
            return initial_report

    def _generate_cluster_summary(self, symbol: str, cluster_id: int, cluster_data: dict) -> str:
        """Generate LLM summary for a cluster of posts - focus on actual content/topics"""
        company = self.symbol_mapping.get(symbol, symbol)
        posts = cluster_data['posts'][:10]  # Use up to 10 sample posts
        
        # Format posts for LLM - remove sentiment scores from the input
        posts_text = "\n\n".join([
            f"Post {i+1}: {post['text'][:300]}"
            for i, post in enumerate(posts)
        ])
        
        prompt = f"""You are analyzing social media discussions about {company} ({symbol}). Below are posts from users discussing a similar theme/topic.

Posts in this cluster ({len(cluster_data['posts'])} total posts):
{posts_text}

Your task: Create a concise 2-3 sentence summary that captures:
1. **What specific topic/theme** are people discussing? (e.g., "product launch", "earnings report", "regulatory news", "technical analysis")
2. **What are the key points** being made? (e.g., specific features, price targets, concerns, opportunities)
3. **What narrative** is emerging from these discussions?

Focus on CONTENT and TOPICS, not sentiment labels. Be specific about what is being discussed.

Example good summaries:
- "Discussions focus on the upcoming iPhone 15 launch, with users debating whether the new USB-C port and titanium frame justify the premium pricing. Some highlight improved camera specs while others question the incremental upgrades."
- "Conversations center on Tesla's Q3 delivery numbers and production challenges at Gigafactory Berlin. Users are analyzing the impact of recent price cuts on margins and market share in Europe."
- "Community discussing Nvidia's new H100 GPU availability and its implications for AI startups. Many posts compare performance benchmarks against AMD alternatives and debate supply constraints."

BAD examples (too vague):
- "Positive discussion about Apple with bullish sentiment"
- "Users talking about the company"

Write ONLY the summary, no labels or extra formatting:"""

        try:
            # Use litellm directly for synchronous call (self.llm is Pathway's async wrapper)
            model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
            if not model_name.startswith('openrouter/') and not model_name.startswith('openai/'):
                model_name = f'openrouter/{model_name}'
            
            api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key,
                api_base="https://openrouter.ai/api/v1",
                temperature=0.0,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating cluster summary: {e}")
            return f"Discussion about {company} with {len(cluster_data['posts'])} posts on a common theme"

    def _create_report_from_summaries(
        self, symbol: str, current_report: str, cluster_summaries: list[dict]
    ) -> list[dict]:
        """Create LLM prompt to generate report from cluster summaries (not individual posts)"""

        company_name = self.symbol_mapping.get(symbol, symbol)

        system_message = f"""You are a financial analyst AI assistant specializing in social sentiment analysis for {company_name} ({symbol}).
Your task is to update the trading report by analyzing THEMATIC CLUSTERS of social media discussions.

Each cluster represents a group of similar posts discussing a common theme. You will receive:
- Cluster summaries (natural language descriptions of the main themes/narratives)
- Number of posts in each cluster

Focus on:
1. **Thematic Analysis**: Identify the main discussion themes/narratives from the summaries
2. **Sentiment Interpretation**: Infer sentiment from the language and tone of the summaries
3. **Discussion Volume**: Which themes have the most engagement
4. **Emerging Trends**: New themes or shifts in existing themes
5. **Trading Signals**: Provide clear BUY/SELL/HOLD recommendations based on thematic analysis

Keep the report concise, actionable, and well-structured in markdown format.
Focus on THEMES and their narrative context, not numerical scores or individual posts.
Always update the "Last Analysis" timestamp at the bottom.
"""

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Format cluster summaries - only include summary text and post count, no scores
        summaries_text = "\n\n".join([
            f"""**Cluster {cs['cluster_id']}** ({cs['count']} posts):
{cs['summary']}"""
            for cs in cluster_summaries
        ])

        user_message = f"""Here is the CURRENT REPORT for {company_name} ({symbol}):

{current_report}

---

Here are NEW THEMATIC CLUSTERS from social media analysis:

{summaries_text}

---

TASK: Update the report by:
1. Analyzing the main themes/narratives from the cluster summaries
2. Updating the "Recent Sentiment Overview" with thematic insights based on the narrative content
3. Updating "Sentiment Breakdown" by theme (infer sentiment from the summaries' language and tone)
4. Listing "Key Discussion Points" from the cluster themes
5. Updating "Trading Signals" with actionable BUY/SELL/HOLD based on the overall narrative sentiment
6. Updating the timestamp to: {current_time} UTC

Return ONLY the updated markdown report. Do not include explanations outside the report.
Focus on the qualitative analysis of themes rather than numerical scores."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

    def _classify_sentiment(self, score: float) -> str:
        """Classify sentiment score"""
        if score >= 0.05:
            return "Bullish 📈"
        elif score <= -0.05:
            return "Bearish 📉"
        else:
            return "Neutral ➡️"


def process_sentiment_stream(
    sentiment_table: pw.Table, reports_directory: str = "./reports/sentiment"
) -> tuple[pw.Table, pw.Table]:
    """Process sentiment stream with clustering -> summaries -> reports pipeline using Pathway tables."""

    os.makedirs(reports_directory, exist_ok=True)
    report_updater = SentimentReportUpdater(reports_directory=reports_directory)

    # STEP 1: Prepare data - combine text fields and calculate average sentiment
    @pw.udf
    def combine_text_fields(title: str, content: str, comments: str) -> str:
        """Combine text fields for clustering"""
        parts = []
        if title:
            parts.append(title)
        if content and len(content) > 10:
            parts.append(content[:500])
        if comments and len(comments) > 10:
            parts.append(comments[:300])
        result = " | ".join(parts) if parts else title or "No content"
        return result
    
    @pw.udf
    def average_sentiment(title_sent: float, content_sent: float, comments_sent: float) -> float:
        """Calculate average sentiment across all fields"""
        avg = (title_sent + content_sent + comments_sent) / 3.0
        return avg
    
    @pw.udf
    def generate_embedding(text: str) -> str:
        """Generate embedding for text (returns JSON string for storage)"""
        embedding = get_embedding(text)
        return json.dumps(embedding)

    # Enrich posts with combined text, sentiment, and embedding
    enriched_table = sentiment_table.select(
        symbol=pw.this.symbol,
        post_id=pw.this.post_id,
        combined_text=combine_text_fields(
            pw.this.post_title,
            pw.this.post_content,
            pw.this.post_comments
        ),
        avg_sentiment=average_sentiment(
            pw.this.sentiment_post_title,
            pw.this.sentiment_post_content,
            pw.this.sentiment_comments
        ),
        post_timestamp=pw.this.post_timestamp,
    )
    
    # Add embeddings
    enriched_table = enriched_table.select(
        pw.this.symbol,
        pw.this.post_id,
        pw.this.combined_text,
        pw.this.avg_sentiment,
        pw.this.post_timestamp,
        embedding=generate_embedding(pw.this.combined_text)
    )

    # STEP 2: Clustering using stateful reducer (Pathway table-based)
    @pw.reducers.stateful_many
    def cluster_assignment_reducer(
        current_state: Optional[dict], posts_batch: list[tuple[list, int]]
    ) -> dict:
        """
        Assign posts to clusters using Pathway stateful reducer.
        State stores cluster information as Pathway-managed data.
        """
        SIMILARITY_THRESHOLD = 0.75
        MERGE_THRESHOLD = 0.85
        MAX_POSTS_PER_CLUSTER = 50
        
        # Convert JSON state to Python dict if needed
        if current_state is not None and not isinstance(current_state, dict):
            try:
                # Convert Pathway Json object to dict
                current_state = json.loads(json.dumps(current_state))
            except:
                current_state = None
        
        # Initialize state if None
        if current_state is None:
            current_state = {
                'clusters': {},  # {cluster_id: cluster_data}
                'next_cluster_id': 0,
                'symbol': None
            }
        
        # Ensure we have a mutable dict
        if not isinstance(current_state, dict):
            current_state = dict(current_state)
        
        symbol = None
        new_posts = []
        
        # Collect posts from batch
        for row_values, count in posts_batch:
            if count > 0:
                for _ in range(count):
                    # row_values: [symbol, post_id, combined_text, avg_sentiment, post_timestamp, embedding]
                    if symbol is None:
                        symbol = row_values[0]
                        current_state['symbol'] = symbol
                    
                    new_posts.append({
                        'post_id': row_values[1],
                        'text': row_values[2][:500],
                        'sentiment': row_values[3],
                        'timestamp': row_values[4],
                        'embedding': json.loads(row_values[5])
                    })
        
        if not new_posts:
            return current_state
        
        clusters = current_state['clusters']
        
        # Process each new post
        for post in new_posts:
            post_embedding = post['embedding']
            best_cluster_id = None
            best_similarity = -1
            
            # Find nearest cluster
            for cluster_id, cluster_data in clusters.items():
                centroid = cluster_data['centroid']
                similarity = cosine_similarity(centroid, post_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_cluster_id = cluster_id
            
            # Assign to existing cluster or create new
            if best_similarity >= SIMILARITY_THRESHOLD and best_cluster_id is not None:
                # Update existing cluster
                cluster = clusters[best_cluster_id]
                count = cluster['count']
                
                # Incremental centroid update
                new_centroid = [
                    (cluster['centroid'][i] * count + post_embedding[i]) / (count + 1)
                    for i in range(len(post_embedding))
                ]
                cluster['centroid'] = new_centroid
                cluster['count'] += 1
                
                # Sliding window for posts
                cluster['posts'].append({
                    'text': post['text'],
                    'sentiment': post['sentiment'],
                    'timestamp': post['timestamp']
                })
                if len(cluster['posts']) > MAX_POSTS_PER_CLUSTER:
                    cluster['posts'].pop(0)
                
                # Incremental sentiment update
                cluster['avg_sentiment'] = (
                    (cluster['avg_sentiment'] * count + post['sentiment']) / (count + 1)
                )
                cluster['last_updated'] = datetime.now().isoformat()
                
            else:
                # Create new cluster
                new_cluster_id = current_state['next_cluster_id']
                clusters[new_cluster_id] = {
                    'cluster_id': new_cluster_id,
                    'centroid': post_embedding,
                    'count': 1,
                    'posts': [{
                        'text': post['text'],
                        'sentiment': post['sentiment'],
                        'timestamp': post['timestamp']
                    }],
                    'avg_sentiment': post['sentiment'],
                    'summary': None,
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
                current_state['next_cluster_id'] += 1
        
        # Cluster maintenance: merge similar clusters
        if len(clusters) > 1:
            cluster_ids = list(clusters.keys())
            i = 0
            while i < len(cluster_ids):
                if cluster_ids[i] not in clusters:
                    i += 1
                    continue
                
                cluster_i = clusters[cluster_ids[i]]
                j = i + 1
                
                while j < len(cluster_ids):
                    if cluster_ids[j] not in clusters:
                        j += 1
                        continue
                    
                    cluster_j = clusters[cluster_ids[j]]
                    similarity = cosine_similarity(cluster_i['centroid'], cluster_j['centroid'])
                    
                    if similarity >= MERGE_THRESHOLD:
                        # Merge cluster_j into cluster_i
                        total_count = cluster_i['count'] + cluster_j['count']
                        
                        # Weighted centroid merge
                        new_centroid = [
                            (cluster_i['centroid'][k] * cluster_i['count'] + 
                             cluster_j['centroid'][k] * cluster_j['count']) / total_count
                            for k in range(len(cluster_i['centroid']))
                        ]
                        cluster_i['centroid'] = new_centroid
                        cluster_i['posts'].extend(cluster_j['posts'])
                        cluster_i['posts'] = sorted(
                            cluster_i['posts'],
                            key=lambda p: p.get('timestamp', ''),
                            reverse=True
                        )[:MAX_POSTS_PER_CLUSTER]
                        
                        cluster_i['avg_sentiment'] = (
                            (cluster_i['avg_sentiment'] * cluster_i['count'] +
                             cluster_j['avg_sentiment'] * cluster_j['count']) / total_count
                        )
                        cluster_i['count'] = total_count
                        cluster_i['last_updated'] = datetime.now().isoformat()
                        cluster_i['summary'] = None  # Invalidate
                        
                        # Remove merged cluster
                        del clusters[cluster_ids[j]]
                    
                    j += 1
                i += 1
        
        # Remove old clusters
        now = datetime.now()
        to_remove = []
        for cluster_id, cluster_data in clusters.items():
            try:
                last_updated = datetime.fromisoformat(cluster_data['last_updated'])
                age_hours = (now - last_updated).total_seconds() / 3600
                
                if age_hours > 48 and cluster_data['count'] < 3:
                    to_remove.append(cluster_id)
            except:
                pass
        
        for cluster_id in to_remove:
            del clusters[cluster_id]
        
        current_state['clusters'] = clusters
        return current_state

    # Group by symbol and apply clustering
    clustered_table = enriched_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        cluster_state=cluster_assignment_reducer(
            pw.this.symbol,
            pw.this.post_id,
            pw.this.combined_text,
            pw.this.avg_sentiment,
            pw.this.post_timestamp,
            pw.this.embedding
        )
    )
    
    # STEP 3: Flatten cluster state into individual cluster rows
    @pw.udf
    def extract_cluster_id(cluster_dict: pw.Json) -> int:
        return cluster_dict["cluster_id"].as_int()
    
    @pw.udf
    def extract_summary(cluster_dict: pw.Json) -> str:
        # Use bracket notation and handle potential null/missing values
        summary = cluster_dict["summary"]
        # Check if it's null or missing
        if summary is None or summary == pw.Json.NULL:
            return ""
        return summary.as_str()
    
    @pw.udf
    def extract_avg_sentiment(cluster_dict: pw.Json) -> float:
        return cluster_dict["avg_sentiment"].as_float()
    
    @pw.udf
    def extract_count(cluster_dict: pw.Json) -> int:
        return cluster_dict["count"].as_int()
    
    @pw.udf
    def extract_posts(cluster_dict: pw.Json) -> list:
        # Convert Json array to Python list
        posts = cluster_dict["posts"]
        if posts is None or posts == pw.Json.NULL:
            return []
        # as_list() converts pw.Json array to Python list
        return posts.as_list()
    
    @pw.udf
    def extract_created_at(cluster_dict: pw.Json) -> str:
        created = cluster_dict["created_at"]
        if created is None or created == pw.Json.NULL:
            return ""
        return created.as_str()
    
    @pw.udf
    def extract_last_updated(cluster_dict: pw.Json) -> str:
        updated = cluster_dict["last_updated"]
        if updated is None or updated == pw.Json.NULL:
            return ""
        return updated.as_str()
    
    @pw.udf
    def extract_clusters(cluster_state: pw.Json) -> list:
        """Extract list of clusters from state"""
        # Convert Pathway Json to Python dict using as_dict()
        if cluster_state is None:
            return []
        
        try:
            # Convert pw.Json to Python dict
            state_dict = cluster_state.as_dict()
            
            if not state_dict or 'clusters' not in state_dict:
                return []
            
            clusters_dict = state_dict['clusters']
        except Exception as e:
            return []
        
        clusters_list = []
        
        try:
            # Iterate over cluster items (now working with plain Python dict)
            for cluster_id, cluster_data in clusters_dict.items():
                summary = cluster_data.get('summary')
                # Ensure summary is a string, not None
                if summary is None:
                    summary = ''
                
                clusters_list.append({
                    'cluster_id': int(cluster_id),
                    'summary': str(summary),
                    'avg_sentiment': float(cluster_data.get('avg_sentiment', 0.0)),
                    'count': int(cluster_data.get('count', 0)),
                    'posts': list(cluster_data.get('posts', [])),
                    'created_at': str(cluster_data.get('created_at', '')),
                    'last_updated': str(cluster_data.get('last_updated', ''))
                })
        except Exception as e:
            return []
        
        return clusters_list
    
    # Flatten to get one row per cluster
    clusters_exploded = clustered_table.select(
        symbol=pw.this.symbol,
        cluster_item=extract_clusters(pw.this.cluster_state)
    ).flatten(pw.this.cluster_item).select(
        symbol=pw.this.symbol,
        cluster_id=extract_cluster_id(pw.this.cluster_item),
        summary=extract_summary(pw.this.cluster_item),
        avg_sentiment=extract_avg_sentiment(pw.this.cluster_item),
        count=extract_count(pw.this.cluster_item),
        posts=extract_posts(pw.this.cluster_item),
        created_at=extract_created_at(pw.this.cluster_item),
        last_updated=extract_last_updated(pw.this.cluster_item)
    )
    
    # STEP 4: Generate summaries for clusters
    # Use UDF to conditionally generate or reuse summaries
    @pw.udf
    def get_cluster_summary(symbol: str, cluster_id: int, posts: list, avg_sentiment: float, current_summary: Optional[str], count: int) -> str:
        """Get cluster summary - either generate new one or reuse existing"""
        # Check if we need to generate a new summary
        needs_generation = (
            not current_summary or 
            current_summary.strip() == "" or 
            count % 10 == 0  # Regenerate every 10 posts to keep it fresh
        )
        
        if not needs_generation:
            return current_summary
        
        # Generate new summary using LLM
        
        cluster_data = {
            'posts': posts,
            'avg_sentiment': avg_sentiment
        }
        
        try:
            summary = report_updater._generate_cluster_summary(symbol, cluster_id, cluster_data)
            return summary
        except Exception as e:
            # Fallback: Create descriptive summary from post content
            company = report_updater.symbol_mapping.get(symbol, symbol)
            
            sample_posts = posts[:5]  # Use first 5 posts
            if sample_posts and len(sample_posts) > 0:
                # Extract key topics from posts
                post_texts = [post.get('text', '')[:100] for post in sample_posts if isinstance(post, dict) and post.get('text')]
                if post_texts:
                    combined = " ".join(post_texts)
                    # Create a more descriptive fallback
                    return f"Cluster discussing {company}: {combined[:200]}... ({count} posts total)"
            
            return f"Discussion cluster about {company} with {count} posts"
    
    cluster_summaries_table = clusters_exploded.select(
        symbol=pw.this.symbol,
        cluster_id=pw.this.cluster_id,
        summary=get_cluster_summary(
            pw.this.symbol,
            pw.this.cluster_id,
            pw.this.posts,
            pw.this.avg_sentiment,
            pw.this.summary,
            pw.this.count
        ),
        avg_sentiment=pw.this.avg_sentiment,
        count=pw.this.count,
        created_at=pw.this.created_at,
        last_updated=pw.this.last_updated
    )
    
    # STEP 5: Group cluster summaries by symbol to create final reports
    @pw.udf
    def collect_summaries(symbol: str, cluster_summaries_json: str) -> list:
        """Parse and collect cluster summaries for report generation"""
        try:
            summaries = json.loads(cluster_summaries_json)
            # Filter out empty summaries
            valid_summaries = [s for s in summaries if s.get('summary', '').strip()]
            
            if not valid_summaries:
                return []
            
            # Load current report
            current_report = report_updater._load_report(symbol)
            
            # Create prompt from cluster summaries
            messages = report_updater._create_report_from_summaries(
                symbol, current_report, valid_summaries
            )
            
            return messages
        except Exception as e:
            return []
    
    # Aggregate summaries by symbol
    summaries_by_symbol = cluster_summaries_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        summaries_json=pw.reducers.sorted_tuple(
            pw.make_tuple(
                pw.this.cluster_id,
                pw.this.summary,
                pw.this.avg_sentiment,
                pw.this.count
            )
        )
    )
    
    # Convert to JSON string for easier processing in UDF
    @pw.udf
    def summaries_to_json(summaries_tuple: tuple) -> str:
        summaries_list = []
        for item in summaries_tuple:
            summaries_list.append({
                'cluster_id': item[0],
                'summary': item[1],
                'avg_sentiment': item[2],
                'count': item[3]
            })
        return json.dumps(summaries_list)
    
    prompts_table = summaries_by_symbol.select(
        symbol=pw.this.symbol,
        prompts=collect_summaries(pw.this.symbol, summaries_to_json(pw.this.summaries_json))
    )
    
    # Filter out symbols with empty prompts (no valid summaries)
    @pw.udf
    def has_valid_prompts(prompts: list) -> bool:
        return prompts is not None and len(prompts) > 0
    
    filtered_prompts_table = prompts_table.filter(has_valid_prompts(pw.this.prompts))

    # STEP 6: Generate final reports via LLM and save (with alert trigger)
    # Cooldown tracking for alerts (module-level)
    _alert_cooldowns = {}
    
    @pw.udf
    def _save_report_and_alert(symbol: str, report_content: str, cluster_data_json: str) -> str:
        """Save report AND trigger BullBear alert if sentiment is outside threshold."""
        import httpx
        from datetime import datetime as dt
        
        # 1. Save report (original functionality)
        report_path = report_updater._get_report_path(symbol)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"💾 [{symbol}] Saved sentiment report")
        
        # 2. Calculate overall sentiment from cluster data and trigger alert
        try:
            clusters = json.loads(cluster_data_json)
            if clusters:
                total_weighted = sum(c['avg_sentiment'] * c['count'] for c in clusters)
                total_posts = sum(c['count'] for c in clusters)
                overall_sentiment = total_weighted / total_posts if total_posts > 0 else 0.0
                
                # Get alert config from env
                alert_min = float(os.getenv("SENTIMENT_ALERT_MIN", "-0.5"))
                alert_max = float(os.getenv("SENTIMENT_ALERT_MAX", "0.5"))
                alerts_enabled = os.getenv("SENTIMENT_ALERT_ENABLED", "true").lower() == "true"
                alert_cooldown = int(os.getenv("SENTIMENT_ALERT_COOLDOWN", "300"))
                bullbear_url = os.getenv("BULLBEAR_API_URL", "http://localhost:8000")
                
                if alerts_enabled and (overall_sentiment < alert_min or overall_sentiment > alert_max):
                    # Check cooldown
                    now = dt.now()
                    last = _alert_cooldowns.get(symbol)
                    if not last or (now - last).total_seconds() >= alert_cooldown:
                        direction = "bearish" if overall_sentiment < alert_min else "bullish"
                        print(f"🚨 [{symbol}] Triggering BullBear alert ({direction}, sentiment={overall_sentiment:.3f})")
                        try:
                            response = httpx.post(
                                f"{bullbear_url}/debate/{symbol}",
                                json={"max_rounds": 2, "background": True},
                                timeout=10.0
                            )
                            _alert_cooldowns[symbol] = now
                        except Exception:
                            pass
        except Exception:
            pass
        
        return report_content
    
    # Generate reports conditionally based on API key availability
    if report_updater.has_valid_api_key:
        response_table = filtered_prompts_table.join(
            summaries_by_symbol, pw.left.symbol == pw.right.symbol
        ).select(
            symbol=pw.left.symbol,
            response=_save_report_and_alert(
                pw.left.symbol, 
                report_updater.llm(pw.left.prompts),
                summaries_to_json(pw.right.summaries_json)
            )
        )
    else:
        @pw.udf
        def generate_basic_report(symbol: str, prompts: list) -> str:
            """Generate a basic report without LLM when no API key is available"""
            company = report_updater.symbol_mapping.get(symbol, symbol)
            return f"# {company} ({symbol}) - Sentiment Report\n\nBasic sentiment tracking enabled.\n\nNote: LLM analysis unavailable (no API key configured)."
        
        response_table = filtered_prompts_table.join(
            summaries_by_symbol, pw.left.symbol == pw.right.symbol
        ).select(
            symbol=pw.left.symbol,
            response=_save_report_and_alert(
                pw.left.symbol,
                generate_basic_report(pw.left.symbol, pw.left.prompts),
                summaries_to_json(pw.right.summaries_json)
            )
        )
    
    # STEP 7: Create visualization table (separate from reports)
    cluster_viz_table = cluster_summaries_table.select(
        symbol=pw.this.symbol,
        cluster_id=pw.this.cluster_id,
        summary=pw.this.summary,
        avg_sentiment=pw.this.avg_sentiment,
        count=pw.this.count,
        timestamp=datetime.now().isoformat()
    )

    return response_table, cluster_viz_table