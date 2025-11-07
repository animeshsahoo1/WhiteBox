import functools
from datetime import datetime, timezone
from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os
import pandas as pd
import pathway as pw
import pprint
import psycopg2

load_dotenv()
chat_model = llms.OpenAIChat(
        model="gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
def create_risk_manager(llm):
    def risk_manager_node(state, name):
        company_name = state["company_of_interest"]

        risky_view = state.get("risky_analysis", "")
        safe_view = state.get("safe_analysis", "")
        neutral_view = state.get("neutral_analysis", "")

        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["trader_investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        prompt = f"""
Context / Inputs (use these in your reasoning):
- Instrument / Ticker: {company_name}
  (Fields you should consider if present: coin, signal, quantity, profit_target, stop_loss, invalidation_condition, leverage, confidence, risk_usd)
- Trader / Investment Plan: {trader_plan}
- Market Context:
 {curr_situation}
- RISKY VIEW:
{risky_view}
- NEUTRAL VIEW:
{neutral_view}
- SAFE VIEW:
{safe_view}

Produce the report with the exact labeled sections below (each section short & actionable). Use absolute prices where possible and show the short derivation/formula for any numeric suggestion you provide. If required numeric inputs are missing, explicitly call out which values are missing and describe how to compute the numbers once available.

REQUIRED REPORT SECTIONS (exact headers):

1) EXECUTIVE SUMMARY
- 1–2 sentences summarizing the nominal trade signal (e.g., "Signal: BUY (from Risk Manager) for COIN") and the immediate risk posture.

2) SIGNAL BREAKDOWN & IMPLICATIONS
- Explain what the declared `signal` means in this context (buy/sell/hold).
- If `quantity` is provided, comment whether size is reasonable given current_price / portfolio_value / risk_per_trade.
- If `quantity` not provided, describe a clear formula to compute it (briefly show the calculation using available fields).

3) PROFIT TARGET & STOP LOSS REVIEW
- If `profit_target` and `stop_loss` are provided, validate whether they are consistent with typical ATR-based rules or a sensible RR ratio (show short formula, e.g., "stop = entry - 1.5*ATR").
- If numeric inputs missing, state "insufficient numeric inputs" and list which ones (e.g., current_price, ATR).
- Give a recommended absolute stop and target (rounded to 2 decimals) or explain why you cannot.

4) INVALIDATION CONDITIONS (1–3 bullets)
- Interpret the provided `invalidation_condition` (if present) and/or suggest robust invalidation(s) in <= 100 characters each.

5) LEVERAGE, CONFIDENCE & RISK_USD
- Comment on whether the chosen `leverage` (if present) is consistent with the stop distance and `risk_usd`.
- Compute or validate `risk_usd = quantity * abs(entry - stop)` if numbers exist; otherwise show the formula and say which inputs are missing.
- Provide a suggested `confidence` score (0.00–1.00) and a one-line justification.

6) TOP RISKS & MITIGATIONS (3–6 bullets)
- List prioritized, actionable risks (market, liquidity, regulatory, fundamental, on-chain / exchange risks).
- For each risk add a concrete mitigation (e.g., tighter stop, staggered sizing, limit-only execution, hedging).

7) QUICK ACTIONS (1–3 bullets)
- Immediate steps the trading desk should take (e.g., "Place stop at $X", "Reduce leverage to Y", "Wait for confirmation candle").

END with exactly one final line (no extra text) prefixed:
RECOMMENDED NEXT STEP: <single sentence>

