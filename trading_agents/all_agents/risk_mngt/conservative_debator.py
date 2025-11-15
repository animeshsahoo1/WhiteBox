import os
import functools
import pandas as pd
from datetime import datetime, timezone
import pathway as pw
from dotenv import load_dotenv
from pathway.xpacks.llm import llms

# Load environment variables (ensure OPENAI_API_KEY is set)
load_dotenv()

# Create the chat model
chat_model = llms.LiteLLMChat(
    model="openrouter/openai/gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

def create_safe_debator(llm):
    def safe_node(state, name):
        
        market_research_report = str(state.get("market_report", ""))
        sentiment_report = str(state.get("sentiment_report", ""))
        news_report = str(state.get("news_report", ""))
        fundamentals_report = str(state.get("fundamentals_report", ""))
        trader_decision = str(state.get("trader_investment_plan", ""))

        # ---------------------------------------------------------
        # Construct the Safe/Conservative Analyst prompt
        # ---------------------------------------------------------
        prompt = f"""As the Safe or Conservative Risk Analyst, your primary responsibility is to safeguard assets, minimize volatility, and ensure consistent, reliable portfolio growth. You focus on capital preservation, stability, and long-term sustainability over short-term high returns. Your analysis should critically evaluate the trader's plan and the arguments presented by other analysts—especially identifying where risk-taking might lead to financial exposure, operational inefficiency, or vulnerability to macroeconomic shocks.

Here is the trader's decision:

{trader_decision}

Your objective is to construct a logical, risk-averse counter-argument to the perspectives of the Risky and Neutral Analysts. Draw on quantitative reasoning and financial prudence, and emphasize areas where restraint and patience yield better outcomes than aggressive pursuit of uncertain gains.

To support your reasoning, refer to the following reports and datasets:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}

If there are no prior responses from other participants, avoid speculation and focus on presenting your independent viewpoint. Provide concise yet persuasive arguments that appeal to rational judgment and disciplined strategy.

Specifically:
- Identify any overextensions, speculative assumptions, or weak justifications in the Risky and Neutral perspectives.
- Highlight potential external threats such as interest rate fluctuations, liquidity risks, market overvaluation, or geopolitical instability.
- Recommend defensive adjustments, hedging opportunities, and capital protection measures that can still align with the trader's objectives.

Your communication style should be confident, analytical, and grounded in financial logic—avoiding hype or fear-mongering. The goal is to demonstrate that a cautious, well-managed approach can yield more consistent results in volatile markets.

At the end of your response, include two quantitative metrics for clarity:
Risk Percentage: [numeric value between 0 and 100]
Confidence Level: [numeric value between 0 and 100]

Ensure these metrics appear on separate lines and at the very end of your response, after your argumentation."""

        # ---------------------------------------------------------
        # Wrap the prompt into a structured LLM chat format
        # ---------------------------------------------------------
        system_msg = {
            "role": "system",
            "content": "You are the Safe/Conservative Risk Analyst. Focus on minimizing portfolio risk and defending conservative investment strategies while analyzing and critiquing more aggressive perspectives."
        }
        user_msg = {"role": "user", "content": prompt}
        chat_messages = [system_msg, user_msg]

        # ---------------------------------------------------------
        # Step 1: Convert messages into a Pathway table for processing
        # ---------------------------------------------------------
        prompt_table = pw.debug.table_from_pandas(pd.DataFrame({"messages": [chat_messages]}))

        # ---------------------------------------------------------
        # Step 2: Call the model through Pathway
        # ---------------------------------------------------------
        try:
            response_table = prompt_table.select(reply=llm(pw.this.messages))
            response_df = pw.debug.table_to_pandas(response_table)
        except Exception as e:
            response_df = pd.DataFrame({"reply": [f"[LLM error: {e}]"]})

        # ---------------------------------------------------------
        # Step 3: Safely extract model output
        # ---------------------------------------------------------
        safe_reply = ""
        if not response_df.empty and "reply" in response_df.columns:
            safe_reply = str(response_df["reply"].iloc[0])

        # ---------------------------------------------------------
        # Step 4: Construct the next dialogue state update
        # ---------------------------------------------------------
        argument = f"Safe Analyst: {safe_reply}"

        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Safe/Conservative Analyst Report
Generated: {timestamp}

{argument}

This report represents the Safe Analyst's rebuttal emphasizing portfolio preservation, disciplined allocation, and the long-term view. It builds upon prior discussion and introduces a conservative adjustment path that integrates market intelligence, sentiment analysis, and risk control."""

        # ---------------------------------------------------------
        # Step 6: Return final state and structured output
        # ---------------------------------------------------------
        return {
            "safe_analysis": full_report,
            "sender": name,
        }

    # Return partial function with pre-defined analyst identity
    return functools.partial(safe_node, name="Safe")