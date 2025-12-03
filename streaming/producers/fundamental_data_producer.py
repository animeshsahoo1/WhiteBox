# file: producers/fundamental_data_producer.py

"""
Fundamental Data Producer
Fetches comprehensive fundamental analysis data from FMP API and streams to Kafka.
ONLY handles raw data extraction and streaming - NO report generation.
"""

import os
from typing import Optional, Dict
from dotenv import load_dotenv

from producers.base_producer import BaseProducer
from utils.fmp_api_client import FmpApiClient
from utils.web_scraper import WebScraper

load_dotenv()

class FundamentalDataProducer(BaseProducer):
    """Producer for comprehensive fundamental analysis data - raw streaming only."""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,MSFT,GOOG').split(',')
        fetch_interval = int(os.getenv('FUNDAMENTAL_DATA_INTERVAL', '3600'))
        
        super().__init__(
            kafka_topic='fundamental-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        self.fmp_client = None
        
        # Initialize WebScraper
        self.web_scraper = None
        try:
            self.web_scraper = WebScraper(timeout=int(os.getenv('SCRAPER_TIMEOUT', '10')))
            self.enable_web_scraping = True
            print("✅ Web Scraper (Serpex) initialized successfully")
        except Exception as e:
            print(f"⚠️  Web Scraper initialization failed: {e}")
            print("   Web scraping will be disabled. Set SERPEX_API_KEY to enable.")
            self.enable_web_scraping = False
        
        # Configuration
        self.max_articles_per_stock = int(os.getenv('MAX_ARTICLES_PER_STOCK', '10'))
    
    def setup_sources(self):
        """Setup FMP as the primary data source for fundamentals."""
        try:
            # Initialize FMP client
            self.fmp_client = FmpApiClient()
            self.register_source("FMP", self._fetch_from_fmp, priority=0)
            
        except ValueError as e:
            print(f"  ❌ Critical Error: Could not initialize FMP client. {e}")
            print("     Please ensure FMP_API_KEY is set in your .env file.")
    
    def _fetch_from_fmp(self, stock_symbol: str) -> Optional[Dict]:
        """
        Fetches comprehensive fundamental data from FMP and prepares for Kafka streaming.
        
        Args:
            stock_symbol: The stock ticker to fetch data for.
            
        Returns:
            A dictionary with raw data ready for Kafka, or None if an error occurs.
        """
        if not self.fmp_client:
            print(f"❌ FMP client not initialized. Cannot fetch data for {stock_symbol}.")
            return None

        try:
            # Step 1: Gather all raw fundamental data from FMP API
            raw_data = self.fmp_client.gather_all_fundamental_data(stock_symbol)
            
            if not raw_data.get('profile'):
                print(f"  ⚠️  Could not retrieve core profile for {stock_symbol}. Aborting fetch.")
                return None

            print(f"  ✅ Successfully gathered FMP data for {stock_symbol}")
            
            # Step 2: Optionally scrape web articles using Serpex
            web_intelligence = None
            if self.enable_web_scraping and self.web_scraper:
                try:
                    company_name = raw_data['profile'].get('companyName', stock_symbol)
                    print(f"\n  🕷️  Scraping web articles for {stock_symbol} using Serpex...")
                    
                    web_intelligence = self.web_scraper.gather_stock_intelligence(
                        stock_symbol=stock_symbol, 
                        company_name=company_name,
                        max_articles=self.max_articles_per_stock,
                        scrape_full=True
                    )
                    
                    print(f"  ✅ Scraped {web_intelligence['total_articles']} articles ({web_intelligence['total_words_scraped']:,} words)")
                    
                except Exception as e:
                    print(f"  ⚠️  Web scraping failed: {e}")
                    import traceback
                    traceback.print_exc()
                    web_intelligence = None
            
            # Step 3: Combine raw data and web intelligence for Kafka
            # Add web intelligence to the data structure
            if web_intelligence:
                raw_data['web_intelligence'] = web_intelligence
            
            print(f"  ✅ Raw data prepared for Kafka streaming: {stock_symbol}")
            
            return raw_data  # Return raw data for Kafka streaming
            
        except Exception as e:
            print(f"❌ An unexpected error occurred during FMP fetch for {stock_symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Entry point for the fundamental data producer."""
    producer = FundamentalDataProducer()
    producer.run()


if __name__ == '__main__':
    main()