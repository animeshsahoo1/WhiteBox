"""
Web search functionality using Serpex API with DuckDuckGo fallback.
Includes smart search with query decomposition and result aggregation.
"""

import asyncio
import json
import re
import html as html_module
from typing import List, Dict, Any
from urllib.parse import quote_plus

import httpx

from config import (
    SERPEX_API_KEY,
    SERPEX_BASE_URL,
    TRUSTED_TRADING_SITES,
    SITE_SEARCH_DOMAINS,
    BLOCKED_DOMAINS,
    TRADING_RELEVANCE_KEYWORDS,
    OPENAI_MODEL_RISK,
    openai_client
)


# ============================================================================
# QUERY ENHANCEMENT UTILITIES
# ============================================================================

def build_site_specific_query(query: str, sites: List[str] = None) -> str:
    """
    Build a query with site-specific operators for better results.
    
    Args:
        query: Original search query
        sites: List of domains to search (uses SITE_SEARCH_DOMAINS if None)
    
    Returns:
        Enhanced query with site: operators
    """
    if sites is None:
        sites = SITE_SEARCH_DOMAINS[:3]  # Use top 3 sites
    
    site_operators = " OR ".join([f"site:{site}" for site in sites])
    return f"{query} ({site_operators})"


def enhance_trading_query(query: str, search_type: str = "trading") -> str:
    """
    Intelligently enhance a trading query without over-stuffing keywords.
    
    Args:
        query: Original query
        search_type: Type of search (trading, code, news, general)
    
    Returns:
        Enhanced query string
    """
    query_lower = query.lower()
    
    if search_type == "trading":
        additions = []
        
        # Only add if query is missing key trading context
        has_trading_term = any(term in query_lower for term in ["trading", "strategy", "trade", "trader"])
        has_indicator = any(ind in query_lower for ind in ["rsi", "macd", "sma", "ema", "bollinger", "stochastic", "adx"])
        has_action = any(act in query_lower for act in ["buy", "sell", "entry", "exit", "signal"])
        
        if not has_trading_term and not has_action:
            additions.append("trading strategy")
        
        # Don't add "stock market" if query is specific enough
        if not has_indicator and "backtest" not in query_lower:
            pass  # Let the query be more focused
        
        enhanced = f"{query} {' '.join(additions)}".strip()
        return enhanced
        
    elif search_type == "code":
        if "python" not in query_lower:
            return f"{query} python implementation"
        return query
        
    elif search_type == "news":
        return f"{query} financial news analysis"
        
    return query


# ============================================================================
# CONTENT VALIDATION UTILITIES
# ============================================================================

def is_blocked_domain(url: str) -> bool:
    """
    Check if URL is from a blocked domain.
    Also filters search engine result pages (but allows their content pages).
    """
    url_lower = url.lower()
    
    # Check blocked domains
    if any(domain in url_lower for domain in BLOCKED_DOMAINS):
        return True
    
    # Filter search engine RESULT pages (not their content)
    search_result_patterns = [
        "google.com/search",
        "bing.com/search",
        "yahoo.com/search",
        "duckduckgo.com/?q=",
        "/search?q=",
        "/search?p=",
    ]
    if any(pattern in url_lower for pattern in search_result_patterns):
        return True
    
    return False


