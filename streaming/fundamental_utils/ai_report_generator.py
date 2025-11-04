# file: fundamental_utils/ai_report_generator.py

"""
AI Report Generator for Fundamental Analysis
Uses OpenAI via OpenRouter to create comprehensive AI-enhanced reports
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional


class AIReportGenerator:
    """Generates AI-enhanced fundamental analysis reports using LLM."""
    
    def __init__(self):
        """Initialize the AI report generator with OpenRouter API key."""
        self.openrouter_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openrouter_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Import OpenAI for direct API calls (since pathway's OpenAIChat is for streaming)
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.temperature = 0.3
        self.max_tokens = 10000
    
    def _format_financial_data(self, data: Dict[str, Any]) -> str:
        """Format ALL financial data from FMP into a comprehensive, well-structured text for LLM."""
        
        profile = data.get('profile') or {}
        peers = data.get('peers') or []
        income_annual = data.get('income_annual') or []
        balance_annual = data.get('balance_annual') or []
        cashflow_annual = data.get('cashflow_annual') or []
        ratios_ttm = data.get('ratios_ttm') or {}
        growth_annual = data.get('growth_annual') or []
        scores = data.get('scores') or []
        grades = data.get('grades_consensus') or {}
        targets = data.get('price_target_consensus') or {}
        dividends = data.get('dividends') or []
        splits = data.get('splits') or []
        insider_trades = data.get('insider_trades') or []
        executives = data.get('executives') or []
        news = data.get('news') or []
        sec_filings = data.get('sec_filings') or []
        
        # Build comprehensive formatted text
        sections = []
        
        # Pre-format all numeric values to avoid f-string formatting issues
        def format_number(value, prefix='', suffix='', decimals=0):
            """Helper to format numbers safely"""
            if value is None or value == 'N/A':
                return 'N/A'
            if isinstance(value, (int, float)):
                if decimals > 0:
                    return f"{prefix}{value:,.{decimals}f}{suffix}"
                else:
                    return f"{prefix}{value:,.0f}{suffix}"
            return str(value)
        
        # Pre-format key values
        employees_fmt = format_number(profile.get('fullTimeEmployees'))
        mkt_cap_fmt = format_number(profile.get('mktCap'), prefix='$')
        vol_avg_fmt = format_number(profile.get('volAvg'))
        
        # ============================================
        # SECTION 1: COMPANY PROFILE & OVERVIEW
        # ============================================
        section_1 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SECTION 1: COMPANY PROFILE & OVERVIEW                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

1.1 BASIC INFORMATION
───────────────────────────────────────────────────────────────────────────────
Company Name:        {profile.get('companyName', 'N/A')}
Stock Symbol:        {data.get('symbol', 'N/A')}
Exchange:            {profile.get('exchangeShortName', 'N/A')}
Currency:            {profile.get('currency', 'N/A')}
Country:             {profile.get('country', 'N/A')}
Industry:            {profile.get('industry', 'N/A')}
Sector:              {profile.get('sector', 'N/A')}
Website:             {profile.get('website', 'N/A')}
CEO:                 {profile.get('ceo', 'N/A')}
Employees:           {employees_fmt}

1.2 CURRENT MARKET DATA
───────────────────────────────────────────────────────────────────────────────
Current Price:       ${profile.get('price', 'N/A')}
Market Cap:          {mkt_cap_fmt}
52-Week Range:       {profile.get('range', 'N/A')}
Beta:                {profile.get('beta', 'N/A')}
Volume Average:      {vol_avg_fmt}
Last Dividend:       ${profile.get('lastDiv', 'N/A')}
IPO Date:            {profile.get('ipoDate', 'N/A')}

1.3 BUSINESS DESCRIPTION
───────────────────────────────────────────────────────────────────────────────
{profile.get('description', 'No description available.')}

1.4 COMPETITIVE LANDSCAPE - PEER COMPANIES
───────────────────────────────────────────────────────────────────────────────
Peer Companies:      {', '.join(peers) if peers else 'No peer data available'}
"""
        sections.append(section_1)
        
        # ============================================
        # SECTION 2: FINANCIAL STATEMENTS (5-YEAR HISTORY)
        # ============================================
        section_2 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                  SECTION 2: FINANCIAL STATEMENTS (5-YEAR)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

