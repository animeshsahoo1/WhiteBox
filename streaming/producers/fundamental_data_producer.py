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
from fundamental_utils.ai_report_generator import AIReportGenerator

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
        
        # Initialize AI Report Generator
        try:
            self.ai_report_generator = AIReportGenerator()
            self.enable_ai_reports = True
            print("✅ AI Report Generator initialized successfully")
        except Exception as e:
            print(f"⚠️  AI Report Generator initialization failed: {e}")
            print("   AI-enhanced reports will be disabled. Set OPENAI_API_KEY to enable.")
            self.ai_report_generator = None
            self.enable_ai_reports = False
        
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
        self.generate_reports = os.getenv('GENERATE_REPORTS', 'true').lower() == 'true'
        self.max_articles_per_stock = int(os.getenv('MAX_ARTICLES_PER_STOCK', '10'))
    
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
            
            # Step 3: Generate RAW data report with all extracted content
            raw_report_path = None
            if self.generate_reports:
                try:
                    print(f"\n  📄 Generating raw data report for {stock_symbol}...")
                    raw_report_path = self.report_generator.generate_report(
                        data=raw_data,
                        web_intelligence=web_intelligence
                    )
                    print(f"  ✅ Raw data report saved: {raw_report_path}")
                except Exception as e:
                    print(f"  ⚠️  Raw report generation failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Step 4: Generate AI-enhanced summary report
            ai_report_path = None
            if self.enable_ai_reports and self.ai_report_generator:
                try:
                    print(f"\n  🤖 Generating AI-enhanced summary report for {stock_symbol}...")
                    
                    # Generate AI summary
                    ai_summary = self.ai_report_generator.generate_ai_summary(
                        symbol=stock_symbol,
                        data=raw_data,
                        web_intelligence=web_intelligence
                    )
                    
                    # Save AI report
                    ai_report_path = self.ai_report_generator.save_ai_report(
                        symbol=stock_symbol,
                        ai_summary=ai_summary
                    )
                    
                    print(f"  ✅ AI-enhanced report saved: {ai_report_path}")
                    
                except Exception as e:
                    print(f"  ⚠️  AI report generation failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Add report paths to the data for tracking
            raw_data['_report_paths'] = {
                'raw_report': raw_report_path,
                'ai_report': ai_report_path
            }
            
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