def calculate_relevance_score(result: Dict, query: str) -> float:
    """
    Calculate a relevance score for a search result based on content matching.
    
    Args:
        result: Search result dict with title, snippet, url
        query: Original search query
    
    Returns:
        Relevance score between 0.0 and 1.0
    """
    score = 0.0
    max_score = 0.0
    
    title = (result.get("title", "") or "").lower()
    snippet = (result.get("snippet", "") or "").lower()
    url = (result.get("url", "") or "").lower()
    source = (result.get("source", "") or "").lower()
    
    content = f"{title} {snippet}"
    query_terms = query.lower().split()
    
    # 1. Query term matching (40% weight)
    max_score += 0.4
    query_matches = sum(1 for term in query_terms if term in content and len(term) > 2)
    if query_terms:
        score += 0.4 * (query_matches / len(query_terms))
    
    # 2. Trading keyword presence (30% weight)
    max_score += 0.3
    keyword_matches = sum(1 for kw in TRADING_RELEVANCE_KEYWORDS if kw in content)
    score += 0.3 * min(1.0, keyword_matches / 5)  # Cap at 5 keywords
    
    # 3. Trusted source bonus (20% weight)
    max_score += 0.2
    for i, trusted_site in enumerate(TRUSTED_TRADING_SITES):
        if trusted_site in source or trusted_site in url:
            # Higher bonus for higher-ranked trusted sites
            score += 0.2 * (1 - i / len(TRUSTED_TRADING_SITES))
            break
    
    # 4. Title relevance bonus (10% weight)
    max_score += 0.1
    title_query_match = sum(1 for term in query_terms if term in title and len(term) > 2)
    if query_terms:
        score += 0.1 * (title_query_match / len(query_terms))
    
    return min(1.0, score / max_score) if max_score > 0 else 0.0


def validate_result(result: Dict, query: str, min_relevance: float = 0.2) -> Dict:
    """
    Validate and enrich a search result with relevance scoring.
    
    Args:
        result: Search result dict
        query: Original query for relevance calculation
        min_relevance: Minimum relevance score to pass validation
    
    Returns:
        Result dict with added validation fields, or None if filtered
    """
    url = result.get("url", "")
    
    # Filter blocked domains
    if is_blocked_domain(url):
        return None
    
    # Calculate relevance score
    relevance = calculate_relevance_score(result, query)
    result["relevance_score"] = round(relevance, 3)
    
    # Filter low relevance results
    if relevance < min_relevance:
        return None
    
    # Add quality indicators
    result["is_trusted_source"] = any(
        site in result.get("source", "").lower() 
        for site in TRUSTED_TRADING_SITES
    )
    
    return result


async def validate_results_batch(
    results: List[Dict], 
    query: str,
    min_relevance: float = 0.15
) -> List[Dict]:
    """
    Validate a batch of results and return only relevant ones.
    
    Args:
        results: List of search results
        query: Original query
        min_relevance: Minimum relevance threshold
    
    Returns:
        Filtered and sorted list of validated results
    """
    validated = []
    
    for result in results:
        validated_result = validate_result(result, query, min_relevance)
        if validated_result:
            validated.append(validated_result)
    
    # Sort by relevance score (highest first)
    validated.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    
    return validated


# ============================================================================
# DUCKDUCKGO FALLBACK SEARCH
# ============================================================================

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


