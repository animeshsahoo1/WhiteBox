#final_manager.py
import functools
import psycopg2
import socket
import pathway as pw
import pandas as pd
from datetime import datetime, timezone
import json
import re

from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os

load_dotenv()

chat_model = llms.LiteLLMChat(
    model="openrouter/openai/gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

def create_final_manager(llm):
    def final_manager_node(state, name):
        company_name = state["company_of_interest"]
        symbol = company_name
        
        # Get trading agent report
        trader_report = state.get("trader_investment_plan", "")
        
        # Get risk manager report
        risk_manager_report = state.get("final_trade_decision", "")
        
        # Get the 4 analyst reports
        market_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        
        # Get current position info if available
        current_position_size = state.get("current_position_size", 0)
        account_balance = state.get("account_balance", 10000)
        
        # UDF to combine all reports
        @pw.udf
        def combine_all_reports(trader, risk, market, sentiment, news, fundamentals):
            return f"""Trading Agent Analysis:
{trader}

Risk Manager Assessment:
{risk}

Market Research Report:
{market}

Sentiment Analysis Report:
{sentiment}

News Report:
{news}

Fundamentals Report:
{fundamentals}"""

        # Combine all available reports
        all_reports = combine_all_reports(
            trader_report, 
            risk_manager_report, 
            market_report, 
            sentiment_report, 
            news_report, 
            fundamentals_report
        )
        
        # System prompt for Final Manager
        FINAL_MANAGER_SYSTEM_PROMPT = f"""You are the Chief Investment Hypothesis Generator responsible for synthesizing comprehensive multi-agent analysis into a structured investment thesis for {symbol}.

Your role is to:
1. Synthesize the Investment Analyst's perspective (bullish/bearish/neutral positioning)
2. Integrate Risk Assessment findings and scenario analysis
3. Incorporate all research dimensions (market, sentiment, news, fundamentals)
4. Generate a professional investment hypothesis with clear rationale

Analysis Context:
- Company: {symbol}
- Analysis Framework: Multi-agent consensus-based
- Reference Scenario Capital: ${account_balance}

You MUST output your hypothesis in this EXACT JSON format:
{{
  "symbol": "{symbol}",
  "investment_thesis": "<2-3 sentence summary of the core investment hypothesis>",
  "outlook": "bullish" or "bearish" or "neutral",
  "time_horizon": "<short-term/medium-term/long-term>",
  "key_catalysts": ["<catalyst 1>", "<catalyst 2>", "<catalyst 3>"],
  "primary_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "price_targets": {{
    "bull_case": <float - optimistic price target>,
    "base_case": <float - most likely price target>,
    "bear_case": <float - pessimistic price target>
  }},
  "conviction_level": "<high/medium/low>",
  "confidence_score": <float between 0-1>,
  "recommended_allocation": "<percentage or descriptor like 'overweight', 'underweight', 'neutral'>",
  "invalidation_triggers": ["<trigger 1>", "<trigger 2>"],
  "analysis_summary": "<3-4 sentence summary explaining the rationale>"
}}

Guidelines for Hypothesis Generation:

**Investment Thesis**: Concise statement of why this is a compelling opportunity or risk
**Outlook**: 
- "bullish": Positive momentum, growth catalysts, favorable risk/reward
- "bearish": Headwinds, valuation concerns, deteriorating fundamentals
- "neutral": Mixed signals, wait-and-see approach, range-bound expectations

**Time Horizon**: Based on catalyst timing and market conditions
**Key Catalysts**: Specific events or trends that could drive price movement
**Primary Risks**: Main concerns that could undermine the hypothesis
**Price Targets**: Realistic price scenarios based on valuation and technical analysis
**Conviction Level**: How strong is the evidence supporting this hypothesis
**Confidence Score**: Statistical measure of prediction reliability (0.0-1.0)
**Recommended Allocation**: Portfolio positioning guidance
**Invalidation Triggers**: Specific events that would require reassessing the hypothesis
**Analysis Summary**: Clear explanation of the reasoning and key factors

Return ONLY the JSON object, nothing else. Make it sound like professional investment research, not trading signals."""

        # Construct the final manager prompt
        final_manager_prompt = [
            {"role": "system", "content": FINAL_MANAGER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Analyze all reports and generate the comprehensive investment hypothesis:

{all_reports}

Generate the hypothesis JSON now."""}
        ]
        
        # Create a Pathway table from the prompt for processing
        manager_table = pw.debug.table_from_pandas(
            pd.DataFrame({"messages": [final_manager_prompt]})
        )

        # Pass through the model — this is the key Pathway call
        manager_response = manager_table.select(reply=llm(pw.this.messages))

        # Convert back to pandas so you can print / inspect
        manager_result = pw.debug.table_to_pandas(manager_response)
        manager_reply = manager_result["reply"].iloc[0] if not manager_result.empty else ""

        # Parse JSON from the response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', manager_reply, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', manager_reply, re.DOTALL)
                json_str = json_match.group(0) if json_match else manager_reply
            
            hypothesis_data = json.loads(json_str)
            
            # Ensure all required fields are present with defaults
            hypothesis_data.setdefault("symbol", symbol)
            hypothesis_data.setdefault("investment_thesis", "Analysis pending")
            hypothesis_data.setdefault("outlook", "neutral")
            hypothesis_data.setdefault("time_horizon", "medium-term")
            hypothesis_data.setdefault("key_catalysts", [])
            hypothesis_data.setdefault("primary_risks", [])
            hypothesis_data.setdefault("price_targets", {
                "bull_case": 0.0,
                "base_case": 0.0,
                "bear_case": 0.0
            })
            hypothesis_data.setdefault("conviction_level", "medium")
            hypothesis_data.setdefault("confidence_score", 0.5)
            hypothesis_data.setdefault("recommended_allocation", "neutral")
            hypothesis_data.setdefault("invalidation_triggers", [])
            hypothesis_data.setdefault("analysis_summary", "")
            
        except (json.JSONDecodeError, AttributeError) as e:
            # Fallback to safe default values if JSON parsing fails
            print(f"Warning: Failed to parse hypothesis JSON: {e}")
            hypothesis_data = {
                "symbol": symbol,
                "investment_thesis": "Error in analysis generation",
                "outlook": "neutral",
                "time_horizon": "medium-term",
                "key_catalysts": [],
                "primary_risks": ["Analysis error"],
                "price_targets": {
                    "bull_case": 0.0,
                    "base_case": 0.0,
                    "bear_case": 0.0
                },
                "conviction_level": "low",
                "confidence_score": 0.0,
                "recommended_allocation": "underweight",
                "invalidation_triggers": ["Parsing error"],
                "analysis_summary": f"Error parsing analysis: {str(e)}"
            }

        # === Write results out ===
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        
        # Create the final output structure
        final_output = {
            symbol: {
                "hypothesis": hypothesis_data
            }
        }
        
        full_report = f"""Hypothesis Generator - Investment Analysis
Generated: {timestamp}
Symbol: {symbol}

{json.dumps(final_output, indent=2)}

"""

        DATABASE_URL = os.getenv("DATABASE_URL")

        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            cur = conn.cursor()
            
            # Store the full hypothesis as JSONB for flexibility
            insert_query = """
            INSERT INTO hypothesis_generation (
            symbol, hypothesis_data, timestamp
            ) VALUES (%s, %s, NOW() AT TIME ZONE 'UTC')
            RETURNING id;
            """
            
            cur.execute(insert_query, (
                hypothesis_data["symbol"],
                json.dumps(hypothesis_data),  # Store full JSON
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Database error: {e}")
            if 'conn' in locals():
                conn.close()
            raise
                
        # Return structured output for pathway table
        return {
            "final_report": full_report,
            "sender": name,
            "symbol": symbol,
            "hypothesis": final_output,
            "hypothesis_data": hypothesis_data
        }
    
    return functools.partial(final_manager_node, name="Final Manager")



# if __name__ == "__main__":
#     # Initial state dictionary for testing the final manager
#     test_state = {
#         "company_of_interest": "AAPL",  # Changed to symbol format
#         "current_position_size": 0,
#         "account_balance": 10000,
        
#         "trader_investment_plan": """Trader agent Analysis 
# Generated: Monday, November 04, 2024 at 10:30 AM UTC

# **Summary of Bull Position:**
# The bull analyst emphasizes Apple's strong ecosystem, growing services revenue, and financial fortress.

# **Summary of Bear Position:**
# The bear analyst highlights regulatory risks, iPhone dependency, and slowing growth at high valuation.

# **Comparative Evaluation:**
# While both positions have merit, the regulatory headwinds and valuation concerns present near-term risks.

# **Final Reasoning:**
# Given current market conditions and mixed signals, a cautious approach is warranted.

# **Decision:**
# HOLD position with potential to add on significant dips below key support levels.

# **Investment Plan:**
# Maintain current exposure, monitor regulatory developments closely.

# FINAL TRANSACTION PROPOSAL: **HOLD**""",
        
#         "final_trade_decision": """Risk Manager Assessment

# Position Sizing: Recommend limiting exposure to 2% of portfolio
# Risk per trade: Maximum $200 (2% of $10,000)
# Leverage: Conservative 5-10x given current volatility
# Stop Loss: Recommend 3% below entry
# Key Risk Factors: Regulatory risk, China exposure, valuation""",
        
#         "market_report": """Market conditions show mixed signals with Fed maintaining higher rates.""",
        
#         "sentiment_report": """Overall sentiment cautiously optimistic but increasing hold ratings.""",
        
#         "news_report": """Recent EU investigation and China slowdown concerns.""",
        
#         "fundamentals_report": """P/E at 31.2x, Revenue growth 1.8%, Strong margins at 26.3%"""
#     }
    
#     # Create and run the final manager
#     final_manager_agent = create_final_manager(chat_model)
#     final_output = final_manager_agent(test_state)
    
#     print(final_output['final_report'])  # Changed from 'report' to 'final_report'
#     print("\n" + "="*80)
#     print("Trade Signal Output:")
#     print(json.dumps(final_output['trade_signal'], indent=2))