2.1 INCOME STATEMENT - ANNUAL (Latest 5 Years)
───────────────────────────────────────────────────────────────────────────────
"""
        if income_annual:
            for i, stmt in enumerate(income_annual[:5], 1):
                year = stmt.get('date', 'N/A')
                # Pre-format all numeric values
                revenue_fmt = format_number(stmt.get('revenue', 0), prefix='$')
                cost_rev_fmt = format_number(stmt.get('costOfRevenue', 0), prefix='$')
                gross_profit_fmt = format_number(stmt.get('grossProfit', 0), prefix='$')
                operating_income_fmt = format_number(stmt.get('operatingIncome', 0), prefix='$')
                ebitda_fmt = format_number(stmt.get('ebitda', 0), prefix='$')
                net_income_fmt = format_number(stmt.get('netIncome', 0), prefix='$')
                eps_fmt = format_number(stmt.get('eps', 0), prefix='$', decimals=4)
                rd_fmt = format_number(stmt.get('researchAndDevelopmentExpenses', 0), prefix='$')
                opex_fmt = format_number(stmt.get('operatingExpenses', 0), prefix='$')
                interest_fmt = format_number(stmt.get('interestExpense', 0), prefix='$')
                tax_fmt = format_number(stmt.get('incomeTaxExpense', 0), prefix='$')
                
                section_2 += f"""
Year {i}: {year}
  Revenue:                    {revenue_fmt}
  Cost of Revenue:            {cost_rev_fmt}
  Gross Profit:               {gross_profit_fmt}
  Operating Income:           {operating_income_fmt}
  EBITDA:                     {ebitda_fmt}
  Net Income:                 {net_income_fmt}
  EPS (Earnings Per Share):   {eps_fmt}
  R&D Expenses:               {rd_fmt}
  Operating Expenses:         {opex_fmt}
  Interest Expense:           {interest_fmt}
  Income Tax Expense:         {tax_fmt}
"""
        else:
            section_2 += "\nNo income statement data available.\n"
        
        section_2 += f"""
2.2 BALANCE SHEET - ANNUAL (Latest 5 Years)
───────────────────────────────────────────────────────────────────────────────
"""
        if balance_annual:
            for i, stmt in enumerate(balance_annual[:5], 1):
                year = stmt.get('date', 'N/A')
                # Pre-format all balance sheet values
                total_assets_fmt = format_number(stmt.get('totalAssets', 0), prefix='$')
                current_assets_fmt = format_number(stmt.get('totalCurrentAssets', 0), prefix='$')
                cash_fmt = format_number(stmt.get('cashAndCashEquivalents', 0), prefix='$')
                inventory_fmt = format_number(stmt.get('inventory', 0), prefix='$')
                receivables_fmt = format_number(stmt.get('netReceivables', 0), prefix='$')
                ppe_fmt = format_number(stmt.get('propertyPlantEquipmentNet', 0), prefix='$')
                intangibles_fmt = format_number(stmt.get('intangibleAssets', 0), prefix='$')
                goodwill_fmt = format_number(stmt.get('goodwill', 0), prefix='$')
                total_liab_fmt = format_number(stmt.get('totalLiabilities', 0), prefix='$')
                current_liab_fmt = format_number(stmt.get('totalCurrentLiabilities', 0), prefix='$')
                ltdebt_fmt = format_number(stmt.get('longTermDebt', 0), prefix='$')
                stdebt_fmt = format_number(stmt.get('shortTermDebt', 0), prefix='$')
                payables_fmt = format_number(stmt.get('accountPayables', 0), prefix='$')
                total_equity_fmt = format_number(stmt.get('totalEquity', 0), prefix='$')
                retained_fmt = format_number(stmt.get('retainedEarnings', 0), prefix='$')
                common_stock_fmt = format_number(stmt.get('commonStock', 0), prefix='$')
                
                section_2 += f"""
Year {i}: {year}
  ASSETS:
    Total Assets:             {total_assets_fmt}
    Current Assets:           {current_assets_fmt}
    Cash & Equivalents:       {cash_fmt}
    Inventory:                {inventory_fmt}
    Accounts Receivable:      {receivables_fmt}
    Property, Plant & Equip:  {ppe_fmt}
    Intangible Assets:        {intangibles_fmt}
    Goodwill:                 {goodwill_fmt}
  
  LIABILITIES:
    Total Liabilities:        {total_liab_fmt}
    Current Liabilities:      {current_liab_fmt}
    Long-term Debt:           {ltdebt_fmt}
    Short-term Debt:          {stdebt_fmt}
    Accounts Payable:         {payables_fmt}
  
  EQUITY:
    Total Equity:             {total_equity_fmt}
    Retained Earnings:        {retained_fmt}
    Common Stock:             {common_stock_fmt}
