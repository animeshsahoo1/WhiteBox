import os
import pathway as pw
from pathway.xpacks.llm.llms import OpenAIChat
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()


class FundamentalReportUpdater:
    """Maintains and updates fundamental analysis AI reports using OpenAI's LLM."""

    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory

        try:
            self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}"))
        except json.JSONDecodeError:
            print("Warning: Could not parse STOCK_COMPANY_MAP, using empty mapping")
            self.symbol_mapping = {}

        self.llm = OpenAIChat(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=0.3,
            max_tokens=10000,
        )

        os.makedirs(self.reports_directory, exist_ok=True)

    def _get_report_path(self, symbol: str) -> str:
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "fundamental_report.md")

    def _load_report(self, symbol: str) -> str:
        report_path = self._get_report_path(symbol)

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            company_name = self.symbol_mapping.get(symbol, symbol)
            initial_report = f"""# {company_name} ({symbol}) - Fundamental Analysis Report

## Executive Summary
No fundamental data analyzed yet for {company_name}.

## Company Overview
*Awaiting fundamental data...*

## Financial Performance
- **Financial Health**: N/A
- **Profitability**: N/A
- **Growth Trajectory**: N/A

## Valuation Analysis
- **Current Valuation**: N/A
- **Fair Value Estimate**: N/A

## Investment Recommendation
- **Rating**: HOLD
- **Confidence**: N/A
- **Reasoning**: Insufficient data

---
*This report is automatically updated by the AI Trading Agent*
*Last Analysis: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(initial_report)
            return initial_report

    def _format_number(self, value, prefix='', suffix='', decimals=0):
        """Helper to format numbers safely"""
        if value is None or value == 'N/A':
            return 'N/A'
        if isinstance(value, (int, float)):
            if decimals > 0:
                return f"{prefix}{value:,.{decimals}f}{suffix}"
            else:
                return f"{prefix}{value:,.0f}{suffix}"
        return str(value)

    def _format_fundamental_data(self, data_dict: dict) -> str:
        """Format fundamental data into comprehensive text for LLM analysis."""
        
        # Extract data - it's already a dict with converted values
        data = data_dict
        
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
        web_intelligence = data.get('web_intelligence') or {}
        
        # Build comprehensive formatted text
        sections = []
        
        # SECTION 1: Company Profile
        section_1 = f"""
## SECTION 1: COMPANY PROFILE & OVERVIEW

**Company Name:** {profile.get('companyName', 'N/A')}
**Stock Symbol:** {data.get('symbol', 'N/A')}
**Exchange:** {profile.get('exchangeShortName', 'N/A')}
**Industry:** {profile.get('industry', 'N/A')}
**Sector:** {profile.get('sector', 'N/A')}
**CEO:** {profile.get('ceo', 'N/A')}
**Employees:** {self._format_number(profile.get('fullTimeEmployees'))}

**Current Price:** ${profile.get('price', 'N/A')}
**Market Cap:** {self._format_number(profile.get('mktCap'), prefix='$')}
**52-Week Range:** {profile.get('range', 'N/A')}
**Beta:** {profile.get('beta', 'N/A')}

**Business Description:**
{profile.get('description', 'No description available.')}

**Peer Companies:** {', '.join(peers) if peers else 'N/A'}
"""
        sections.append(section_1)
        
        # SECTION 2: Financial Statements (latest 3 years)
        section_2 = "\n## SECTION 2: FINANCIAL STATEMENTS (Latest 3 Years)\n\n"
        
        if income_annual:
            section_2 += "### Income Statement:\n"
            for i, stmt in enumerate(income_annual[:3], 1):
                year = stmt.get('date', 'N/A')
                section_2 += f"""
**Year {i} ({year}):**
- Revenue: {self._format_number(stmt.get('revenue', 0), prefix='$')}
- Gross Profit: {self._format_number(stmt.get('grossProfit', 0), prefix='$')}
- Operating Income: {self._format_number(stmt.get('operatingIncome', 0), prefix='$')}
- Net Income: {self._format_number(stmt.get('netIncome', 0), prefix='$')}
- EPS: {self._format_number(stmt.get('eps', 0), prefix='$', decimals=4)}
- EBITDA: {self._format_number(stmt.get('ebitda', 0), prefix='$')}
"""
        
        if balance_annual:
            section_2 += "\n### Balance Sheet:\n"
            for i, stmt in enumerate(balance_annual[:3], 1):
                year = stmt.get('date', 'N/A')
                section_2 += f"""
