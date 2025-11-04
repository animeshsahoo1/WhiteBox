import functools
from datetime import datetime, timezone
from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os
import pandas as pd
import pathway as pw
import pprint

def create_risk_manager(llm):
    def risk_manager_node(state, name):
        company_name = state["company_of_interest"]
        risk_debate_state = state["risk_debate_state"]

        risky_view = risk_debate_state["risky_response"]
        safe_view = risk_debate_state["safe_response"]
        neutral_view = risk_debate_state["neutral_response"]

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

        return {
            "final_trade_decision": full_report,
            "sender": name,
        }

    # return a named partial, matching your other nodes
    return functools.partial(risk_manager_node, name="RiskManager")


# Things to optimize -> 
# Precompute all numeric values (risk, RR, stops) in Python.
# Decide one source of truth for stop / risk_usd.
# Add a system message for consistent LLM behavior.
# Trim long reports before sending to LLM.
# Save outputs (report + metrics) to file for audit.
# Validate LLM output vs computed numbers.
# Add retry + error handling.
# Keep consistent rounding / formatting.

# ---------------------------------------------------------
# SAMPLE RUN CASE
# ---------------------------------------------------------

# # Example Memory (same as before)
# class DummyMemory:
#     def get_memories(self, curr_situation, n_matches=2):
#         return [
#             {"recommendation": "Previously: reduce leverage on regulatory noise."},
#             {"recommendation": "Previously: ATR-based stop at 1.5x ATR worked well."}
#         ]


# def run_demo():
#     load_dotenv()
#     api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         raise ValueError("❌ Missing OPENAI_API_KEY in your .env file!")

#     chat_model = llms.OpenAIChat(
#         model="gpt-4o-mini",   # or whichever model you prefer
#         temperature=0.7,
#         api_key=api_key,
#     )

#     memory = DummyMemory()

#     initial_state = {
#         "company_of_interest": "Apple Inc. (AAPL)",
#         "market_report": "Fed holds rates steady; markets slightly bullish.",
#         "sentiment_report": "Investors moderately optimistic post-earnings.",
#         "news_report": "Apple expands Vision Pro availability; DOJ case ongoing.",
#         "fundamentals_report": "Revenue growth 1.8%, Net Margin 26%.",
#         "investment_plan": "Add exposure on dips; moderate leverage (1–2x).",
#         "trade_signal_args": {
#             "signal": "BUY",
#             "quantity": 100,
#             "profit_target": 235.0,
#             "stop_loss": 195.0,
#             "leverage": 1,
#             "confidence": 0.75,
#             "risk_usd": 4000
#         },
#         "current_price": 210.3,
#         "atr": 2.5,
#         "portfolio_value": 150000,
#         "risk_per_trade": 0.02,
#         "risk_debate_state": {"history": "Bull and bear analysts debated risk last week."}
#     }

#     risk_node_partial = create_risk_manager(chat_model, memory)
#     output = risk_node_partial(initial_state, name="RiskManager")

#     print("\n\n=== 🧠 HUMAN-READABLE RISK REPORT ===\n")
#     print(output["report"])

#     print("\n\n=== 🧩 STRUCTURED OUTPUT ===\n")
#     pp = pprint.PrettyPrinter(indent=2, width=120)
#     pp.pprint(output)


# if __name__ == "__main__":
#     run_demo()