"""
        else:
            section_2 += "\nNo balance sheet data available.\n"
        
        section_2 += f"""
2.3 CASH FLOW STATEMENT - ANNUAL (Latest 5 Years)
───────────────────────────────────────────────────────────────────────────────
"""
        if cashflow_annual:
            for i, stmt in enumerate(cashflow_annual[:5], 1):
                year = stmt.get('date', 'N/A')
                # Pre-format cash flow values
                ocf_fmt = format_number(stmt.get('operatingCashFlow', 0), prefix='$')
                icf_fmt = format_number(stmt.get('cashFlowFromInvestments', 0), prefix='$')
                fcf_fmt = format_number(stmt.get('cashFlowFromFinancing', 0), prefix='$')
                free_cf_fmt = format_number(stmt.get('freeCashFlow', 0), prefix='$')
                capex_fmt = format_number(stmt.get('capitalExpenditure', 0), prefix='$')
                div_fmt = format_number(stmt.get('dividendsPaid', 0), prefix='$')
                buyback_fmt = format_number(stmt.get('commonStockRepurchased', 0), prefix='$')
                net_change_fmt = format_number(stmt.get('netChangeInCash', 0), prefix='$')
                
                section_2 += f"""
Year {i}: {year}
  Operating Cash Flow:        {ocf_fmt}
  Investing Cash Flow:        {icf_fmt}
  Financing Cash Flow:        {fcf_fmt}
  Free Cash Flow:             {free_cf_fmt}
  Capital Expenditure:        {capex_fmt}
  Dividends Paid:             {div_fmt}
  Stock Buybacks:             {buyback_fmt}
  Net Change in Cash:         {net_change_fmt}