async def duckduckgo_search(
    query: str,
    num_results: int = 10,
    search_type: str = "trading",
    use_site_search: bool = False
) -> List[Dict]:
    """
    Fallback search using DuckDuckGo HTML interface.
    
    Args:
        query: Search query
        num_results: Number of results to fetch
        search_type: Type of search for query enhancement
        use_site_search: Whether to add site-specific operators
    
    Returns:
        List of search results
    """
    # Use enhanced query builder
    enhanced_query = enhance_trading_query(query, search_type)
    
    # Optionally add site-specific search
    if use_site_search:
        enhanced_query = build_site_specific_query(enhanced_query)
    
    print(f"[DEBUG] DuckDuckGo query: '{enhanced_query}'")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http_client:
            # DuckDuckGo HTML search
            response = await http_client.post(
                DUCKDUCKGO_URL,
                data={"q": enhanced_query, "b": ""},
                headers=headers
            )
            
            if response.status_code != 200:
                return [{"error": f"DuckDuckGo returned status {response.status_code}"}]
            
            html = response.text
            results = []
            
            # Parse results using regex (avoid external HTML parser dependency)
            # DuckDuckGo HTML results are in <a class="result__a" href="...">
            result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>'
            
            # Find all result links
            links = re.findall(result_pattern, html, re.IGNORECASE)
            snippets = re.findall(snippet_pattern, html, re.IGNORECASE | re.DOTALL)
            
            for i, (url, title) in enumerate(links[:num_results + 5]):  # Fetch extra to filter ads
                # Skip DuckDuckGo ads (URLs containing y.js?ad_domain or duckduckgo.com/y.js)
                if "duckduckgo.com/y.js" in url or "ad_domain=" in url or "/y.js?" in url:
                    continue
                
                # Clean up the URL (DuckDuckGo wraps URLs)
                if "uddg=" in url:
                    # Extract actual URL from DuckDuckGo redirect
                    url_match = re.search(r'uddg=([^&]+)', url)
                    if url_match:
                        from urllib.parse import unquote
                        url = unquote(url_match.group(1))
                
                # Skip if still a DuckDuckGo internal URL after cleanup
                if "duckduckgo.com" in url:
                    continue
                
                # Get snippet if available
                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r'<[^>]+>', '', snippets[i])  # Strip HTML tags
                    snippet = html_module.unescape(snippet).strip()
                
                # Extract domain
                try:
                    domain = url.split("/")[2] if url.startswith("http") else "unknown"
                except:
                    domain = "unknown"
                
                results.append({
                    "title": html_module.unescape(title.strip()),
                    "url": url,
                    "snippet": snippet or "No description available",
                    "source": domain,
                    "position": len(results) + 1,
                    "search_engine": "DuckDuckGo"
                })
                
                # Stop once we have enough results
                if len(results) >= num_results:
                    break
            
            if not results:
                return [{"error": "No results found from DuckDuckGo"}]
            
            return results
            
    except httpx.TimeoutException:
        return [{"error": "DuckDuckGo request timed out"}]
    except Exception as e:
        return [{"error": f"DuckDuckGo search failed: {type(e).__name__}: {str(e)}"}]


# ============================================================================
# SERPEX SEARCH (PRIMARY)
# ============================================================================


async def serpex_search(
    query: str,
    num_results: int = 10,
    search_type: str = "trading",
    category: str = "web"
) -> List[Dict]:
    """
    Perform a search using Serpex API (https://api.serpex.dev).
    
    Args:
        query: Search query
        num_results: Number of results to fetch
        search_type: Type of search - "trading", "code", "news", "general"
        category: Serpex category - "web", "news", "images"
    
    Returns:
        List of search results
    """
    if not SERPEX_API_KEY:
        return [{"error": "SERPAPI_API_KEY not configured. Set it in .env file."}]
    
    # Use enhanced query builder
    enhanced_query = enhance_trading_query(query, search_type)
    
    if search_type == "news":
        category = "news"
    
    print(f"[DEBUG] Serpex enhanced query: '{enhanced_query}'")
    
    headers = {
        "Authorization": f"Bearer {SERPEX_API_KEY}"
    }
    
    params = {
        "q": enhanced_query,
        "engine": "auto",
        "category": category,
        "num": num_results
    }
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            response = await http_client.get(SERPEX_BASE_URL, headers=headers, params=params)
            
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f" - {error_data.get('message', error_data.get('error', response.text[:200]))}"
                except:
                    error_detail = f" - {response.text[:200]}"
                return [{"error": f"Serpex returned status {response.status_code}{error_detail}"}]
            
            data = response.json()
            results = []
            
            # Extract organic/web results from Serpex response
            organic_results = data.get("organic_results", data.get("results", data.get("web_results", [])))
            
            for i, item in enumerate(organic_results):
                results.append({
                    "title": item.get("title", "No title"),
                    "url": item.get("link", item.get("url", "")),
                    "snippet": item.get("snippet", item.get("description", "No description")),
                    "source": (item.get("link", item.get("url", "")).split("/")[2] 
                              if item.get("link", item.get("url")) else "unknown"),
                    "position": item.get("position", i + 1),
                    "date": item.get("date", "")
                })
            
            # Include knowledge graph if available
            kg = data.get("knowledge_graph", data.get("knowledgeGraph", {}))
            if kg and kg.get("description"):
                results.insert(0, {
                    "title": kg.get("title", "Knowledge Graph"),
                    "url": kg.get("website", kg.get("url", "")),
                    "snippet": kg.get("description", ""),
                    "source": "Knowledge Graph",
                    "position": 0,
                    "is_knowledge_graph": True
                })
            
            # Include answer box if available
            ab = data.get("answer_box", data.get("answerBox", {}))
            if ab:
                answer_text = ab.get("answer") or ab.get("snippet") or ab.get("title", "")
                if answer_text:
                    results.insert(0, {
                        "title": ab.get("title", "Answer"),
                        "url": ab.get("link", ab.get("url", "")),
                        "snippet": answer_text,
                        "source": "Answer Box",
                        "position": 0,
                        "is_answer_box": True
                    })
            
            return results
            
    except httpx.TimeoutException:
        return [{"error": "Serpex request timed out"}]
    except httpx.RequestError as e:
        return [{"error": f"Serpex request failed: {type(e).__name__}: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Serpex request failed: {type(e).__name__}: {str(e)}"}]


