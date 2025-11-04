# file: src/report_generator.py

import os
from datetime import datetime
from typing import Dict, Any, Optional
from .data_processor import FundamentalDataProcessor

class ReportGenerator:
    """Generates a comprehensive fundamental analysis report in Markdown."""

    def __init__(self):
        self.p = FundamentalDataProcessor()

    def _generate_section(self, title, content):
        """Helper to create a standard section with a title and divider."""
        return f"## {title}\n\n{content}\n---\n\n"

    def _generate_overview(self, data):
        profile = data.get('profile') or {}
        peers = data.get('peers') or []
        content = f"""
### 1.1 Business Summary
**Company:** {profile.get('companyName', 'N/A')}
**Exchange:** {profile.get('exchangeShortName', 'N/A')}
**Industry:** {profile.get('industry', 'N/A')}
**Sector:** {profile.get('sector', 'N/A')}
**CEO:** {profile.get('ceo', 'N/A')}
**Description:** {profile.get('description', 'N/A')}

### 1.2 Stock Snapshot
**Price:** {self.p.format_number(profile.get('price'), prefix='$')}
**Market Cap:** {self.p.format_large_number(profile.get('mktCap'))}
**52-Week Range:** {profile.get('range', 'N/A')}
**Beta:** {self.p.format_number(profile.get('beta'))}

### 1.3 Peer Comparison
**Top Peers:** {', '.join(peers) if peers else 'N/A'}
"""
        return self._generate_section("1. Company Overview & Profile", content)

    def _generate_financial_health(self, data):
        income = data.get('income_annual') or []
        balance = data.get('balance_annual') or []
        ratios = data.get('ratios_ttm') or {}
        
        content = "### 2.1 Key Financials (Latest Annual)\n"
        if income and balance:
            latest_income = income[0]
            latest_balance = balance[0]
            content += f"""
| Metric                | Value                               |
|-----------------------|-------------------------------------|
| **Revenue**           | {self.p.format_large_number(latest_income.get('revenue'))} |
| **Net Income**        | {self.p.format_large_number(latest_income.get('netIncome'))} |
| **EPS**               | {self.p.format_number(latest_income.get('eps'), prefix='$')} |
| **Total Assets**      | {self.p.format_large_number(latest_balance.get('totalAssets'))} |
| **Total Liabilities** | {self.p.format_large_number(latest_balance.get('totalLiabilities'))} |
| **Total Equity**      | {self.p.format_large_number(latest_balance.get('totalEquity'))} |
"""
        else:
            content += "Financial statement data not available.\n"

        content += "\n### 2.2 Financial Ratios (TTM)\n"
        content += f"""
| Category       | Ratio                   | Value                                         |
|----------------|-------------------------|-----------------------------------------------|
| **Valuation**  | P/E Ratio               | {self.p.format_number(ratios.get('peRatioTTM'))} |
|                | P/B Ratio               | {self.p.format_number(ratios.get('priceToBookRatioTTM'))} |
| **Profitability**| Net Profit Margin     | {self.p.format_percentage(ratios.get('netProfitMarginTTM'), True)} |
|                | Return on Equity (ROE)  | {self.p.format_percentage(ratios.get('returnOnEquityTTM'), True)} |
| **Liquidity**  | Current Ratio           | {self.p.format_number(ratios.get('currentRatioTTM'))} |
| **Leverage**   | Debt to Equity          | {self.p.format_number(ratios.get('debtEquityRatioTTM'))} |
"""
        return self._generate_section("2. Financial Health & Performance", content)

    def _generate_market_sentiment(self, data):
        grades = data.get('grades_consensus') or {}
        targets = data.get('price_target_consensus') or {}
        content = f"""
### 3.1 Analyst Ratings Consensus
**Consensus:** {grades.get('consensus', 'N/A')}
- **Strong Buy:** {grades.get('strongBuy', 0)}
- **Buy:** {grades.get('buy', 0)}
- **Hold:** {grades.get('hold', 0)}

### 3.2 Price Target Consensus
- **Average:** {self.p.format_number(targets.get('targetConsensus'), prefix='$')}
- **High:** {self.p.format_number(targets.get('targetHigh'), prefix='$')}
- **Low:** {self.p.format_number(targets.get('targetLow'), prefix='$')}
"""
        return self._generate_section("3. Market Sentiment & Analyst Opinions", content)
    
    def _generate_news_and_filings(self, data, web_intelligence=None):
        news = data.get('news') or []
        filings = data.get('sec_filings') or []
        
        content = "### 4.1 Recent News (FMP)\n"
        if news:
            for article in news[:3]:
                content += f"- **{article.get('publishedDate', '').split(' ')[0]}:** [{article.get('title')}]({article.get('url')}) - *{article.get('site')}*\n"
        else:
            content += "No recent news available.\n"

        content += "\n### 4.2 Recent SEC Filings\n"
        if filings:
            for filing in filings[:5]:
                content += f"- **{filing.get('fillingDate')}:** {filing.get('type')} - [Link]({filing.get('finalLink')})\n"
        else:
            content += "No recent filings available.\n"
        
        # Add web-scraped articles with FULL CONTENT if available
        if web_intelligence and web_intelligence.get('articles'):
            content += "\n### 4.3 Web Intelligence - Comprehensive Article Analysis\n\n"
            content += f"*Analyzed {web_intelligence.get('total_articles', 0)} articles from {len(web_intelligence.get('sources', []))} sources*\n"
            content += f"*Total Content Extracted: {web_intelligence.get('total_words_scraped', 0):,} words*\n\n"
            
            articles = web_intelligence.get('articles', [])
            for i, article in enumerate(articles[:10], 1):  # Top 10 articles
                title = article.get('title', 'No Title')
                url = article.get('url', '#')
                source = article.get('source', 'Unknown')
                word_count = article.get('word_count', 0)
                published_date = article.get('publish_date') or article.get('published_date', 'N/A')
                
                content += f"#### Article {i}: {title}\n\n"
                content += f"**Source:** {source}\n"
                content += f"**Published:** {published_date}\n"
                content += f"**URL:** [{url}]({url})\n"
                content += f"**Word Count:** {word_count:,}\n\n"
                
                # Include FULL article text
                if article.get('text') and len(article['text']) > 100:
                    full_text = article['text']
                    content += f"**Full Article Content:**\n\n{full_text}\n\n"
                elif article.get('snippet'):
                    content += f"**Summary:** {article['snippet']}\n\n"
                else:
                    content += "*Article content not available*\n\n"
                
                # Add authors if available
                if article.get('authors'):
                    authors = ', '.join(article['authors'])
                    content += f"*Authors: {authors}*\n\n"
                
                content += "---\n\n"
            
        return self._generate_section("4. News & Market Intelligence", content)

    def generate_report(self, data: Dict[str, Any], ai_summary: Optional[str] = None, 
                       web_intelligence: Optional[Dict] = None) -> str:
        """Assembles the full Markdown report with RAW data (not AI-enhanced)."""
        symbol = data.get('symbol', 'UNKNOWN').upper()
        profile = data.get('profile') or {}
        company_name = profile.get('companyName', symbol)
        
        report_content = f"# Comprehensive Fundamental Analysis (Raw Data): {company_name} ({symbol})\n"
        report_content += f"**Report Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_content += f"**Data Sources:** FMP API + Serpex Web Intelligence\n"
        report_content += f"**Report Type:** Raw Data Report (All Extracted Content)\n"
        report_content += "---\n\n"
        
        # Add metadata about web intelligence if available
        if web_intelligence:
            report_content += f"*This report includes {web_intelligence.get('total_articles', 0)} web-scraped articles "
            report_content += f"({web_intelligence.get('total_words_scraped', 0):,} words) from "
            report_content += f"{len(web_intelligence.get('sources', []))} sources.*\n\n"
            report_content += f"*Sources: {', '.join(web_intelligence.get('sources', [])[:10])}*\n\n"
        
        report_content += self._generate_overview(data)
        report_content += self._generate_financial_health(data)
        report_content += self._generate_market_sentiment(data)
        report_content += self._generate_news_and_filings(data, web_intelligence)
        
        # Save to file
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"Raw_Data_Report_{symbol}.md")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"✅ Raw data report saved to {filename}")
        
        return filename