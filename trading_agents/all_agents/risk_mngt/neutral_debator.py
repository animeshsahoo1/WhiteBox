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

def create_neutral_debator(llm):
    def neutral_node(state, name):

        market_research_report = str(state.get("market_report", ""))
        sentiment_report = str(state.get("sentiment_report", ""))
        news_report = str(state.get("news_report", ""))
        fundamentals_report = str(state.get("fundamentals_report", ""))
        trader_decision = str(state.get("trader_investment_plan", ""))

        # ---------------------------------------------------------
        # Build the complete Neutral Analyst prompt
        # ---------------------------------------------------------
        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.
        
Here is the trader's decision:

{trader_decision}

Your task is to provide an independent analysis that considers both optimistic and cautious viewpoints. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}

Provide a comprehensive analysis that examines both the growth potential and the risks involved. Focus on illustrating why a moderate risk strategy might offer the best balance, providing growth potential while safeguarding against extreme volatility. Output conversationally as if you are speaking without any special formatting.

At the end of your response, on two separate lines, clearly state:

Risk Percentage: [numeric value between 0 and 100]
Confidence Level: [numeric value between 0 and 100]

Output conversationally and naturally, but ensure these two metrics appear exactly at the end."""

        # ---------------------------------------------------------
        # Wrap as chat messages (system + user)
        # ---------------------------------------------------------
        system_msg = {
            "role": "system",
            "content": "You are the Neutral Risk Analyst. Provide a balanced, data-driven perspective that considers both growth opportunities and risk management to guide a moderate investment strategy."
        }
        user_msg = {"role": "user", "content": prompt}
        chat_messages = [system_msg, user_msg]

        # ---------------------------------------------------------
        # Step 1: Wrap chat messages into a Pathway table
        # ---------------------------------------------------------
        prompt_table = pw.debug.table_from_pandas(pd.DataFrame({"messages": [chat_messages]}))

        # ---------------------------------------------------------
        # Step 2: Pass through the LLM (with defensive handling)
        # ---------------------------------------------------------
        try:
            response_table = prompt_table.select(reply=llm(pw.this.messages))
            response_df = pw.debug.table_to_pandas(response_table)
        except Exception as e:
            response_df = pd.DataFrame({"reply": [f"[LLM error: {e}]"]})

        # ---------------------------------------------------------
        # Step 3: Extract reply defensively
        # ---------------------------------------------------------
        neutral_reply = ""
        if not response_df.empty and "reply" in response_df.columns:
            neutral_reply = str(response_df["reply"].iloc[0])

        # ---------------------------------------------------------
        # Step 4: Prepare the report
        # ---------------------------------------------------------
        argument = f"Neutral Analyst: {neutral_reply}"

        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Neutral agent Analysis
Generated: {timestamp}

{argument}"""

        return {
            "neutral_analysis": full_report,
            "sender": name,
        }

    # Return a partial node with a fixed name
    return functools.partial(neutral_node, name="Neutral")