# ============================================================================
# UNIFIED SEARCH WITH FALLBACK
# ============================================================================

async def web_search(
    query: str,
    num_results: int = 10,
    search_type: str = "trading",
    category: str = "web"
) -> List[Dict]:
    """
    Unified web search that tries Serpex first, then falls back to DuckDuckGo.
    
    Args:
        query: Search query
        num_results: Number of results to fetch
        search_type: Type of search - "trading", "code", "news", "general"
        category: Search category (for Serpex)
    
    Returns:
        List of search results with 'search_engine' field indicating source
    """
    # Try Serpex first if configured
    if SERPEX_API_KEY:
        print(f"[INFO] Trying Serpex search...")
        results = await serpex_search(query, num_results, search_type, category)
        
        # Check if Serpex succeeded
        if results and "error" not in results[0]:
            for r in results:
                r["search_engine"] = "Serpex"
            return results
        else:
            print(f"[WARN] Serpex failed: {results[0].get('error', 'Unknown error')}, falling back to DuckDuckGo")
    else:
        print(f"[INFO] Serpex not configured, using DuckDuckGo")
    
    # Fallback to DuckDuckGo
    print(f"[INFO] Using DuckDuckGo fallback...")
    results = await duckduckgo_search(query, num_results, search_type)
    return results


