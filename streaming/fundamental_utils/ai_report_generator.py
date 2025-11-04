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
        import openai
        self.openai = openai
        self.openai.api_key = self.openrouter_api_key
        
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.temperature = 0.3
        self.max_tokens = 10000
    
    def _format_financial_data(self, data: Dict[str, Any]) -> str:
        """Format financial data into a structured text for LLM."""
        
        profile = data.get('profile') or {}
        income = data.get('income_annual') or []
        balance = data.get('balance_annual') or []
        ratios = data.get('ratios_ttm') or {}
        grades = data.get('grades_consensus') or {}
        targets = data.get('price_target_consensus') or {}
        news = data.get('news') or []
        
        # Format market cap
        mkt_cap = profile.get('mktCap', 'N/A')
        if isinstance(mkt_cap, (int, float)):
            mkt_cap_str = f"${mkt_cap:,.0f}"
        else:
            mkt_cap_str = 'N/A'
        
        formatted_text = f"""
COMPANY PROFILE:
- Name: {profile.get('companyName', 'N/A')}
- Symbol: {data.get('symbol', 'N/A')}
- Industry: {profile.get('industry', 'N/A')}
- Sector: {profile.get('sector', 'N/A')}
- CEO: {profile.get('ceo', 'N/A')}
- Price: ${profile.get('price', 'N/A')}
- Market Cap: {mkt_cap_str}
- Description: {profile.get('description', 'N/A')[:500]}...

FINANCIAL METRICS (LATEST ANNUAL):
"""
        if income and balance:
            latest_income = income[0]
            latest_balance = balance[0]
            revenue = latest_income.get('revenue', 0)
            net_income = latest_income.get('netIncome', 0)
            total_assets = latest_balance.get('totalAssets', 0)
            total_liabilities = latest_balance.get('totalLiabilities', 0)
            total_equity = latest_balance.get('totalEquity', 0)
            
            formatted_text += f"""
- Revenue: ${revenue:,.0f}
- Net Income: ${net_income:,.0f}
- EPS: ${latest_income.get('eps', 'N/A')}
- Total Assets: ${total_assets:,.0f}
- Total Liabilities: ${total_liabilities:,.0f}
- Total Equity: ${total_equity:,.0f}
"""
        
        formatted_text += f"""
FINANCIAL RATIOS (TTM):
- P/E Ratio: {ratios.get('peRatioTTM', 'N/A')}
- P/B Ratio: {ratios.get('priceToBookRatioTTM', 'N/A')}
- Net Profit Margin: {ratios.get('netProfitMarginTTM', 'N/A')}
- Return on Equity: {ratios.get('returnOnEquityTTM', 'N/A')}
- Current Ratio: {ratios.get('currentRatioTTM', 'N/A')}
- Debt to Equity: {ratios.get('debtEquityRatioTTM', 'N/A')}

ANALYST CONSENSUS:
- Rating: {grades.get('consensus', 'N/A')}
- Strong Buy: {grades.get('strongBuy', 0)}
- Buy: {grades.get('buy', 0)}
- Hold: {grades.get('hold', 0)}
- Price Target (Avg): ${targets.get('targetConsensus', 'N/A')}
- Price Target Range: ${targets.get('targetLow', 'N/A')} - ${targets.get('targetHigh', 'N/A')}

RECENT NEWS HEADLINES:
"""
        for i, article in enumerate(news[:5], 1):
            formatted_text += f"{i}. {article.get('title', 'No Title')} ({article.get('publishedDate', 'N/A').split(' ')[0]})\n"
        
        return formatted_text
    
    def _format_web_intelligence(self, web_intelligence: Optional[Dict]) -> str:
        """Format web-scraped articles into structured text for LLM."""
        
        if not web_intelligence or not web_intelligence.get('articles'):
            return "\nWEB INTELLIGENCE:\nNo web articles available.\n"
        
        formatted_text = f"""
WEB INTELLIGENCE SUMMARY:
- Total Articles Analyzed: {web_intelligence.get('total_articles', 0)}
- Unique Sources: {len(web_intelligence.get('sources', []))}
- Total Words Scraped: {web_intelligence.get('total_words_scraped', 0):,}

ARTICLE DETAILS:
"""
        
        for i, article in enumerate(web_intelligence.get('articles', [])[:10], 1):
            title = article.get('title', 'No Title')
            source = article.get('source', 'Unknown')
            snippet = article.get('snippet', '')
            text = article.get('text', '')
            word_count = article.get('word_count', 0)
            
            formatted_text += f"\n--- Article {i} ---\n"
            formatted_text += f"Title: {title}\n"
            formatted_text += f"Source: {source}\n"
            formatted_text += f"Word Count: {word_count}\n"
            
            # Include full text or snippet
            if text and len(text) > 100:
                # Use first 1500 characters to stay within token limits
                formatted_text += f"Content: {text[:1500]}...\n"
            elif snippet:
                formatted_text += f"Snippet: {snippet}\n"
            
        return formatted_text
    
    def _create_analysis_prompt(self, symbol: str, financial_data: str, web_intelligence_data: str) -> list:
        """Create the prompt for LLM analysis."""
        
        system_message = f"""You are an expert financial analyst specializing in fundamental analysis and equity research.
Your task is to create a comprehensive, detailed, and actionable investment report for {symbol}.

Analyze ALL the provided data including:
1. Company profile and business overview
2. Financial statements and key metrics
3. Financial ratios and valuation metrics
4. Analyst consensus and price targets
5. Recent news and market developments
6. Web-scraped articles and intelligence

Provide a thorough analysis covering:
- Executive Summary with key investment thesis
- Business Model & Competitive Position
- Financial Health Assessment
- Valuation Analysis
- Growth Prospects and Risks
- Market Sentiment & News Analysis
- Clear BUY/HOLD/SELL recommendation with detailed reasoning
- Price target estimate with justification

Be specific, data-driven, and professional. Use markdown formatting for structure.
Include specific numbers and metrics from the data provided.
"""

        user_message = f"""Please analyze the following comprehensive data for {symbol} and create a detailed investment report:

{financial_data}

{web_intelligence_data}

Create a comprehensive, professional investment analysis report with clear sections, specific insights, and actionable recommendations.
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
            response = self.openai.ChatCompletion.create(
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