**Year {i} ({year}):**
- Total Assets: {self._format_number(stmt.get('totalAssets', 0), prefix='$')}
- Current Assets: {self._format_number(stmt.get('totalCurrentAssets', 0), prefix='$')}
- Cash: {self._format_number(stmt.get('cashAndCashEquivalents', 0), prefix='$')}
- Total Liabilities: {self._format_number(stmt.get('totalLiabilities', 0), prefix='$')}
- Long-term Debt: {self._format_number(stmt.get('longTermDebt', 0), prefix='$')}
- Total Equity: {self._format_number(stmt.get('totalEquity', 0), prefix='$')}
"""
        
        if cashflow_annual:
            section_2 += "\n### Cash Flow Statement:\n"
            for i, stmt in enumerate(cashflow_annual[:3], 1):
                year = stmt.get('date', 'N/A')
                section_2 += f"""
**Year {i} ({year}):**
- Operating Cash Flow: {self._format_number(stmt.get('operatingCashFlow', 0), prefix='$')}
- Free Cash Flow: {self._format_number(stmt.get('freeCashFlow', 0), prefix='$')}
- Capital Expenditure: {self._format_number(stmt.get('capitalExpenditure', 0), prefix='$')}
- Dividends Paid: {self._format_number(stmt.get('dividendsPaid', 0), prefix='$')}
"""
        
        sections.append(section_2)
        
        # SECTION 3: Financial Ratios (TTM)
        section_3 = f"""
## SECTION 3: FINANCIAL RATIOS & METRICS (TTM)

**Valuation Ratios:**
- P/E Ratio: {ratios_ttm.get('peRatioTTM', 'N/A')}
- P/B Ratio: {ratios_ttm.get('priceToBookRatioTTM', 'N/A')}
- P/S Ratio: {ratios_ttm.get('priceToSalesRatioTTM', 'N/A')}
- PEG Ratio: {ratios_ttm.get('pegRatioTTM', 'N/A')}

**Profitability Ratios:**
- Gross Profit Margin: {ratios_ttm.get('grossProfitMarginTTM', 'N/A')}
- Operating Profit Margin: {ratios_ttm.get('operatingProfitMarginTTM', 'N/A')}
- Net Profit Margin: {ratios_ttm.get('netProfitMarginTTM', 'N/A')}
- ROE: {ratios_ttm.get('returnOnEquityTTM', 'N/A')}
- ROA: {ratios_ttm.get('returnOnAssetsTTM', 'N/A')}

**Liquidity Ratios:**
- Current Ratio: {ratios_ttm.get('currentRatioTTM', 'N/A')}
- Quick Ratio: {ratios_ttm.get('quickRatioTTM', 'N/A')}

**Leverage Ratios:**
- Debt-to-Equity: {ratios_ttm.get('debtEquityRatioTTM', 'N/A')}
- Interest Coverage: {ratios_ttm.get('interestCoverageTTM', 'N/A')}

**Dividend Metrics:**
- Dividend Yield: {ratios_ttm.get('dividendYieldTTM', 'N/A')}
"""
        sections.append(section_3)
        
        # SECTION 4: Growth Metrics
        section_4 = "\n## SECTION 4: GROWTH METRICS\n\n"
        if growth_annual:
            for i, growth in enumerate(growth_annual[:3], 1):
                year = growth.get('date', 'N/A')
                section_4 += f"""
**Year {i} ({year}):**
- Revenue Growth: {growth.get('revenueGrowth', 'N/A')}
- Net Income Growth: {growth.get('netIncomeGrowth', 'N/A')}
- EPS Growth: {growth.get('epsgrowth', 'N/A')}
- Free Cash Flow Growth: {growth.get('freeCashFlowGrowth', 'N/A')}
"""
        sections.append(section_4)
        
        # SECTION 5: Analyst Ratings
        section_5 = f"""
## SECTION 5: ANALYST RATINGS & PRICE TARGETS

**Consensus Rating:** {grades.get('consensus', 'N/A')}
- Strong Buy: {grades.get('strongBuy', 0)}
- Buy: {grades.get('buy', 0)}
- Hold: {grades.get('hold', 0)}
- Sell: {grades.get('sell', 0)}