async def decompose_query_with_llm(query: str) -> List[str]:
    """Use LLM to decompose a complex trading query into focused sub-queries."""
    
    prompt = f"""You are a trading strategy research assistant. Break down this query into 2-4 focused, specific search queries that will find relevant trading strategy information.

User Query: "{query}"

Rules:
1. Each sub-query should focus on ONE specific aspect
2. Include specific trading terms (RSI, MACD, SMA, backtest, etc.) when relevant
3. Make queries specific enough to get trading-related results, not generic web results
4. Add "trading strategy" or "stock market" to queries that might be ambiguous

Return ONLY a JSON array of strings, nothing else:
["query1", "query2", "query3"]"""

    try:
        response = await openai_client.chat.completions.create(
            model=OPENAI_MODEL_RISK,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON array
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            queries = json.loads(json_match.group())
            return [str(q) for q in queries if q][:4]
        
        return [query]
        
    except Exception as e:
        print(f"[WARN] Query decomposition failed: {e}")
        return [query]


async def aggregate_search_results(all_results: List[Dict], original_query: str) -> List[Dict]:
    """Deduplicate and rank aggregated search results."""
    
    seen_urls = set()
    unique_results = []
    
    for result in all_results:
        url = result.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    def get_score(result):
        source = result.get("source", "").lower()
        position = result.get("position", 99)
        
        for i, site in enumerate(TRUSTED_TRADING_SITES):
            if site in source:
                return (i, position)
        return (len(TRUSTED_TRADING_SITES), position)
    
    unique_results.sort(key=get_score)
    return unique_results


async def fetch_page_content(url: str, max_length: int = 2500) -> Dict:
    """Fetch and extract content from a web page."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http_client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9"
            }
            response = await http_client.get(url, headers=headers)
            
            if response.status_code != 200:
                return {"url": url, "error": f"HTTP {response.status_code}"}
            
            html = response.text
            
            # Extract title
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = html_module.unescape(title_match.group(1).strip()) if title_match else "No title"
            
            # Clean HTML
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
            html = re.sub(r'<(nav|header|footer|aside)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
            
            # Try to find main content
            main_content = ""
            for pattern in [
                r'<article[^>]*>(.*?)</article>',
                r'<main[^>]*>(.*?)</main>',
                r'<div[^>]*class="[^"]*(?:content|article|post)[^"]*"[^>]*>(.*?)</div>',
            ]:
                match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                if match and len(match.group(1)) > len(main_content):
                    main_content = match.group(1)
            
            if not main_content:
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
                main_content = body_match.group(1) if body_match else html
            
            # Clean to text
            text = re.sub(r'<[^>]+>', ' ', main_content)
            text = re.sub(r'\s+', ' ', text).strip()
            text = html_module.unescape(text)
            
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return {"url": url, "title": title, "content": text}
            
    except Exception as e:
        return {"url": url, "error": str(e)}


async def smart_search(
    query: str,
    max_results: int = 6,
    fetch_content: bool = True,
    content_max_length: int = 2500
) -> Dict[str, Any]:
    """
    Smart search that decomposes queries, searches in parallel, and aggregates results.
    Uses Serpex with DuckDuckGo fallback.
    
    Args:
        query: Search query
        max_results: Maximum results to return
        fetch_content: Whether to fetch page content
        content_max_length: Max characters per page
    
    Returns:
        Dictionary with search results and metadata
    """
    print(f"[INFO] Smart search: '{query}'")
    
    try:
        # Step 1: Decompose query using LLM
        print("[INFO] Step 1: Decomposing query...")
        sub_queries = await decompose_query_with_llm(query)
        print(f"[INFO] Decomposed into {len(sub_queries)} sub-queries: {sub_queries}")
        
        # Step 2: Search all sub-queries in parallel (with fallback)
        print("[INFO] Step 2: Searching in parallel...")
        search_tasks = [
            web_search(sq, num_results=8, search_type="trading")  # Fetch more to allow filtering
            for sq in sub_queries
        ]
        all_search_results = await asyncio.gather(*search_tasks)
        
        # Determine which search engine was used
        search_engine_used = "Unknown"
        
        # Flatten results
        flat_results = []
        for i, results in enumerate(all_search_results):
            if results and "error" not in results[0]:
                for r in results:
                    r["source_query"] = sub_queries[i]
                    flat_results.append(r)
                    if "search_engine" in r:
                        search_engine_used = r["search_engine"]
        
        # Step 3: Aggregate and deduplicate
        print("[INFO] Step 3: Aggregating results...")
        aggregated = await aggregate_search_results(flat_results, query)
        
        # Step 4: Content validation - filter and score results
        print("[INFO] Step 4: Validating content relevance...")
        validated_results = await validate_results_batch(aggregated, query, min_relevance=0.15)
        
        print(f"[INFO] Found {len(flat_results)} total, {len(aggregated)} unique, {len(validated_results)} validated")
        
        top_results = validated_results[:max_results]
        
        # Step 5: Fetch content from top results in parallel
        fetched_content = []
        if fetch_content and top_results:
            print("[INFO] Step 5: Fetching page content...")
            urls_to_fetch = [r["url"] for r in top_results[:4] if r.get("url")]
            fetch_tasks = [fetch_page_content(url, content_max_length) for url in urls_to_fetch]
            fetched_content = await asyncio.gather(*fetch_tasks)
        
        # Build response
        response = {
            "original_query": query,
            "decomposed_queries": sub_queries,
            "total_results_found": len(flat_results),
            "unique_results": len(aggregated),
            "validated_results": len(validated_results),
            "results": top_results,
            "search_engine": f"{search_engine_used} (Smart Search)",
            "quality_note": "Results filtered by relevance scoring and trusted sources"
        }
        
        if fetched_content:
            response["fetched_pages"] = fetched_content
            response["pages_with_content"] = len([c for c in fetched_content if "content" in c])
        
        return response
        
    except Exception as e:
        return {
            "error": f"Smart search failed: {str(e)}",
            "query": query
        }
