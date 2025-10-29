import os
import pathway as pw
from pathway.xpacks.llm.llms import OpenAIChat
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv(dotenv_path="Pathway_InterIIT/streaming/.env")

class NewsReportUpdater:
    """
    A class that uses stateful reducers to maintain and update a news report
    for trading agents using OpenAI's LLM.
    Creates separate reports for each company.
    """
    
    def __init__(self, reports_directory: str):
        """
        Initialize the news report updater.
        
        Args:
            reports_directory: Directory path where company reports will be stored
        """
        self.reports_directory = reports_directory
        
        # Parse the STOCK_COMPANY_MAP from environment
        try:
            self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}"))
        except json.JSONDecodeError:
            print("Warning: Could not parse STOCK_COMPANY_MAP, using empty mapping")
            self.symbol_mapping = {}
        
        # Initialize OpenAI Chat model
        self.llm = OpenAIChat(
            model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=0.0,  # Lower temperature for more consistent analysis
            max_tokens=2000
        )
        
        # Create reports directory if it doesn't exist
        os.makedirs(self.reports_directory, exist_ok=True)
    
    def _get_report_path(self, symbol: str) -> str:
        """Get the file path for a company's report."""
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "news_report.md")
    
    def _load_report(self, symbol: str) -> str:
        """Load the existing report from file for a specific company."""
        report_path = self._get_report_path(symbol)
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Create initial report template for this company
            company_name = self.symbol_mapping.get(symbol, symbol)
            initial_report = f"""# {company_name} ({symbol}) - Market News Analysis Report

## Summary
No news analyzed yet for {company_name}.

## Recent Developments
*Awaiting news updates...*

## Market Impact Analysis
- **Current Sentiment**: Neutral
- **Price Impact Expectation**: None
- **Last Updated**: Never

## Trading Signals
- **Signal**: HOLD
- **Confidence**: N/A
- **Reasoning**: Insufficient data

---
*This report is automatically updated by the AI Trading Agent*
*Last Analysis: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
            # Save initial report
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(initial_report)
            return initial_report
    
    def _save_report(self, symbol: str, report_content: str) -> None:
        """Save the updated report to file for a specific company."""
        report_path = self._get_report_path(symbol)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Saved report for {symbol} to {report_path}")
    
    def _format_news_batch(self, symbol: str, news_items: list) -> str:
        """Format a batch of news items for the LLM prompt."""
        company = self.symbol_mapping.get(symbol, symbol)
        formatted_news = []
        
        for item in news_items:
            # Extract fields from the news item
            # item = [timestamp, title, description, source, url, published_at, sent_at]
            timestamp, title, description, source, url, published_at, sent_at = item
            
            formatted_news.append(f"""
---
**Title**: {title}
**Description**: {description}
**Source**: {source}
**Published**: {published_at}
**URL**: {url}
**Received**: {timestamp}
""")
        
        header = f"## News Batch for {company} ({symbol})\n"
        header += f"Total articles in this batch: {len(news_items)}\n"
        
        return header + "\n".join(formatted_news)
    
    def _create_update_prompt(self, symbol: str, current_report: str, news_batch: str) -> list[dict]:
        """Create the prompt for updating the report."""
        
        company_name = self.symbol_mapping.get(symbol, symbol)
        
        system_message = f"""You are a financial analyst AI assistant specializing in market impact analysis for {company_name} ({symbol}).
Your task is to update the trading report by analyzing new news articles and their potential impact on {symbol}'s stock price.

Focus on:
1. **Price Impact**: Assess whether news is bullish (positive), bearish (negative), or neutral for {symbol}
2. **Magnitude**: Evaluate the significance (High/Medium/Low impact)
3. **Timeframe**: Consider short-term vs long-term implications
4. **Market Sentiment**: Update sentiment specific to {company_name}
5. **Trading Signals**: Provide clear BUY/SELL/HOLD recommendations with confidence levels

Keep the report concise, actionable, and well-structured in markdown format.
Preserve the overall structure but update content based on new information.
Always update the "Last Analysis" timestamp at the bottom.
"""
        
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        user_message = f"""Here is the CURRENT REPORT for {company_name} ({symbol}):

{current_report}

---

Here are NEW NEWS ARTICLES to analyze and incorporate:

{news_batch}

---

TASK: Update the report by:
1. Analyzing each news item's potential market impact on {symbol}
2. Updating the "Recent Developments" section with new information
3. Adjusting the "Market Impact Analysis" based on the news
4. Updating the "Trading Signals" with actionable BUY/SELL/HOLD recommendation
5. Updating the timestamp to: {current_time} UTC