"""
        else:
            section_2 += "\nNo cash flow data available.\n"
        
        sections.append(section_2)
        
        # ============================================
        # SECTION 3: FINANCIAL RATIOS & METRICS (TTM)
        # ============================================
        section_3 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SECTION 3: FINANCIAL RATIOS & METRICS (TTM)                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

3.1 VALUATION RATIOS
───────────────────────────────────────────────────────────────────────────────
P/E Ratio (Price-to-Earnings):              {ratios_ttm.get('peRatioTTM', 'N/A')}
P/B Ratio (Price-to-Book):                  {ratios_ttm.get('priceToBookRatioTTM', 'N/A')}
P/S Ratio (Price-to-Sales):                 {ratios_ttm.get('priceToSalesRatioTTM', 'N/A')}
Price-to-Free-Cash-Flow:                    {ratios_ttm.get('priceToFreeCashFlowsRatioTTM', 'N/A')}
EV-to-Sales:                                {ratios_ttm.get('enterpriseValueMultipleTTM', 'N/A')}
PEG Ratio:                                  {ratios_ttm.get('pegRatioTTM', 'N/A')}

3.2 PROFITABILITY RATIOS
───────────────────────────────────────────────────────────────────────────────
Gross Profit Margin:                        {ratios_ttm.get('grossProfitMarginTTM', 'N/A')}
Operating Profit Margin:                    {ratios_ttm.get('operatingProfitMarginTTM', 'N/A')}
Net Profit Margin:                          {ratios_ttm.get('netProfitMarginTTM', 'N/A')}
Return on Assets (ROA):                     {ratios_ttm.get('returnOnAssetsTTM', 'N/A')}
Return on Equity (ROE):                     {ratios_ttm.get('returnOnEquityTTM', 'N/A')}
Return on Capital Employed (ROCE):          {ratios_ttm.get('returnOnCapitalEmployedTTM', 'N/A')}
EBITDA Margin:                              {ratios_ttm.get('ebitdaMarginTTM', 'N/A')}

3.3 LIQUIDITY RATIOS
───────────────────────────────────────────────────────────────────────────────
Current Ratio:                              {ratios_ttm.get('currentRatioTTM', 'N/A')}
Quick Ratio (Acid Test):                    {ratios_ttm.get('quickRatioTTM', 'N/A')}
Cash Ratio:                                 {ratios_ttm.get('cashRatioTTM', 'N/A')}
Operating Cash Flow Ratio:                  {ratios_ttm.get('operatingCashFlowRatioTTM', 'N/A')}

3.4 LEVERAGE/SOLVENCY RATIOS
───────────────────────────────────────────────────────────────────────────────
Debt-to-Equity Ratio:                       {ratios_ttm.get('debtEquityRatioTTM', 'N/A')}
Debt-to-Assets Ratio:                       {ratios_ttm.get('debtRatioTTM', 'N/A')}
Interest Coverage Ratio:                    {ratios_ttm.get('interestCoverageTTM', 'N/A')}
Debt-to-EBITDA:                             {ratios_ttm.get('companyEquityMultiplierTTM', 'N/A')}

3.5 EFFICIENCY RATIOS
───────────────────────────────────────────────────────────────────────────────
Asset Turnover:                             {ratios_ttm.get('assetTurnoverTTM', 'N/A')}
Inventory Turnover:                         {ratios_ttm.get('inventoryTurnoverTTM', 'N/A')}
Receivables Turnover:                       {ratios_ttm.get('receivablesTurnoverTTM', 'N/A')}
Days Sales Outstanding:                     {ratios_ttm.get('daysOfSalesOutstandingTTM', 'N/A')}
Days Inventory Outstanding:                 {ratios_ttm.get('daysOfInventoryOutstandingTTM', 'N/A')}
Days Payables Outstanding:                  {ratios_ttm.get('daysOfPayablesOutstandingTTM', 'N/A')}
Cash Conversion Cycle:                      {ratios_ttm.get('cashConversionCycleTTM', 'N/A')}

3.6 DIVIDEND METRICS
───────────────────────────────────────────────────────────────────────────────
Dividend Yield:                             {ratios_ttm.get('dividendYieldTTM', 'N/A')}
Dividend Payout Ratio:                      {ratios_ttm.get('dividendPayoutRatioTTM', 'N/A')}
"""
        sections.append(section_3)
        
        # ============================================
        # SECTION 4: GROWTH METRICS (5-YEAR TREND)
        # ============================================
        section_4 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                SECTION 4: GROWTH METRICS (5-YEAR TREND)                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        if growth_annual:
            for i, growth in enumerate(growth_annual[:5], 1):
                year = growth.get('date', 'N/A')
                section_4 += f"""
Year {i}: {year}
  Revenue Growth:                           {growth.get('revenueGrowth', 'N/A')}
  Gross Profit Growth:                      {growth.get('grossProfitGrowth', 'N/A')}
  Net Income Growth:                        {growth.get('netIncomeGrowth', 'N/A')}
  EPS Growth:                               {growth.get('epsgrowth', 'N/A')}
  Operating Income Growth:                  {growth.get('operatingIncomeGrowth', 'N/A')}
  Free Cash Flow Growth:                    {growth.get('freeCashFlowGrowth', 'N/A')}
  Total Assets Growth:                      {growth.get('assetGrowth', 'N/A')}
  Book Value Per Share Growth:              {growth.get('bookValuePerShareGrowth', 'N/A')}
  R&D Expense Growth:                       {growth.get('rdexpenseGrowth', 'N/A')}
"""
        else:
            section_4 += "No growth data available.\n"
        
        sections.append(section_4)
        
        # ============================================
        # SECTION 5: FINANCIAL HEALTH SCORES
        # ============================================
        section_5 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SECTION 5: FINANCIAL HEALTH SCORES                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        if scores:
            latest_score = scores[0] if isinstance(scores, list) and scores else scores
            if isinstance(latest_score, dict):
                section_5 += f"""
Overall Score:                              {latest_score.get('overallScore', 'N/A')}
Altman Z-Score:                             {latest_score.get('altmanZScore', 'N/A')}
Piotroski Score:                            {latest_score.get('piotroskiScore', 'N/A')}
Working Capital Score:                      {latest_score.get('workingCapitalScore', 'N/A')}
"""
            else:
                 section_5 += "Score data is in an unexpected format.\n"
        else:
            section_5 += "No financial scores available.\n"
        
        sections.append(section_5)
        
        # ============================================
        # SECTION 6: ANALYST RATINGS & PRICE TARGETS
        # ============================================
        section_6 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SECTION 6: ANALYST RATINGS & PRICE TARGETS                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