**Price Targets:**
- Target Consensus: ${targets.get('targetConsensus', 'N/A')}
- Target High: ${targets.get('targetHigh', 'N/A')}
- Target Low: ${targets.get('targetLow', 'N/A')}
- Number of Analysts: {targets.get('numberOfAnalysts', 'N/A')}
"""
        sections.append(section_5)
        
        # SECTION 6: Recent News
        section_6 = "\n## SECTION 6: RECENT NEWS & MARKET SENTIMENT\n\n"
        if news:
            section_6 += "**Recent News Headlines:**\n"
            for i, article in enumerate(news[:5], 1):
                section_6 += f"{i}. [{article.get('publishedDate', 'N/A')}] {article.get('title', 'No Title')} - {article.get('site', 'Unknown')}\n"
        sections.append(section_6)
        
        # SECTION 7: Web Intelligence (if available)
        if web_intelligence and web_intelligence.get('articles'):
            section_7 = f"""
## SECTION 7: WEB INTELLIGENCE & COMPREHENSIVE ARTICLES

**Total Articles Analyzed:** {web_intelligence.get('total_articles', 0)}
**Total Words Extracted:** {web_intelligence.get('total_words_scraped', 0):,}
**Sources:** {', '.join(web_intelligence.get('sources', [])[:10])}

**Top Articles with Full Content:**
"""
            articles = web_intelligence.get('articles', [])
            for i, article in enumerate(articles[:5], 1):
                title = article.get('title', 'No Title')
                source = article.get('source', 'Unknown')
                text = article.get('text', article.get('snippet', ''))
                section_7 += f"""
### Article {i}: {title}
**Source:** {source}
**Content:** {text[:1000]}...

"""
            sections.append(section_7)
        
        return '\n'.join(sections)

    def _create_analysis_prompt(self, symbol: str, current_report: str, fundamental_data: str) -> list[dict]:
        """Create comprehensive analysis prompt for LLM."""
        
        company_name = self.symbol_mapping.get(symbol, symbol)
        
        system_message = f"""You are a senior investment analyst specializing in fundamental analysis for {company_name} ({symbol}).
Your task is to update the comprehensive fundamental analysis report by analyzing the new fundamental data provided.

Focus on:
1. **Financial Health**: Analyze balance sheet strength, liquidity, and solvency
2. **Profitability**: Assess margins, returns, and efficiency metrics
3. **Growth Trajectory**: Evaluate revenue, earnings, and cash flow growth
4. **Valuation**: Determine if the stock is overvalued, fairly valued, or undervalued
5. **Investment Quality**: Consider competitive position, management quality, and sustainability
6. **Analyst Consensus**: Incorporate Wall Street analyst ratings and price targets
7. **Recent Developments**: Analyze news, SEC filings, and web intelligence
8. **Investment Recommendation**: Provide clear BUY/HOLD/SELL with price target and confidence level

Structure your report professionally with:
- Executive Summary (investment thesis and recommendation)
- Company Overview & Business Model
- Financial Performance Analysis
- Valuation Analysis
- Growth Prospects & Catalysts
- Risk Assessment
- Investment Recommendation (with specific price target and timeframe)

Use specific numbers, ratios, and metrics from the data. Be balanced in presenting both opportunities and risks.
Keep the report concise, actionable, and well-structured in markdown format.
Always update the "Last Analysis" timestamp at the bottom.
"""

        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        user_message = f"""Here is the CURRENT REPORT for {company_name} ({symbol}):

{current_report}

---

Here is the NEW FUNDAMENTAL DATA to analyze and incorporate:

{fundamental_data}

---

TASK: Update the comprehensive fundamental analysis report by:
1. Analyzing all financial statements and metrics
2. Evaluating the company's financial health and profitability
3. Assessing valuation using multiple approaches (P/E, P/B, DCF considerations)
4. Incorporating analyst consensus and price targets
5. Analyzing recent news and web intelligence for market sentiment
6. Providing a clear investment recommendation (BUY/HOLD/SELL)
7. Setting a price target with upside/downside potential
8. Updating the timestamp to: {current_time} UTC

Return ONLY the updated markdown report. Do not include explanations outside the report."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]