Return ONLY the updated markdown report. Do not include explanations outside the report."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def create_reducer_for_symbol(self, symbol: str):
        """
        Create a stateful reducer function for a specific symbol.
        This is needed because each symbol needs its own state.
        """
        
        @pw.reducers.stateful_many
        def update_report_reducer(
            current_state: str | None,
            news_batch: list[tuple[list, int]]
        ) -> str:
            """
            Stateful reducer that maintains and updates the news report for this symbol.
            
            Args:
                current_state: Current report content (None on first call)
                news_batch: List of (news_row, count) tuples
                
            Returns:
                Updated report content
            """
            # Initialize state with existing report for this symbol
            if current_state is None:
                current_state = self._load_report(symbol)
            
            # Extract news items (only process insertions)
            news_items = []
            for row_values, count in news_batch:
                if count > 0:  # Only process insertions
                    # row_values contains: [timestamp, title, description, source, url, published_at, sent_at]
                    for _ in range(count):
                        news_items.append(row_values)
            
            # If no news to process, return current state
            if not news_items:
                return current_state
            
            # Format news batch for LLM
            formatted_news = self._format_news_batch(symbol, news_items)
            
            # Create prompt
            messages = self._create_update_prompt(symbol, current_state, formatted_news)
            
            # Call LLM to update report
            try:
                updated_report = pw.unwrap(self.llm(pw.Json(messages)))
                
                # Save updated report to file
                self._save_report(symbol, updated_report)
                
                print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Report updated for {symbol} with {len(news_items)} news items")
                
                return updated_report
                
            except Exception as e:
                print(f"Error updating report for {symbol}: {e}")
                return current_state  # Return unchanged state on error
        
        return update_report_reducer


def process_news_stream(news_table: pw.Table, reports_directory: str = "./reports") -> pw.Table:
    """
    Process news stream and create/update company-specific reports.
    
    Args:
        news_table: Pathway table with news data
        reports_directory: Directory where reports will be stored
        
    Returns:
        Table with updated reports per company
    """
    
    # Ensure the reports directory exists
    os.makedirs(reports_directory, exist_ok=True)
    # Initialize the updater
    report_updater = NewsReportUpdater(reports_directory=reports_directory)
    
    # Group by symbol and create reducer for each
    # This will create separate reports for each company
    updated_reports = news_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        report=report_updater.create_reducer_for_symbol(pw.this.symbol)(
            pw.this.timestamp,
            pw.this.title,
            pw.this.description,
            pw.this.source,
            pw.this.url,
            pw.this.published_at,
            pw.this.sent_at
        )
    )
    
    return updated_reports


# # Example usage
# if __name__ == "__main__":
    
#     # Demo table for testing
#     news_table = pw.debug.table_from_markdown("""
#     symbol | timestamp           | title                        | description                      | source      | url                  | published_at         | sent_at
#     AAPL   | 2025-10-29 10:00:00 | Apple launches new iPhone    | Revolutionary new features       | TechNews    | http://example.com/1 | 2025-10-29 09:45:00 | 2025-10-29 10:00:00
#     AAPL   | 2025-10-29 11:00:00 | Apple stock surges           | Market reacts positively         | MarketWatch | http://example.com/2 | 2025-10-29 10:50:00 | 2025-10-29 11:00:00
#     GOOGL  | 2025-10-29 10:30:00 | Google announces AI update   | New AI capabilities              | TechCrunch  | http://example.com/3 | 2025-10-29 10:20:00 | 2025-10-29 10:30:00
#     MSFT   | 2025-10-29 12:00:00 | Microsoft earnings beat      | Strong quarterly results         | Bloomberg   | http://example.com/4 | 2025-10-29 11:55:00 | 2025-10-29 12:00:00
#     """)
    
#     # Process news stream and create company-specific reports
#     updated_reports = process_news_stream(news_table, reports_directory="./reports")
    
#     # Print the results
#     pw.debug.compute_and_print(updated_reports)
    
#     print("\n" + "="*80)
#     print("Reports have been created in the following structure:")
#     print("./reports/")
#     print("├── AAPL/")
#     print("│   └── news_report.md")
#     print("├── GOOGL/")
#     print("│   └── news_report.md")
#     print("└── MSFT/")
#     print("    └── news_report.md")
#     print("="*80)