6.1 ANALYST CONSENSUS RATING
───────────────────────────────────────────────────────────────────────────────
Overall Consensus:                          {grades.get('consensus', 'N/A')}
Strong Buy Recommendations:                 {grades.get('strongBuy', 0)}
Buy Recommendations:                        {grades.get('buy', 0)}
Hold Recommendations:                       {grades.get('hold', 0)}
Sell Recommendations:                       {grades.get('sell', 0)}
Strong Sell Recommendations:                {grades.get('strongSell', 0)}

6.2 PRICE TARGET CONSENSUS
───────────────────────────────────────────────────────────────────────────────
Target Price (Consensus):                   ${targets.get('targetConsensus', 'N/A')}
Target Price (High):                        ${targets.get('targetHigh', 'N/A')}
Target Price (Low):                         ${targets.get('targetLow', 'N/A')}
Target Price (Median):                      ${targets.get('targetMedian', 'N/A')}
Number of Analysts:                         {targets.get('numberOfAnalysts', 'N/A')}
"""
        sections.append(section_6)
        
        # ============================================
        # SECTION 7: DIVIDENDS & SHAREHOLDER RETURNS
        # ============================================
        section_7 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SECTION 7: DIVIDENDS & SHAREHOLDER RETURNS                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

7.1 DIVIDEND HISTORY (Last 20 Payments)
───────────────────────────────────────────────────────────────────────────────
"""
        if dividends:
            for i, div in enumerate(dividends[:20], 1):
                section_7 += f"{i}. Date: {div.get('date', 'N/A')} | Amount: ${div.get('dividend', 'N/A')} | Adj. Dividend: ${div.get('adjDividend', 'N/A')}\n"
        else:
            section_7 += "No dividend payment history available.\n"
        
        section_7 += f"""
7.2 STOCK SPLITS HISTORY
───────────────────────────────────────────────────────────────────────────────
"""
        if splits:
            for i, split in enumerate(splits, 1):
                section_7 += f"{i}. Date: {split.get('date', 'N/A')} | Split Ratio: {split.get('numerator', 'N/A')}:{split.get('denominator', 'N/A')}\n"
        else:
            section_7 += "No stock splits history available.\n"
        
        sections.append(section_7)
        
        # ============================================
        # SECTION 8: INSIDER ACTIVITY
        # ============================================
        section_8 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      SECTION 8: INSIDER TRADING ACTIVITY                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Recent Insider Trades (Last 20):
───────────────────────────────────────────────────────────────────────────────
"""
        if insider_trades:
            for i, trade in enumerate(insider_trades[:20], 1):
                filing_date = trade.get('filingDate', 'N/A')
                transaction_date = trade.get('transactionDate', 'N/A')
                reporter = trade.get('reportingName', 'N/A')
                transaction_type = trade.get('transactionType', 'N/A')
                securities_owned = trade.get('securitiesOwned', 0)
                securities_transacted = trade.get('securitiesTransacted', 0)
                price = trade.get('price', 0)
                
                section_8 += f"""
Trade {i}:
  Filing Date: {filing_date} | Transaction Date: {transaction_date}
  Insider: {reporter}
  Transaction Type: {transaction_type}
  Shares Transacted: {securities_transacted:,} | Price: ${price:.2f}
  Total Shares Owned: {securities_owned:,}
  
"""
        else:
            section_8 += "No insider trading data available.\n"
        
        sections.append(section_8)
        
        # ============================================
        # SECTION 9: KEY EXECUTIVES
        # ============================================
        section_9 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        SECTION 9: KEY EXECUTIVES                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Executive Team:
───────────────────────────────────────────────────────────────────────────────
"""
        if executives:
            for i, exec in enumerate(executives, 1):
                name = exec.get('name', 'N/A')
                title = exec.get('title', 'N/A')
                pay = exec.get('pay', 'N/A')
                section_9 += f"{i}. {name} - {title} | Compensation: ${pay:,}\n" if isinstance(pay, (int, float)) else f"{i}. {name} - {title}\n"
        else:
            section_9 += "No executive data available.\n"
        
        sections.append(section_9)
        
        # ============================================
        # SECTION 10: RECENT NEWS & MARKET SENTIMENT
        # ============================================
        section_10 = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SECTION 10: RECENT NEWS & MARKET SENTIMENT                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

10.1 RECENT NEWS HEADLINES (FMP Source)
───────────────────────────────────────────────────────────────────────────────
"""
        if news:
            for i, article in enumerate(news[:10], 1):
                title = article.get('title', 'No Title')
                published = article.get('publishedDate', 'N/A')
                site = article.get('site', 'N/A')
                url = article.get('url', '#')
                text = article.get('text', '')
                
                section_10 += f"""
