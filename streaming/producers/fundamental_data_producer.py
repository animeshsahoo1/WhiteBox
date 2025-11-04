# file: main.py

"""
Fundamental Data Producer
Fetches comprehensive fundamental analysis data from FMP API and simulates streaming.
This script acts as the main entry point for the data pipeline.
"""

import os
import time
import json
from typing import Optional, Dict, List
from dotenv import load_dotenv

from producers.base_producer import BaseProducer
from fundamental_utils.fmp_api_client import FmpApiClient
from fundamental_utils.data_processor import FundamentalDataProcessor
from fundamental_utils.report_generator import ReportGenerator
from fundamental_utils.web_scraper import WebScraper

load_dotenv()

class FundamentalDataProducer(BaseProducer):
    """Producer for comprehensive fundamental analysis data."""
    
    def __init__(self):
        stocks = os.getenv('STOCKS', 'AAPL,MSFT,GOOG').split(',')
        fetch_interval = int(os.getenv('FUNDAMENTAL_DATA_INTERVAL', '3600'))
        
        super().__init__(
            kafka_topic='fundamental-data',
            fetch_interval=fetch_interval,
            stocks=stocks
        )
        
        self.fmp_client = None
        self.processor = FundamentalDataProcessor()
        self.report_generator = ReportGenerator()
        
        # Initialize WebScraper with optional proxy
        scraper_proxy = os.getenv('DDGS_PROXY', None)  # Can use "tb" for Tor browser
        scraper_timeout = int(os.getenv('DDGS_TIMEOUT', '10'))
        self.web_scraper = WebScraper(proxy=scraper_proxy, timeout=scraper_timeout)
        
        # Configuration
        self.generate_reports = os.getenv('GENERATE_REPORTS', 'true').lower() == 'true'
        self.enable_web_scraping = os.getenv('ENABLE_WEB_SCRAPING', 'true').lower() == 'true'
        self.max_articles_per_stock = int(os.getenv('MAX_ARTICLES_PER_STOCK', '8'))
    
    def setup_sources(self):
        """Setup FMP as the primary data source for fundamentals."""
        try:
            # Initialize FMP client using the corrected class
            self.fmp_client = FmpApiClient()
            self.register_source("FMP", self._fetch_from_fmp, priority=0)
            
        except ValueError as e:
            print(f"  ❌ Critical Error: Could not initialize FMP client. {e}")
            print("     Please ensure FMP_API_KEY is set in your .env file.")
    
    def _fetch_from_fmp(self, stock_symbol: str) -> Optional[Dict]:
        """
        Fetches and processes comprehensive fundamental data from FMP.
        
        Args:
            stock_symbol: The stock ticker to fetch data for.
            
        Returns:
            A processed dictionary ready for Kafka, or None if an error occurs.
        """
        if not self.fmp_client:
            print(f"❌ FMP client not initialized. Cannot fetch data for {stock_symbol}.")
            return None

        try:
            # Step 1: Gather all raw data using the master function from the client
            raw_data = self.fmp_client.gather_all_fundamental_data(stock_symbol)
            
            if not raw_data.get('profile'):
                print(f"  ⚠️  Could not retrieve core profile for {stock_symbol}. Aborting fetch for this symbol.")
                return None

            print(f"  ✅ Successfully gathered FMP data for {stock_symbol}")
            
            # Step 2: Optionally scrape web articles
            web_intelligence = None
            if self.enable_web_scraping:
                try:
                    company_name = raw_data['profile'].get('companyName', stock_symbol)
                    print(f"\n  🕷️  Scraping web articles for {stock_symbol}...")
                    
                    web_intelligence = self.web_scraper.gather_stock_intelligence(
                        stock_symbol=stock_symbol, 
                        company_name=company_name,
                        max_articles=self.max_articles_per_stock,
                        scrape_full=True
                    )
                    
                    print(f"  ✅ Scraped {web_intelligence['total_articles']} articles")
                    
                except Exception as e:
                    print(f"  ⚠️  Web scraping failed: {e}")
                    web_intelligence = None
            
            # Step 3: Generate comprehensive report
            if self.generate_reports:
                try:
                    print(f"\n  📄 Generating comprehensive report for {stock_symbol}...")
                    report_path = self.report_generator.generate_report(
                        data=raw_data,
                        ai_summary=None,  # AI summary disabled
                        web_intelligence=web_intelligence
                    )
                    print(f"  ✅ Report saved: {report_path}")
                except Exception as e:
                    print(f"  ⚠️  Report generation failed: {e}")
            
            return raw_data # Returning the raw dictionary for Kafka
            
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