import functools
import pathway as pw
import pandas as pd
from datetime import datetime, timezone
import json
import re

from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os

load_dotenv()

chat_model = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
)

def create_final_manager(llm):
    def final_manager_node(state, name):
        company_name = state["company_of_interest"]
        symbol = state.get("symbol", company_name)
        
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
        FINAL_MANAGER_SYSTEM_PROMPT = f"""You are the Final Manager responsible for synthesizing all analysis and generating the final trade signal for {symbol}.

Your role is to:
1. Review the Trading Agent's recommendation (BUY/HOLD/SELL)
2. Incorporate the Risk Manager's risk assessment and position sizing guidance
3. Consider all research reports (market, sentiment, news, fundamentals)
4. Generate a precise, executable trade signal with specific parameters

Current Portfolio Context:
- Symbol: {symbol}
- Current Position Size: {current_position_size}
- Account Balance: ${account_balance}

You MUST output your decision in this EXACT JSON format:
{{
  "symbol": "{symbol}",
  "signal": "buy" or "sell" or "hold",
  "quantity": <integer - number of units to trade>,
  "profit_target": <float - target price>,
  "stop_loss": <float - stop loss price>,
  "invalidation_condition": "<string - condition that invalidates the trade>",
  "leverage": <integer between 5-40>,
  "confidence": <float between 0-1>,
  "risk_usd": <float - dollar amount at risk>
}}

Signal Guidelines:
- "buy": Initiate new long position or add to existing
- "sell": Exit position or initiate short
- "hold": Maintain current position, no changes

Quantity Calculation:
- For BUY: Calculate based on risk_usd, account balance, and risk manager's guidance
- For SELL: Use full current position size to close position
- For HOLD: Use current position size

Risk Parameters:
- Leverage should be 5-40 based on conviction and volatility
- Confidence should reflect the strength of all analyses (0.0-1.0)
- risk_usd should align with risk manager's recommendations (typically 1-3% of account)
- profit_target and stop_loss must be realistic based on technical and fundamental analysis

Invalidation Condition:
- Describe the specific event or price level that would invalidate this trade
- Examples: "Break below $150 support", "Negative earnings surprise", "Regulatory decision against company"

Return ONLY the JSON object, nothing else."""

        # Construct the final manager prompt
        final_manager_prompt = [
            {"role": "system", "content": FINAL_MANAGER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Analyze all reports and generate the final trade signal:

{all_reports}

Generate the trade signal JSON now."""}
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
            
            trade_signal_args = json.loads(json_str)
            
            # Ensure all required fields are present with defaults
            trade_signal_args.setdefault("symbol", symbol)
            trade_signal_args.setdefault("signal", "hold")
            trade_signal_args.setdefault("quantity", current_position_size)
            trade_signal_args.setdefault("profit_target", 0.0)
            trade_signal_args.setdefault("stop_loss", 0.0)
            trade_signal_args.setdefault("invalidation_condition", "No specific condition")
            trade_signal_args.setdefault("leverage", 10)
            trade_signal_args.setdefault("confidence", 0.5)
            trade_signal_args.setdefault("risk_usd", account_balance * 0.02)
            
        except (json.JSONDecodeError, AttributeError) as e:
            # Fallback to safe default values if JSON parsing fails
            print(f"Warning: Failed to parse trade signal JSON: {e}")
            trade_signal_args = {
                "symbol": symbol,
                "signal": "hold",
                "quantity": current_position_size,
                "profit_target": 0.0,
                "stop_loss": 0.0,
                "invalidation_condition": "Parsing error - hold position",
                "leverage": 10,
                "confidence": 0.0,
                "risk_usd": 0.0
            }

        # === Write results out ===
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        
        # Create the final output structure
        final_output = {
            symbol: {
                "trade_signal_args": trade_signal_args
            }
        }
        
        full_report = f"""Final Manager Trade Signal
Generated: {timestamp}
Symbol: {symbol}

{json.dumps(final_output, indent=2)}

Raw Analysis:
{manager_reply}"""
        
        # Return structured output for pathway table
        return {
            "final_report": full_report,
            "sender": name,
            "symbol": symbol,
            "trade_signal": final_output,
            "trade_signal_args": trade_signal_args
        }
    
    return functools.partial(final_manager_node, name="Final Manager")


# Example usage with sample state (commented out - uncomment to test standalone)
# if __name__ == "__main__":
#     # Initial state dictionary for testing the final manager
#     test_state = {
#         "company_of_interest": "Apple Inc.",
#         "symbol": "AAPL",
#         "current_position_size": 0,
#         "account_balance": 10000,
        
#         "trader_report": """Trader agent Analysis 
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
        
#         "risk_manager_report": """Risk Manager Assessment

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
    
#     print(final_output['report'])
#     print("\n" + "="*80)
#     print("Trade Signal Output:")
#     print(json.dumps(final_output['trade_signal'], indent=2))