# # Sample output: 
# # root@53da62d6a340:/app# cd trading_agents
# # bash: cd: trading_agents: No such file or directory
# # root@53da62d6a340:/app# ls
# # Dockerfile  all_agents  graph  requirements.txt
# # root@53da62d6a340:/app# python all_agents/managers/risk_manager.py 
# # /usr/local/lib/python3.11/site-packages/fs/__init__.py:4: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
# #   __import__("pkg_resources").declare_namespace(__name__)  # type: ignore
# # [2025-11-03T19:43:44]:INFO:Preparing Pathway computation
# # [2025-11-03T19:43:44]:INFO:{"_type": "openai_chat_request", "kwargs": {"temperature": 0.7, "model": "gpt-4o-mini"}, "id": "9e885e99", "messages": "[{'role': 'user', 'content': 'DO NOT RETURN JSON OR ANY MACHINE-ONLY SCHEMA. Produce a concise, huma..."}
# # [2025-11-03T19:43:54]:INFO:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
# # [2025-11-03T19:43:54]:INFO:{"_type": "openai_chat_response", "response": "1) EXECUTIVE SUMMARY  \nSignal: BUY (from Risk Mana...", "id": "9e885e99"}
# # [2025-11-03T19:43:54]:INFO:subscribe-0: Done writing 1 entries, closing data sink. Current batch writes took: 0 ms. All writes so far took: 0 ms.


# # === 🧠 HUMAN-READABLE RISK REPORT ===

# # Risk Manager Risk Analysis - Apple Inc. (AAPL)
# # Generated: Monday, November 03, 2025 at 07:43 PM UTC

# # 1) EXECUTIVE SUMMARY  
# # Signal: BUY (from Risk Manager) for AAPL. The immediate risk posture is moderate, with potential volatility stemming from regulatory concerns and market sentiment.

# # 2) SIGNAL BREAKDOWN & IMPLICATIONS  
# # The declared signal to buy indicates a belief that AAPL will appreciate in value. With a quantity of 100 shares at a current price of $210.3 and a portfolio value of $150,000, this represents approximately 1.33% of the portfolio, which is reasonable given the risk per trade of 2%.

# # 3) PROFIT TARGET & STOP LOSS REVIEW  
# # The profit target of $235.0 and stop loss of $195.0 imply a risk-reward (RR) ratio of approximately 1.6:1, which is favorable. The calculated stop should follow the ATR-based rule: stop = entry - 1.5 * ATR = 210.3 - 1.5 * 2.5 = 205.3. Thus, a recommended stop loss is $205.30.

# # 4) INVALIDATION CONDITIONS  
# # - Close position if the price falls below $205.30.  
# # - Monitor regulatory developments regarding the DOJ case.  
# # - Exit if market sentiment shifts significantly bearish.

# # 5) LEVERAGE, CONFIDENCE & RISK_USD  
# # The chosen leverage of 1 is appropriate given the risk profile and stop distance. Calculating risk: risk_usd = quantity * abs(entry - stop) = 100 * (210.3 - 205.3) = $500. Given the stated risk_usd of $4000, this indicates a need to reassess position size or stop placement. Suggested confidence score is 0.75, reflecting moderate optimism amid cautious market signals.

# # 6) TOP RISKS & MITIGATIONS  
# # - **Market Risk**: Potential for sudden downturns; mitigation: set tighter stops.  
# # - **Regulatory Risk**: Ongoing DOJ case could impact share price; mitigation: monitor news closely and be ready to exit.  
# # - **Volatility Risk**: ATR indicates possible price swings; mitigation: consider staggered entry to average price.

# # 7) QUICK ACTIONS  
# # - Place stop at $205.30.  
# # - Monitor news related to the DOJ case for potential impacts.  
# # - Reassess position size if market volatility increases.

# # RECOMMENDED NEXT STEP: Implement the trade with a stop at $205.30 and monitor regulatory developments closely.


# # === 🧩 STRUCTURED OUTPUT ===