Make sure the report is written for a human trader / risk manager and does not contain JSON or machine keys. Keep sections compact and clearly labeled.
"""

        # IMPORTANT FIX: wrap the prompt as a list of chat-message objects so OpenAI receives proper structure
        # The DataFrame cell must contain a Python list of dicts: [{"role": "user", "content": prompt}]
        prompt_table = pw.debug.table_from_pandas(
            pd.DataFrame({"messages": [[{"role": "user", "content": prompt}]]})
        )

        # Pass through the model — Pathway LLM invocation
        try:
            response_table = prompt_table.select(reply=llm(pw.this.messages))
            response_df = pw.debug.table_to_pandas(response_table)
            llm_reply = response_df["reply"].iloc[0] if (not response_df.empty and "reply" in response_df.columns) else ""
        except Exception as e:
            # helpful error message for troubleshooting
            llm_reply = f"ERROR: LLM call failed: {e}"
        lm_text = llm_reply or ""

        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Risk Manager Risk Analysis - {company_name}
Generated: {timestamp}

{lm_text}"""

        # === Database Integration ===
        DATABASE_URL = os.getenv("DATABASE_URL")
        
        # Get graph_id (trade_date) from state if available
        graph_id = state.get("graph_id") or state.get("trade_date")

        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            cur = conn.cursor()
            
            insert_query = """
            INSERT INTO graph_reports (
                graph_id, symbol, report_type, timestamp, report_body
            ) VALUES (%s, %s, %s, NOW() AT TIME ZONE 'UTC', %s)
            RETURNING id;
            """
            
            cur.execute(insert_query, (
                graph_id,
                company_name,
                "risk_manager",  # report_type for risk manager
                full_report,
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Database error: {e}")
            if 'conn' in locals():
                conn.close()
            raise

        return {
            "final_trade_decision": full_report,
            "sender": name,
        }

    # return a named partial, matching your other nodes
    return functools.partial(risk_manager_node, name="RiskManager")


# ============================================================================
# TESTING CODE - Uncomment to test the risk manager independently
# ============================================================================
# if __name__ == "__main__":
    
#     # Test state dictionary with sample data
#     test_state = {
#         "company_of_interest": "AAPL",  # Symbol/ticker
#         "graph_id": "test_trade_001",  # Or use "trade_date": "2024-11-07"
        
#         # Required analysis inputs
#         "risky_analysis": """RISKY VIEW: Aggressive long position recommended. 
# Apple shows strong momentum with potential 15% upside. 
# Recommend 3x leverage with tight stops.""",
        
#         "safe_analysis": """SAFE VIEW: Conservative approach warranted.
# Wait for pullback to $170 support before entry.
# Maximum 1x leverage, risk only 1% of portfolio.""",
        
#         "neutral_analysis": """NEUTRAL VIEW: Mixed signals present.
# Technical indicators neutral, fundamentals solid but priced in.
# Consider 50% position with 1.5x leverage.""",
        
#         # Required reports from other agents
#         "market_report": """Market Research Report:
# SPY trending upward, VIX at 15 (low volatility).
# Tech sector showing strength, rotation into large caps.
# Fed maintaining rates, no immediate policy changes expected.""",
        
#         "sentiment_report": """Sentiment Analysis:
# Social media: 65% bullish mentions for AAPL
# Analyst ratings: 12 Buy, 5 Hold, 2 Sell
# Options flow: Slightly bullish with call/put ratio at 1.3""",
        
#         "news_report": """Recent News:
# - Q4 earnings beat expectations by 5%
# - New iPhone sales strong in Asia
# - Services revenue up 12% YoY
# - Minor regulatory concerns in EU (minor impact)""",
        
#         "fundamentals_report": """Fundamentals Report:
# P/E Ratio: 31.2x (slightly above sector average)
# Revenue Growth: 1.8% YoY
# Profit Margin: 26.3%
# Cash Position: $166B
# Debt/Equity: 1.8 (manageable)
# Current Price: $175.50""",
        
#         "trader_investment_plan": """Trader Investment Plan:
# Signal: BUY
# Entry: $175.50
# Target: $185.00 (5.4% upside)
# Stop Loss: $170.00 (3.1% downside)
# Position Size: 100 shares
# Risk/Reward Ratio: 1.7:1
# Recommended Leverage: 2x
# Confidence: 0.72"""
#     }
    
#     # Create and execute the risk manager
#     print("="*80)
#     print("TESTING RISK MANAGER WITH DATABASE INTEGRATION")
#     print("="*80)
    
#     risk_manager_agent = create_risk_manager(chat_model)
#     result = risk_manager_agent(test_state)
    
#     print("\n" + result['final_trade_decision'])
#     print("\n" + "="*80)
#     print("Test completed successfully!")
#     print("Check your Supabase database 'reports' table for the new entry.")
#     print("="*80)