Article {i}: {title}
  Published: {published} | Source: {site}
  URL: {url}
  Summary: {text[:300]}...
  
"""
        else:
            section_10 += "No recent news available.\n"
        
        section_10 += f"""
10.2 SEC FILINGS (Last 90 Days)
───────────────────────────────────────────────────────────────────────────────
"""
        if sec_filings:
            for i, filing in enumerate(sec_filings[:10], 1):
                filing_type = filing.get('type', 'N/A')
                filing_date = filing.get('fillingDate', 'N/A')
                url = filing.get('finalLink', '#')
                section_10 += f"{i}. {filing_date} - {filing_type} | Link: {url}\n"
        else:
            section_10 += "No recent SEC filings available.\n"
        
        sections.append(section_10)
        
        # Combine all sections
        return '\n'.join(sections)
    
    def _format_web_intelligence(self, web_intelligence: Optional[Dict]) -> str:
        """Format ALL web-scraped articles into comprehensive, well-structured text for LLM."""
        
        if not web_intelligence or not web_intelligence.get('articles'):
            return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                 SECTION 11: WEB INTELLIGENCE & ARTICLES                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

No web articles available for analysis.
"""
        
        total_articles = web_intelligence.get('total_articles', 0)
        total_words = web_intelligence.get('total_words_scraped', 0)
        sources = web_intelligence.get('sources', [])
        articles = web_intelligence.get('articles', [])
        
        formatted_text = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 SECTION 11: WEB INTELLIGENCE & ARTICLES                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

11.1 WEB SCRAPING SUMMARY
───────────────────────────────────────────────────────────────────────────────
Total Articles Analyzed:                    {total_articles}
Total Words Extracted:                      {total_words:,}
Unique News Sources:                        {len(sources)}
Sources List:                               {', '.join(sources[:15])}

11.2 COMPLETE ARTICLE CONTENT (Top {min(len(articles), 10)} Articles)
───────────────────────────────────────────────────────────────────────────────
"""
        
        # Include full content from all articles
        for i, article in enumerate(articles[:10], 1):
            title = article.get('title', 'No Title')
            url = article.get('url', '#')
            source = article.get('source', 'Unknown')
            snippet = article.get('snippet', '')
            text = article.get('text', '')
            word_count = article.get('word_count', 0)
            published_date = article.get('published_date') or article.get('publish_date', 'N/A')
            search_query = article.get('search_query', '')
            position = article.get('position', i)
            
            formatted_text += f"""
{'═' * 80}
ARTICLE #{i} (Google Search Position: {position})
{'═' * 80}

Title:           {title}
Source:          {source}
URL:             {url}
Published Date:  {published_date}
Word Count:      {word_count:,}
Search Query:    {search_query}

{'─' * 80}
FULL ARTICLE CONTENT:
{'─' * 80}

"""
            
            # Include FULL article text if available
            if text and len(text) > 100:
                formatted_text += f"{text}\n\n"
            elif snippet:
                formatted_text += f"[Snippet Only]: {snippet}\n\n"
            else:
                formatted_text += "[No content available]\n\n"
            
            formatted_text += f"\n{'─' * 80}\n\n"
        
        # Add summary statistics
        formatted_text += f"""
