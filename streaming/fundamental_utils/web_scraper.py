# file: src/web_scraper.py

"""
Web Scraper for Stock Information
Uses DDGS (Dux Distributed Global Search) to find articles and scrapes content using newspaper3k
"""

import time
from typing import List, Dict, Optional
from datetime import datetime
from ddgs import DDGS
from newspaper import Article
import requests
from bs4 import BeautifulSoup


class WebScraper:
    """Scrapes web articles about stocks using DDGS metasearch"""
    
    def __init__(self, proxy: Optional[str] = None, timeout: int = 10):
        """
        Initialize web scraper with DDGS
        
        Args:
            proxy: Optional proxy (e.g., "tb" for Tor, "socks5h://host:port", etc.)
            timeout: Request timeout in seconds
        """
        self.proxy = proxy
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def search_stock_articles(self, stock_symbol: str, company_name: str, max_results: int = 10) -> List[Dict]:
        """
        Search for articles about a stock using DDGS metasearch
        
        Args:
            stock_symbol: Stock ticker (e.g., "AAPL")
            company_name: Company name (e.g., "Apple Inc")
            max_results: Maximum number of results to return
            
        Returns:
            List of article dictionaries with metadata
        """
        print(f"\n🔍 Searching for articles about {stock_symbol} ({company_name})...")
        
        articles = []
        seen_urls = set()
        
        # Create search queries - prioritize news and analysis
        queries = [
            f"{stock_symbol} stock news",
            f"{company_name} financial news",
            f"{stock_symbol} analysis",
        ]
        
        # Use DDGS with proper initialization
        ddgs = DDGS(proxy=self.proxy, timeout=self.timeout)
        
        for query in queries:
            try:
                print(f"  📡 Query: '{query}'")
                
                # Use text search with news backend preference
                results = ddgs.text(
                    query=query,
                    region="us-en",
                    safesearch="moderate",
                    timelimit="m",  # Last month
                    max_results=max_results // len(queries) + 1,
                    page=1,
                    backend="auto"  # Let DDGS handle backend selection
                )
                
                for result in results:
                    url = result.get('href') or result.get('url')
                    
                    if not url:
                        continue
                    
                    # Skip duplicates
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    article_data = {
                        'title': result.get('title', 'No Title'),
                        'url': url,
                        'snippet': result.get('body', ''),
                        'source': self._extract_domain(url),
                        'search_query': query,
                        'found_at': datetime.now().isoformat()
                    }
                    
                    articles.append(article_data)
                    
                    if len(articles) >= max_results:
                        break
                
                # Small delay between queries
                time.sleep(1)
                
            except Exception as e:
                print(f"  ⚠️  Error searching with query '{query}': {e}")
                # Don't continue on first error - try news search as fallback
                continue
            
            if len(articles) >= max_results:
                break
        
        # If we don't have enough articles, try news search
        if len(articles) < max_results:
            try:
                print(f"  📰 Trying news search for {stock_symbol}...")
                news_results = ddgs.news(
                    query=f"{stock_symbol} OR {company_name}",
                    region="us-en",
                    safesearch="moderate",
                    timelimit="m",
                    max_results=max_results - len(articles),
                    page=1,
                    backend="auto"
                )
                
                for result in news_results:
                    url = result.get('url') or result.get('href')
                    
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    article_data = {
                        'title': result.get('title', 'No Title'),
                        'url': url,
                        'snippet': result.get('body', ''),
                        'source': result.get('source', self._extract_domain(url)),
                        'search_query': 'news_search',
                        'found_at': datetime.now().isoformat(),
                        'published_date': result.get('date', '')
                    }
                    
                    articles.append(article_data)
                    
                    if len(articles) >= max_results:
                        break
                        
            except Exception as e:
                print(f"  ⚠️  News search failed: {e}")
        
        print(f"  ✅ Found {len(articles)} articles")
        return articles[:max_results]
    
    def scrape_article_content(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """
        Scrape full content from an article URL using newspaper3k
        
        Args:
            url: Article URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with scraped content or None if failed
        """
        try:
            article = Article(url)
            article.download()
            article.parse()
            
            # Try to extract publish date
            try:
                article.nlp()
            except:
                pass  # NLP features are optional
            
            content = {
                'url': url,
                'title': article.title,
                'text': article.text,
                'authors': article.authors,
                'publish_date': article.publish_date.isoformat() if article.publish_date else None,
                'top_image': article.top_image,
                'summary': article.summary if hasattr(article, 'summary') else '',
                'word_count': len(article.text.split()) if article.text else 0,
                'scraped_at': datetime.now().isoformat()
            }
            
            return content
            
        except Exception as e:
            print(f"  ⚠️  Failed to scrape {url}: {e}")
            return None
    
    def scrape_with_beautifulsoup(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """
        Fallback scraping method using BeautifulSoup
        
        Args:
            url: Article URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with scraped content or None if failed
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "aside"]):
                script.decompose()
            
            # Get title
            title = soup.find('h1')
            title = title.get_text(strip=True) if title else soup.title.string if soup.title else 'No Title'
            
            # Get main content - try common article tags
            content_tags = soup.find_all(['article', 'main', 'div'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['content', 'article', 'post', 'story', 'text']
            ))
            
            # Fallback to all paragraphs if no content container found
            if not content_tags:
                content_tags = [soup]
            
            # Extract text from paragraphs
            paragraphs = []
            for tag in content_tags:
                for p in tag.find_all('p'):
                    text = p.get_text(strip=True)
                    if len(text) > 50:  # Filter out short/navigation paragraphs
                        paragraphs.append(text)
            
            full_text = '\n\n'.join(paragraphs)
            
            content = {
                'url': url,
                'title': title,
                'text': full_text,
                'word_count': len(full_text.split()),
                'scraped_at': datetime.now().isoformat(),
                'method': 'beautifulsoup'
            }
            
            return content
            
        except Exception as e:
            print(f"  ⚠️  BeautifulSoup scraping failed for {url}: {e}")
            return None
    
    def gather_stock_intelligence(self, stock_symbol: str, company_name: str, 
                                  max_articles: int = 10, scrape_full: bool = True) -> Dict:
        """
        Comprehensive intelligence gathering about a stock
        
        Args:
            stock_symbol: Stock ticker
            company_name: Company name
            max_articles: Maximum number of articles to find
            scrape_full: Whether to scrape full article content
            
        Returns:
            Dictionary with all gathered intelligence
        """
        print(f"\n{'='*70}")
        print(f"🕵️  Gathering Web Intelligence for {stock_symbol} ({company_name})")
        print(f"{'='*70}")
        
        # Search for articles
        articles = self.search_stock_articles(stock_symbol, company_name, max_articles)
        
        # Scrape full content if requested
        if scrape_full:
            print(f"\n📰 Scraping full article content...")
            scraped_articles = []
            
            for i, article in enumerate(articles, 1):
                print(f"  [{i}/{len(articles)}] Scraping: {article['title'][:60]}...")
                
                # Try newspaper3k first
                content = self.scrape_article_content(article['url'])
                
                # Fallback to BeautifulSoup if newspaper fails
                if not content or not content.get('text'):
                    content = self.scrape_with_beautifulsoup(article['url'])
                
                if content:
                    # Merge metadata from search with scraped content
                    article.update(content)
                    scraped_articles.append(article)
                    print(f"    ✅ Scraped {content.get('word_count', 0)} words")
                else:
                    # Keep the article with just snippet if scraping failed
                    scraped_articles.append(article)
                    print(f"    ⚠️  Using search snippet only")
                
                # Rate limiting
                time.sleep(1)
            
            articles = scraped_articles
        
        # Organize the data
        intelligence = {
            'stock_symbol': stock_symbol,
            'company_name': company_name,
            'gathered_at': datetime.now().isoformat(),
            'total_articles': len(articles),
            'articles': articles,
            'sources': list(set(article.get('source', 'Unknown') for article in articles)),
            'total_words_scraped': sum(article.get('word_count', 0) for article in articles)
        }
        
        print(f"\n{'='*70}")
        print(f"✅ Intelligence Gathering Complete")
        print(f"   Articles found: {intelligence['total_articles']}")
        print(f"   Unique sources: {len(intelligence['sources'])}")
        print(f"   Total words scraped: {intelligence['total_words_scraped']:,}")
        print(f"{'='*70}\n")
        
        return intelligence
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return 'Unknown'
    
    def search_specific_topics(self, stock_symbol: str, company_name: str, 
                              topics: List[str], max_per_topic: int = 3) -> Dict:
        """
        Search for specific topics related to the stock
        
        Args:
            stock_symbol: Stock ticker
            company_name: Company name
            topics: List of specific topics to search (e.g., ["earnings", "lawsuit", "partnership"])
            max_per_topic: Maximum articles per topic
            
        Returns:
            Dictionary organized by topics
        """
        print(f"\n🎯 Searching specific topics for {stock_symbol}...")
        
        topic_results = {}
        
        for topic in topics:
            query = f"{stock_symbol} {company_name} {topic}"
            print(f"  📌 Topic: {topic}")
            
            try:
                results = self.ddgs.text(query, max_results=max_per_topic)
                
                articles = []
                for result in results:
                    articles.append({
                        'title': result.get('title', 'No Title'),
                        'url': result.get('href') or result.get('link'),
                        'snippet': result.get('body', ''),
                        'source': self._extract_domain(result.get('href') or result.get('link')),
                        'topic': topic
                    })
                
                topic_results[topic] = articles
                print(f"    ✅ Found {len(articles)} articles")
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"    ⚠️  Error: {e}")
                topic_results[topic] = []
        
        return topic_results