# # { 'final_trade_decision': '1) EXECUTIVE SUMMARY  \n'
# #                           'Signal: BUY (from Risk Manager) for AAPL. The immediate risk posture is moderate, with '
# #                           'potential volatility stemming from regulatory concerns and market sentiment.\n'
# #                           '\n'
# #                           '2) SIGNAL BREAKDOWN & IMPLICATIONS  \n'
# #                           'The declared signal to buy indicates a belief that AAPL will appreciate in value. With a '
# #                           'quantity of 100 shares at a current price of $210.3 and a portfolio value of $150,000, this '
# #                           'represents approximately 1.33% of the portfolio, which is reasonable given the risk per '
# #                           'trade of 2%.\n'
# #                           '\n'
# #                           '3) PROFIT TARGET & STOP LOSS REVIEW  \n'
# #                           'The profit target of $235.0 and stop loss of $195.0 imply a risk-reward (RR) ratio of '
# #                           'approximately 1.6:1, which is favorable. The calculated stop should follow the ATR-based '
# #                           'rule: stop = entry - 1.5 * ATR = 210.3 - 1.5 * 2.5 = 205.3. Thus, a recommended stop loss '
# #                           'is $205.30.\n'
# #                           '\n'
# #                           '4) INVALIDATION CONDITIONS  \n'
# #                           '- Close position if the price falls below $205.30.  \n'
# #                           '- Monitor regulatory developments regarding the DOJ case.  \n'
# #                           '- Exit if market sentiment shifts significantly bearish.\n'
# #                           '\n'
# #                           '5) LEVERAGE, CONFIDENCE & RISK_USD  \n'
# #                           'The chosen leverage of 1 is appropriate given the risk profile and stop distance. '
# #                           'Calculating risk: risk_usd = quantity * abs(entry - stop) = 100 * (210.3 - 205.3) = $500. '
# #                           'Given the stated risk_usd of $4000, this indicates a need to reassess position size or stop '
# #                           'placement. Suggested confidence score is 0.75, reflecting moderate optimism amid cautious '
# #                           'market signals.\n'
# #                           '\n'
# #                           '6) TOP RISKS & MITIGATIONS  \n'
# #                           '- **Market Risk**: Potential for sudden downturns; mitigation: set tighter stops.  \n'
# #                           '- **Regulatory Risk**: Ongoing DOJ case could impact share price; mitigation: monitor news '
# #                           'closely and be ready to exit.  \n'
# #                           '- **Volatility Risk**: ATR indicates possible price swings; mitigation: consider staggered '
# #                           'entry to average price.\n'
# #                           '\n'
# #                           '7) QUICK ACTIONS  \n'
# #                           '- Place stop at $205.30.  \n'
# #                           '- Monitor news related to the DOJ case for potential impacts.  \n'
# #                           '- Reassess position size if market volatility increases.\n'
# #                           '\n'
# #                           'RECOMMENDED NEXT STEP: Implement the trade with a stop at $205.30 and monitor regulatory '
# #                           'developments closely.',
# #   'messages': [ '1) EXECUTIVE SUMMARY  \n'
# #                 'Signal: BUY (from Risk Manager) for AAPL. The immediate risk posture is moderate, with potential '
# #                 'volatility stemming from regulatory concerns and market sentiment.\n'
# #                 '\n'
# #                 '2) SIGNAL BREAKDOWN & IMPLICATIONS  \n'
# #                 'The declared signal to buy indicates a belief that AAPL will appreciate in value. With a quantity of '
# #                 '100 shares at a current price of $210.3 and a portfolio value of $150,000, this represents '
# #                 'approximately 1.33% of the portfolio, which is reasonable given the risk per trade of 2%.\n'
# #                 '\n'
# #                 '3) PROFIT TARGET & STOP LOSS REVIEW  \n'
# #                 'The profit target of $235.0 and stop loss of $195.0 imply a risk-reward (RR) ratio of approximately '
# #                 '1.6:1, which is favorable. The calculated stop should follow the ATR-based rule: stop = entry - 1.5 * '
# #                 'ATR = 210.3 - 1.5 * 2.5 = 205.3. Thus, a recommended stop loss is $205.30.\n'
# #                 '\n'
# #                 '4) INVALIDATION CONDITIONS  \n'
# #                 '- Close position if the price falls below $205.30.  \n'
# #                 '- Monitor regulatory developments regarding the DOJ case.  \n'
# #                 '- Exit if market sentiment shifts significantly bearish.\n'
# #                 '\n'
# #                 '5) LEVERAGE, CONFIDENCE & RISK_USD  \n'
# #                 'The chosen leverage of 1 is appropriate given the risk profile and stop distance. Calculating risk: '
# #                 'risk_usd = quantity * abs(entry - stop) = 100 * (210.3 - 205.3) = $500. Given the stated risk_usd of '
# #                 '$4000, this indicates a need to reassess position size or stop placement. Suggested confidence score '
# #                 'is 0.75, reflecting moderate optimism amid cautious market signals.\n'
# #                 '\n'
# #                 '6) TOP RISKS & MITIGATIONS  \n'
# #                 '- **Market Risk**: Potential for sudden downturns; mitigation: set tighter stops.  \n'
# #                 '- **Regulatory Risk**: Ongoing DOJ case could impact share price; mitigation: monitor news closely '
# #                 'and be ready to exit.  \n'
# #                 '- **Volatility Risk**: ATR indicates possible price swings; mitigation: consider staggered entry to '
# #                 'average price.\n'
# #                 '\n'
# #                 '7) QUICK ACTIONS  \n'
# #                 '- Place stop at $205.30.  \n'
# #                 '- Monitor news related to the DOJ case for potential impacts.  \n'
# #                 '- Reassess position size if market volatility increases.\n'
# #                 '\n'
# #                 'RECOMMENDED NEXT STEP: Implement the trade with a stop at $205.30 and monitor regulatory developments '
# #                 'closely.'],
# #   'report': 'Risk Manager Risk Analysis - Apple Inc. (AAPL)\n'
# #             'Generated: Monday, November 03, 2025 at 07:43 PM UTC\n'
# #             '\n'
# #             '1) EXECUTIVE SUMMARY  \n'
# #             'Signal: BUY (from Risk Manager) for AAPL. The immediate risk posture is moderate, with potential '
# #             'volatility stemming from regulatory concerns and market sentiment.\n'
# #             '\n'
# #             '2) SIGNAL BREAKDOWN & IMPLICATIONS  \n'
# #             'The declared signal to buy indicates a belief that AAPL will appreciate in value. With a quantity of 100 '
# #             'shares at a current price of $210.3 and a portfolio value of $150,000, this represents approximately '
# #             '1.33% of the portfolio, which is reasonable given the risk per trade of 2%.\n'
# #             '\n'
# #             '3) PROFIT TARGET & STOP LOSS REVIEW  \n'
# #             'The profit target of $235.0 and stop loss of $195.0 imply a risk-reward (RR) ratio of approximately '
# #             '1.6:1, which is favorable. The calculated stop should follow the ATR-based rule: stop = entry - 1.5 * ATR '
# #             '= 210.3 - 1.5 * 2.5 = 205.3. Thus, a recommended stop loss is $205.30.\n'
# #             '\n'
# #             '4) INVALIDATION CONDITIONS  \n'
# #             '- Close position if the price falls below $205.30.  \n'
# #             '- Monitor regulatory developments regarding the DOJ case.  \n'
# #             '- Exit if market sentiment shifts significantly bearish.\n'
# #             '\n'
# #             '5) LEVERAGE, CONFIDENCE & RISK_USD  \n'
# #             'The chosen leverage of 1 is appropriate given the risk profile and stop distance. Calculating risk: '
# #             'risk_usd = quantity * abs(entry - stop) = 100 * (210.3 - 205.3) = $500. Given the stated risk_usd of '
# #             '$4000, this indicates a need to reassess position size or stop placement. Suggested confidence score is '
# #             '0.75, reflecting moderate optimism amid cautious market signals.\n'
# #             '\n'
# #             '6) TOP RISKS & MITIGATIONS  \n'
# #             '- **Market Risk**: Potential for sudden downturns; mitigation: set tighter stops.  \n'
# #             '- **Regulatory Risk**: Ongoing DOJ case could impact share price; mitigation: monitor news closely and be '
# #             'ready to exit.  \n'
# #             '- **Volatility Risk**: ATR indicates possible price swings; mitigation: consider staggered entry to '
# #             'average price.\n'
# #             '\n'
# #             '7) QUICK ACTIONS  \n'
# #             '- Place stop at $205.30.  \n'
# #             '- Monitor news related to the DOJ case for potential impacts.  \n'
# #             '- Reassess position size if market volatility increases.\n'
# #             '\n'
# #             'RECOMMENDED NEXT STEP: Implement the trade with a stop at $205.30 and monitor regulatory developments '
# #             'closely.',
# #   'risk_debate_state': { 'count': 0,
# #                          'current_neutral_response': '',
# #                          'current_risky_response': '',
# #                          'current_safe_response': '',
# #                          'history': 'Bull and bear analysts debated risk last week.',
# #                          'judge_decision': '1) EXECUTIVE SUMMARY  \n'
# #                                            'Signal: BUY (from Risk Manager) for AAPL. The immediate risk posture is '
# #                                            'moderate, with potential volatility stemming from regulatory concerns and '
# #                                            'market sentiment.\n'
# #                                            '\n'
# #                                            '2) SIGNAL BREAKDOWN & IMPLICATIONS  \n'
# #                                            'The declared signal to buy indicates a belief that AAPL will appreciate in '
# #                                            'value. With a quantity of 100 shares at a current price of $210.3 and a '
# #                                            'portfolio value of $150,000, this represents approximately 1.33% of the '
# #                                            'portfolio, which is reasonable given the risk per trade of 2%.\n'
# #                                            '\n'
# #                                            '3) PROFIT TARGET & STOP LOSS REVIEW  \n'
# #                                            'The profit target of $235.0 and stop loss of $195.0 imply a risk-reward '
# #                                            '(RR) ratio of approximately 1.6:1, which is favorable. The calculated stop '
# #                                            'should follow the ATR-based rule: stop = entry - 1.5 * ATR = 210.3 - 1.5 * '
# #                                            '2.5 = 205.3. Thus, a recommended stop loss is $205.30.\n'
# #                                            '\n'
# #                                            '4) INVALIDATION CONDITIONS  \n'
# #                                            '- Close position if the price falls below $205.30.  \n'
# #                                            '- Monitor regulatory developments regarding the DOJ case.  \n'
# #                                            '- Exit if market sentiment shifts significantly bearish.\n'
# #                                            '\n'
# #                                            '5) LEVERAGE, CONFIDENCE & RISK_USD  \n'
# #                                            'The chosen leverage of 1 is appropriate given the risk profile and stop '
# #                                            'distance. Calculating risk: risk_usd = quantity * abs(entry - stop) = 100 '
# #                                            '* (210.3 - 205.3) = $500. Given the stated risk_usd of $4000, this '
# #                                            'indicates a need to reassess position size or stop placement. Suggested '
# #                                            'confidence score is 0.75, reflecting moderate optimism amid cautious '
# #                                            'market signals.\n'
# #                                            '\n'
# #                                            '6) TOP RISKS & MITIGATIONS  \n'
# #                                            '- **Market Risk**: Potential for sudden downturns; mitigation: set tighter '
# #                                            'stops.  \n'
# #                                            '- **Regulatory Risk**: Ongoing DOJ case could impact share price; '
# #                                            'mitigation: monitor news closely and be ready to exit.  \n'
# #                                            '- **Volatility Risk**: ATR indicates possible price swings; mitigation: '
# #                                            'consider staggered entry to average price.\n'
# #                                            '\n'
# #                                            '7) QUICK ACTIONS  \n'
# #                                            '- Place stop at $205.30.  \n'
# #                                            '- Monitor news related to the DOJ case for potential impacts.  \n'
# #                                            '- Reassess position size if market volatility increases.\n'
# #                                            '\n'
# #                                            'RECOMMENDED NEXT STEP: Implement the trade with a stop at $205.30 and '
# #                                            'monitor regulatory developments closely.',
# #                          'latest_speaker': 'Judge',
# #                          'neutral_history': '',
# #                          'risky_history': '',
# #                          'safe_history': ''},
# #   'sender': 'RiskManager'}