def process_fundamental_stream(
    fundamental_table: pw.Table, reports_directory: str = "./reports/fundamental"
) -> pw.Table:
    """Process fundamental data stream and create/update AI-enhanced reports."""

    os.makedirs(reports_directory, exist_ok=True)
    report_updater = FundamentalReportUpdater(reports_directory=reports_directory)

    @pw.reducers.stateful_many
    def update_fundamental_report_reducer(
        current_state: tuple[str, str] | None, data_batch: list[tuple[list, int]]
    ) -> str:
        """Stateful reducer to maintain and update fundamental reports."""
        
        # Helper to convert pw.Json to dict/list
        def safe_convert(obj):
            if obj is None:
                return None
            
            # Check if it's a pw.Json object
            if hasattr(obj, 'value'):
                # If the underlying value is None, return None
                if obj.value is None:
                    return None
                
                # Try to convert based on type
                if hasattr(obj, 'as_dict'):
                    try:
                        return obj.as_dict()
                    except (ValueError, AttributeError):
                        return None
                        
                if hasattr(obj, 'as_list'):
                    try:
                        return obj.as_list()
                    except (ValueError, AttributeError):
                        return None
            
            # If it's already a regular Python object, return as is
            return obj
        
        # Extract data from batch
        data_items = []
        symbol = None

        for row_values, count in data_batch:
            if count > 0:
                if symbol is None:
                    symbol = row_values[0]
                for _ in range(count):
                    data_items.append(row_values[1:])

        # Load or initialize report
        if current_state is None:
            if symbol is None:
                return None
            current_report = report_updater._load_report(symbol)
        else:
            symbol, current_report = current_state

        if not data_items:
            return current_report

        # Take the latest data item (most recent fundamental data)
        latest_data = data_items[-1]
        
        # Reconstruct the full data dictionary from row values
        # The order matches get_output_schema(): profile, peers, income_annual, etc.
        # Convert all pw.Json objects to Python dicts/lists
        data_dict = {
            'symbol': symbol,
            'profile': safe_convert(latest_data[0]) or {},
            'peers': safe_convert(latest_data[1]) or [],
            'income_annual': safe_convert(latest_data[2]) or [],
            'balance_annual': safe_convert(latest_data[3]) or [],
            'cashflow_annual': safe_convert(latest_data[4]) or [],
            'ratios_ttm': safe_convert(latest_data[5]) or {},
            'growth_annual': safe_convert(latest_data[6]) or [],
            'scores': safe_convert(latest_data[7]) or [],
            'grades_consensus': safe_convert(latest_data[8]) or {},
            'price_target_consensus': safe_convert(latest_data[9]) or {},
            'dividends': safe_convert(latest_data[10]) or [],
            'splits': safe_convert(latest_data[11]) or [],
            'insider_trades': safe_convert(latest_data[12]) or [],
            'executives': safe_convert(latest_data[13]) or [],
            'news': safe_convert(latest_data[14]) or [],
            'sec_filings': safe_convert(latest_data[15]) or [],
            'web_intelligence': safe_convert(latest_data[16]) or {} if len(latest_data) > 16 else {}
        }

        # Format the fundamental data
        formatted_data = report_updater._format_fundamental_data(data_dict)

        # Create analysis prompt
        messages = report_updater._create_analysis_prompt(
            symbol, current_report, formatted_data
        )
        
        return messages

    @pw.udf
    def _save_report(symbol: str, report_content: str) -> str:
        """UDF to save the report to filesystem."""
        report_path = report_updater._get_report_path(symbol)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(
            f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Saved fundamental report for {symbol} to {report_path}"
        )
        return report_content

    # Group by symbol and apply the reducer
    prompts_table = fundamental_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        prompts=update_fundamental_report_reducer(
            pw.this.symbol,
            pw.this.profile,
            pw.this.peers,
            pw.this.income_annual,
            pw.this.balance_annual,
            pw.this.cashflow_annual,
            pw.this.ratios_ttm,
            pw.this.growth_annual,
            pw.this.scores,
            pw.this.grades_consensus,
            pw.this.price_target_consensus,
            pw.this.dividends,
            pw.this.splits,
            pw.this.insider_trades,
            pw.this.executives,
            pw.this.news,
            pw.this.sec_filings,
            pw.this.web_intelligence,
        ),
    )

    # Generate AI report using LLM
    response_table = prompts_table.select(
        symbol=pw.this.symbol,
        response=_save_report(pw.this.symbol, report_updater.llm(pw.this.prompts))
    )

    return response_table
