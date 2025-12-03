# file: src/web_scraper.py

"""
Web Scraper for Stock Information
Uses Serpex API for Google search and scrapes content using newspaper3k
"""

import time
import os
from typing import List, Dict, Optional
from datetime import datetime
from newspaper import Article
import requests
from bs4 import BeautifulSoup


class WebScraper:
    """Scrapes web articles about stocks using Serpex API"""
    
    def __init__(self, timeout: int = 10):
        """
        Initialize web scraper with Serpex API
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.serpex_api_key = os.environ.get("SERPEX_API_KEY")
        if not self.serpex_api_key:
            raise ValueError("SERPEX_API_KEY environment variable not set")
        
        self.serpex_url = "https://api.serpex.dev/api/search"
        self.serpex_headers = {
            "Authorization": f"Bearer {self.serpex_api_key}"
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _clean_url(self, url: str) -> str:
        """Clean URL by removing tracking parameters and invalid segments."""
        if not url:
            return url
        
        # Remove Yahoo tracking parameters like /RK=2/RS=...
        import re
        url = re.sub(r'/RK=\d+/RS=[^/]+/?', '', url)
        
        # Remove double slashes (except after http://)
        url = re.sub(r'(?<!:)//+', '/', url)
        
        # Remove trailing slashes
        url = url.rstrip('/')
        
        return url
    
    def search_stock_articles(self, stock_symbol: str, company_name: str, max_results: int = 10) -> List[Dict]:
        """
        Search for articles about a stock using Serpex Google search
        
        Args:
            stock_symbol: Stock ticker (e.g., "AAPL")
            company_name: Company name (e.g., "Apple Inc")
            max_results: Maximum number of results to return (default 10)
            
        Returns:
            List of article dictionaries with metadata
        """
        print(f"\n🔍 Searching for articles about {stock_symbol} ({company_name}) using Serpex Google Search...")
        
        articles = []
        seen_urls = set()
        
        # Create comprehensive search query
        query = f"{stock_symbol} {company_name} stock news analysis"
        
        try:
            print(f"  📡 Query: '{query}'")
            
            # Use Serpex API with Google search via requests
            params = {
                'q': query,
                'engine': 'google',
                'category': 'web',
                'time_range': 'month'  # Last month
            }
            
            response = requests.get(
                self.serpex_url,
                headers=self.serpex_headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            results = response.json()
            
            # Extract search results
            search_results = results.get('results', [])
            
            print(f"  📊 Serpex returned {len(search_results)} results")
            
            for result in search_results[:max_results]:
                url = result.get('url')
                
                if not url:
                    continue
                
                # Clean the URL to remove tracking parameters
                url = self._clean_url(url)
                
                if url in seen_urls:
                    continue
                
                seen_urls.add(url)
                
                article_data = {
                    'title': result.get('title', 'No Title'),
                    'url': url,
                    'snippet': result.get('snippet', ''),
                    'source': self._extract_domain(url),
                    'position': result.get('position', 0),
                    'search_query': query,
                    'found_at': datetime.now().isoformat(),
                    'published_date': result.get('published_date')
                }
                
                articles.append(article_data)
                
                if len(articles) >= max_results:
                    break
            
        except Exception as e:
            print(f"  ⚠️  Error searching with Serpex: {e}")
            import traceback
            traceback.print_exc()
        
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
        Enhanced fallback scraping method using BeautifulSoup
        
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
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "aside", "header", "iframe", "noscript"]):
                element.decompose()
            
            # Get title - try multiple strategies
            title = None
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            elif soup.title:
                title = soup.title.string
            else:
                title = 'No Title'
            
            # Extract main content - multiple strategies
            paragraphs = []
            
            # Strategy 1: Look for article/main tags
            main_content = soup.find(['article', 'main'])
            if main_content:
                for p in main_content.find_all(['p', 'div', 'span', 'li']):
                    text = p.get_text(strip=True)
                    if len(text) > 30:  # Filter out very short snippets
                        paragraphs.append(text)
            
            # Strategy 2: Look for content divs
            if len(paragraphs) < 5:
                content_divs = soup.find_all('div', class_=lambda x: x and any(
                    keyword in str(x).lower() for keyword in ['content', 'article', 'post', 'story', 'text', 'body', 'entry']
                ))
                for div in content_divs:
                    for p in div.find_all(['p', 'li']):
                        text = p.get_text(strip=True)
                        if len(text) > 30:
                            paragraphs.append(text)
            
            # Strategy 3: Get all paragraphs if still not enough content
            if len(paragraphs) < 5:
                for p in soup.find_all('p'):
                    text = p.get_text(strip=True)
                    if len(text) > 30:
                        paragraphs.append(text)
            
            # Strategy 4: Get all divs with substantial text
            if len(paragraphs) < 5:
                for div in soup.find_all('div'):
                    text = div.get_text(strip=True)
                    # Get divs with at least 100 characters of text
                    if len(text) > 100 and len(text) < 2000:
                        # Check if it's not already captured
                        if not any(text in para for para in paragraphs):
                            paragraphs.append(text)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_paragraphs = []
            for para in paragraphs:
                if para not in seen:
                    seen.add(para)
                    unique_paragraphs.append(para)
            
            full_text = '\n\n'.join(unique_paragraphs)
            
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
                
                url = article['url']
                
                # Try newspaper3k first
                content = self.scrape_article_content(url)
                
                # Fallback to BeautifulSoup if newspaper fails or returns minimal content
                if not content or not content.get('text') or len(content.get('text', '').split()) < 50:
                    print(f"    🔄 Trying BeautifulSoup fallback...")
                    content = self.scrape_with_beautifulsoup(url)
                
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
        Search for specific topics related to the stock using Serpex
        
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
                params = {
                    'q': query,
                    'engine': 'google',
                    'category': 'web',
                    'time_range': 'month'
                }
                
                response = requests.get(
                    self.serpex_url,
                    headers=self.serpex_headers,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                results = response.json()
                
                articles = []
                for result in results.get('results', [])[:max_per_topic]:
                    articles.append({
                        'title': result.get('title', 'No Title'),
                        'url': result.get('url'),
                        'snippet': result.get('snippet', ''),
                        'source': self._extract_domain(result.get('url', '')),
                        'topic': topic
                    })
                
                topic_results[topic] = articles
                print(f"    ✅ Found {len(articles)} articles")
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"    ⚠️  Error: {e}")
                topic_results[topic] = []
        
        return topic_results
