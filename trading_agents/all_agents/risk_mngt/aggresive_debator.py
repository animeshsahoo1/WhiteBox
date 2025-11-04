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
chat_model = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
)

def create_risky_debator(llm):
    def risky_node(state, name):

        # Get supporting reports and trader decision (ensure strings)
        market_research_report = str(state.get("market_report", ""))
        sentiment_report = str(state.get("sentiment_report", ""))
        news_report = str(state.get("news_report", ""))
        fundamentals_report = str(state.get("fundamentals_report", ""))
        trader_decision = str(state.get("trader_investment_plan", ""))

        prompt = f"""As the Risky Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and provide a compelling case for aggressive investment strategies.

Here is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by analyzing the opportunities and potential rewards. Incorporate insights from the following sources into your arguments:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}

Provide an independent analysis that emphasizes growth opportunities, first-mover advantages, and the benefits of bold action in capturing market opportunities. Focus on why taking calculated risks can lead to outsized returns and competitive positioning.

At the end of your response, on two separate lines, clearly state:

Risk Percentage: [numeric value between 0 and 100]
Confidence Level: [numeric value between 0 and 100]

Output conversationally and naturally, but ensure these two metrics appear exactly at the end."""

        # Wrap as chat messages (system + user)
        system_msg = {
            "role": "system",
            "content": "You are the Risky Risk Analyst. Advocate for high-reward, high-risk opportunities and emphasize growth potential using provided data."
        }
        user_msg = {"role": "user", "content": prompt}
        chat_messages = [system_msg, user_msg]

        # ---------------------------------------------------------
        # Step 1: Wrap the chat messages into a Pathway table
        # ---------------------------------------------------------
        prompt_table = pw.debug.table_from_pandas(pd.DataFrame({"messages": [chat_messages]}))

        # ---------------------------------------------------------
        # Step 2: Pass through the LLM (with defensive handling)
        # ---------------------------------------------------------
        try:
            response_table = prompt_table.select(reply=llm(pw.this.messages))
            response_df = pw.debug.table_to_pandas(response_table)
        except Exception as e:
            # Capture LLM/Pathway failure without raising
            response_df = pd.DataFrame({"reply": [f"[LLM error: {e}]"]})

        # ---------------------------------------------------------
        # Step 3: Extract reply defensively
        # ---------------------------------------------------------
        risky_reply = ""
        if not response_df.empty and "reply" in response_df.columns:
            risky_reply = str(response_df["reply"].iloc[0])

        argument = f"Risky Analyst: {risky_reply}"

 
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Risky agent Analysis
Generated: {timestamp}

{argument}"""

        # ---------------------------------------------------------
        # Step 6: Return the updated state and report
        # ---------------------------------------------------------
        return {
            "risky_analysis": full_report,
            "sender": name,
        }


    # Return a partial node with a fixed name
    return functools.partial(risky_node, name="Risky")