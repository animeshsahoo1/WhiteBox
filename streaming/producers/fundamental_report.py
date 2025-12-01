import os
import requests
import time
import signal
import sys
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sec_api import PdfGeneratorApi
from utils.fmp_api_client import FmpApiClient
from producers.pdf_parser import PDFParser

load_dotenv()

class FundamentalReportProducer:
    
    def __init__(self):
        self.stocks = os.getenv('STOCKS', 'AAPL,MSFT').split(',')
        self.fetch_interval = int(os.getenv('FUNDAMENTAL_REPORT_INTERVAL', '5184000'))
        self.name = 'FundamentalReportProducer'
        self.scheduler = None
        
        self.fmp_client = None
        self.pdf_api = None
        self.pdf_parser = None
        self.knowledge_base = Path(os.getenv('KNOWLEDGE_BASE_DIR', '../knowledge_base')).resolve()
        self.limit = int(os.getenv('SEC_FILINGS_LIMIT', '100'))
        
        self.from_date = os.getenv('SEC_FILINGS_FROM_DATE')
        self.to_date = os.getenv('SEC_FILINGS_TO_DATE')
        if not self.from_date or not self.to_date:
            today = datetime.now()
            self.to_date = today.strftime('%Y-%m-%d')
            self.from_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    
    def setup(self):
        try:
            self.fmp_client = FmpApiClient()
            self.pdf_api = PdfGeneratorApi(os.getenv('SEC_API'))
            self.pdf_parser = PDFParser()
            print("✅ FMP client initialized")
            print("✅ SEC PDF API initialized")
            print("✅ PDF parser initialized")
            return True
        except ValueError as e:
            print(f"❌ FMP client init failed: {e}")
            return False
        except Exception as e:
            print(f"❌ SEC API init failed: {e}")
            return False
    
    def _save_as_pdf(self, url: str, output_dir: Path) -> Optional[str]:
        try:
            print(f"📥 Converting to PDF: {url}")
            
            pdf_data = self.pdf_api.get_pdf(url)
            
            timestamp = int(time.time())
            pdf_path = output_dir / f"filing_{timestamp}.pdf"
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_data)
            
            size = pdf_path.stat().st_size
            print(f"✓ PDF saved: {pdf_path.name} ({size} bytes)")
            return str(pdf_path)
        except Exception as e:
            print(f"❌ PDF conversion failed: {e}")
            return None
    
    def fetch_filings(self, stock_symbol: str):
        if not self.fmp_client:
            return
        
        try:
            filings = self.fmp_client.get_sec_filings(stock_symbol, limit=self.limit)
            
            if not filings:
                print(f"⚠️ No filings for {stock_symbol}")
                return
            
            output_dir = self.knowledge_base / stock_symbol
            output_dir.mkdir(parents=True, exist_ok=True)
            
            saved_count = 0
            for filing in filings:
                url = filing.get('finalLink')
                if url:
                    if self._save_as_pdf(url, output_dir):
                        saved_count += 1
                    time.sleep(1)
            
            print(f"✅ Saved {saved_count}/{len(filings)} filings for {stock_symbol}")
            
        except Exception as e:
            print(f"❌ Error fetching filings for {stock_symbol}: {e}")
    
    def fetch_all(self):
        print(f"\n[{self.name}] [{datetime.now().strftime('%H:%M:%S')}] Starting fetch...")
        print(f"📅 Date range: {self.from_date} to {self.to_date}")
        
        for stock in self.stocks:
            try:
                self.fetch_filings(stock)
                time.sleep(2)
            except Exception as e:
                print(f"❌ [{stock}] Error: {e}")
        
        # Parse all downloaded PDFs to JSONL
        print(f"\n{'='*70}")
        print("📄 Starting PDF parsing...")
        print(f"{'='*70}\n")
        try:
            self.pdf_parser.parse_all_stocks()
        except Exception as e:
            print(f"❌ PDF parsing failed: {e}")
    
    def run(self):
        print("="*70)
        print(f"{self.name} - Starting...")
        print("="*70)
        print(f"Interval: {self.fetch_interval}s")
        print(f"Stocks: {', '.join(self.stocks)}")
        print("="*70)
        
        if not self.setup():
            print(f"❌ Failed to initialize")
            sys.exit(1)
        
        def signal_handler(sig, frame):
            print(f"\n🛑 Shutting down...")
            if self.scheduler:
                self.scheduler.shutdown(wait=False)
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self.scheduler = BlockingScheduler()
        self.scheduler.add_job(
            self.fetch_all,
            trigger=IntervalTrigger(seconds=self.fetch_interval),
            id=f'{self.name}_job',
            max_instances=1
        )
        
        print("🚀 Running initial fetch...\n")
        try:
            self.fetch_all()
        except Exception as e:
            print(f"⚠️ Initial fetch failed: {e}")
        
        print(f"\n{'='*70}")
        print(f"✅ Scheduled to run every {self.fetch_interval} seconds")
        print("Press Ctrl+C to stop")
        print("="*70 + "\n")
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass


def main():
    producer = FundamentalReportProducer()
    producer.run()


if __name__ == '__main__':
    main()
