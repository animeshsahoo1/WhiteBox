"""Demo News Clustering Pipeline"""

import argparse
import pathway as pw
from pathlib import Path
import sys
import os

sys.path.append(str(Path(__file__).parent))
from agents.news_agent import process_news_stream


class NewsDataSchema(pw.Schema):
    symbol: str
    timestamp: str
    title: str
    description: str
    source: str
    url: str
    published_at: str


def run_demo_pipeline(ticker: str = "AAPL", data_dir: str = "./demo_data",
                      reports_dir: str = "./reports/demo_news", kb_dir: str = "./demo_kb"):
    csv_file = Path(data_dir) / f"{ticker}_news.csv"
    if not csv_file.exists():
        print(f"Data file not found: {csv_file}\nRun: python streaming/producers/demo_news_producer.py")
        return
    
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(kb_dir, exist_ok=True)
    
    print(f"📰 Demo Pipeline | Ticker: {ticker} | Data: {csv_file}")
    
    news_table = pw.io.csv.read(str(Path(data_dir)), schema=NewsDataSchema, mode="static")
    reports_table, clusters_table = process_news_stream(news_table, reports_dir, kb_dir)
    
    pw.io.null.write(reports_table)
    pw.io.null.write(clusters_table)
    
    print(f"Reports: {reports_dir}/{ticker}/ | KB: {kb_dir}/{ticker}/")
    pw.run()


def main():
    parser = argparse.ArgumentParser(description="Demo News Clustering Pipeline")
    parser.add_argument("--ticker", type=str, default="AAPL")
    parser.add_argument("--data-dir", type=str, default="./demo_data")
    parser.add_argument("--reports-dir", type=str, default="./reports/demo_news")
    parser.add_argument("--kb-dir", type=str, default="./demo_kb")
    args = parser.parse_args()
    
    run_demo_pipeline(args.ticker, args.data_dir, args.reports_dir, args.kb_dir)


if __name__ == "__main__":
    main()