11.3 CONTENT ANALYSIS STATISTICS
───────────────────────────────────────────────────────────────────────────────
Average Words Per Article:                  {total_words // total_articles if total_articles > 0 else 0:,}
Total Characters Extracted:                 {sum(len(a.get('text', '')) for a in articles):,}
Articles with Full Content:                 {sum(1 for a in articles if len(a.get('text', '')) > 100)}
Articles with Snippets Only:                {sum(1 for a in articles if not a.get('text') or len(a.get('text', '')) <= 100)}
"""
        
        return formatted_text
    
    def _create_analysis_prompt(self, symbol: str, financial_data: str, web_intelligence_data: str) -> list:
        """Create comprehensive, well-structured prompt for LLM analysis."""
        
        system_message = f"""You are a senior investment analyst at a top-tier investment bank with expertise in:
- Fundamental analysis and financial modeling
- Equity research and valuation techniques
- Industry analysis and competitive positioning
- Market sentiment analysis and technical indicators

Your role is to produce an institutional-grade investment research report for {symbol} that would be used by:
- Portfolio managers making buy/sell decisions
- Investment committees evaluating positions
- Wealth managers advising high-net-worth clients

ANALYSIS REQUIREMENTS:
═══════════════════════════════════════════════════════════════════════════════

You have been provided with COMPREHENSIVE data organized into 11 major sections:

SECTION 1: Company Profile & Overview
  - Basic company information (name, industry, sector, employees, CEO)
  - Current market data (price, market cap, volume, beta, ranges)
  - Business description
  - Competitive peer landscape

SECTION 2: Financial Statements (5-Year Historical)
  - Complete Income Statements (revenue, profits, margins, EPS)
  - Complete Balance Sheets (assets, liabilities, equity, working capital)
  - Complete Cash Flow Statements (operating, investing, financing cash flows)

SECTION 3: Financial Ratios & Metrics (TTM - Trailing Twelve Months)
  - Valuation ratios (P/E, P/B, P/S, PEG, EV multiples)
  - Profitability ratios (margins, ROE, ROA, ROCE)
  - Liquidity ratios (current, quick, cash ratios)
  - Leverage ratios (debt-to-equity, interest coverage)
  - Efficiency ratios (asset turnover, inventory turnover, cash conversion cycle)
  - Dividend metrics (yield, payout ratio)

SECTION 4: Growth Metrics (5-Year Trend Analysis)
  - Revenue, profit, EPS growth rates
  - Asset and equity growth
  - Free cash flow growth trajectory

SECTION 5: Financial Health Scores
  - Altman Z-Score (bankruptcy prediction)
  - Piotroski Score (financial strength)
  - Overall health indicators

SECTION 6: Analyst Ratings & Price Targets
  - Consensus ratings (Strong Buy, Buy, Hold, Sell, Strong Sell)
  - Price target ranges (high, median, low, consensus)
  - Number of analysts covering the stock

SECTION 7: Dividends & Shareholder Returns
  - Complete dividend payment history (last 20 payments)
  - Stock split history
  - Dividend consistency and growth

SECTION 8: Insider Trading Activity
  - Recent insider buy/sell transactions (last 20 trades)
  - Transaction sizes and prices
  - Ownership patterns

SECTION 9: Key Executives
  - Executive team composition
  - Compensation details
  - Leadership structure

SECTION 10: Recent News & Market Sentiment (FMP)
  - Latest company-specific news (10 articles with full summaries)
  - SEC filings from last 90 days
  - Regulatory and compliance updates

SECTION 11: Web Intelligence & Independent Articles
  - Top 10 articles from Google search results
  - FULL article content from independent financial news sources
  - Multiple perspectives on company performance and outlook
  - Recent market commentary and analysis

YOUR TASK:
═══════════════════════════════════════════════════════════════════════════════

Synthesize ALL the information across these 11 sections to produce a detailed, professional investment report with the following structure:

# Investment Research Report: [Company Name] ({symbol})

## Executive Summary (2-3 paragraphs)
- Investment thesis in 2-3 sentences
- Key findings and recommendation (BUY/HOLD/SELL)
- Price target with upside/downside potential
- Top 3 reasons to buy and top 3 risks

## 1. Company Overview & Business Model
- What the company does and how it makes money
- Market position and competitive advantages
- Key products/services and revenue streams
- Industry dynamics and market share

## 2. Financial Performance Analysis
### 2.1 Historical Trends (5-Year Analysis)
- Revenue trajectory and growth drivers
- Profitability trends (margins improving/declining?)
- Balance sheet strength evolution
- Cash flow generation quality

### 2.2 Current Financial Health
- Latest quarter/annual metrics
- Key ratio analysis (compare to industry benchmarks)
- Working capital management
- Capital structure and leverage assessment

## 3. Valuation Analysis
- Current valuation metrics vs. historical averages
- Peer comparison (vs. competitors mentioned in data)
- DCF or multiple-based valuation
- Fair value estimate with justification

## 4. Growth Prospects & Catalysts
- Near-term catalysts (next 3-6 months)
- Medium-term growth drivers (1-2 years)
- Market expansion opportunities
- Product pipeline or innovation potential

## 5. Risk Assessment
- Company-specific risks
- Industry/sector risks
- Macroeconomic sensitivities
- Balance sheet or operational risks
- Management/governance concerns

## 6. Market Sentiment & News Analysis
- What recent news/articles reveal about market perception
- Insider trading patterns (buying or selling signals?)
- Analyst consensus and target price reasonableness
- Institutional sentiment indicators

## 7. Investment Recommendation
### Clear Rating: STRONG BUY / BUY / HOLD / REDUCE / SELL
### Price Target: $XX.XX (X% upside/downside from current price)
### Time Horizon: [6-12 months]
### Confidence Level: High / Medium / Low

### Detailed Rationale:
- Why this rating? (3-5 specific data-driven reasons)
- What needs to happen for upgrade/downgrade?
- Position sizing suggestions (aggressive/moderate/conservative)

## 8. Key Metrics Summary Table
Present critical metrics in an easy-to-scan table format

CRITICAL INSTRUCTIONS:
═══════════════════════════════════════════════════════════════════════════════
✓ Use specific numbers, dates, and percentages from the provided data
✓ Compare metrics to industry averages where relevant
✓ Cite specific articles/news when discussing market sentiment
✓ Be balanced - discuss both bullish and bearish factors
✓ Make the recommendation clear and actionable
✓ Use professional financial terminology
✓ Format using clean markdown with headers, tables, and bullet points
✓ Be comprehensive but concise - aim for institutional-quality depth
✓ Integrate insights from ALL 11 sections of data provided
✓ Pay special attention to the FULL article content in Section 11
"""

        # --- CORRECTED LINE ---
        # Use .center(78) to dynamically center the title line within the 80-char box
        title_line = f"Stock Symbol: {symbol}".center(78)

        user_message = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                  COMPREHENSIVE INVESTMENT ANALYSIS REQUEST                  ║
║{title_line}║
╚══════════════════════════════════════════════════════════════════════════════╝

Please analyze the following COMPLETE dataset for {symbol} and produce a detailed,
institutional-grade investment research report following the structure outlined in
your system instructions.

The data below is organized into 11 comprehensive sections covering everything from
basic company information to web-scraped article content. Use ALL of this information
to create your analysis.

{financial_data}

{web_intelligence_data}

════════════════════════════════════════════════════════════════════════════════

DELIVERABLE:
Generate a comprehensive investment research report that:
1. Analyzes ALL sections of data provided above
2. Follows the exact structure specified in the system message
3. Provides a clear BUY/HOLD/SELL recommendation with price target
4. Uses specific numbers and quotes from the articles
5. Is written in professional, institutional-grade language
6. Includes actionable insights for portfolio managers

Begin your analysis now.
"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def generate_ai_summary(self, symbol: str, data: Dict[str, Any], 
                           web_intelligence: Optional[Dict] = None) -> str:
        """
        Generate an AI-enhanced summary report using LLM.
        
        Args:
            symbol: Stock ticker symbol
            data: Comprehensive fundamental data
            web_intelligence: Web-scraped articles and intelligence
            
        Returns:
            AI-generated comprehensive analysis
        """
        print(f"\n🤖 Generating AI-enhanced analysis for {symbol}...")
        
        try:
            # Format the data
            financial_data = self._format_financial_data(data)
            web_data = self._format_web_intelligence(web_intelligence)
            
            # Create the prompt
            messages = self._create_analysis_prompt(symbol, financial_data, web_data)
            
            # Call OpenAI API
            print(f"  📡 Calling OpenAI API ({self.model})...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            ai_summary = response.choices[0].message.content
            
            print(f"  ✅ AI analysis generated ({len(ai_summary)} characters)")
            return ai_summary
            
        except Exception as e:
            print(f"  ❌ Error generating AI summary: {e}")
            import traceback
            traceback.print_exc()
            return f"Error generating AI summary: {str(e)}"
    
    def save_ai_report(self, symbol: str, ai_summary: str, output_dir: str = "reports") -> str:
        """
        Save the AI-generated report to a markdown file.
        
        Args:
            symbol: Stock ticker symbol
            ai_summary: AI-generated analysis content
            output_dir: Directory to save reports
            
        Returns:
            Path to the saved report
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Create comprehensive report with header
        report_content = f"""# AI-Enhanced Investment Analysis: {symbol}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**AI Model:** {self.model}
**Analysis Type:** Comprehensive Fundamental Analysis

---

{ai_summary}

---

*This report was generated using AI analysis of fundamental data and web intelligence.*
*Recommendations should be verified with your own research and risk assessment.*
"""
        
        filename = os.path.join(output_dir, f"AI_Enhanced_Report_{symbol}.md")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"  💾 AI report saved to {filename}")
        return filename