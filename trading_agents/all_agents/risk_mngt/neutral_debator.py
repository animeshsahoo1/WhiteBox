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

def create_neutral_debator(llm):
    def neutral_node(state, name):
        risk_debate_state = state.get("risk_debate_state", {})

        market_research_report = str(state.get("market_report", ""))
        sentiment_report = str(state.get("sentiment_report", ""))
        news_report = str(state.get("news_report", ""))
        fundamentals_report = str(state.get("fundamentals_report", ""))
        trader_decision = str(state.get("trader_investment_plan", ""))

        # ---------------------------------------------------------
        # Defensive: limit history size to avoid token limits
        # ---------------------------------------------------------
        # MAX_HISTORY_CHARS = 4000
        # if len(history) > MAX_HISTORY_CHARS:
        #     history = history[-MAX_HISTORY_CHARS:]

        # ---------------------------------------------------------
        # Build the complete Neutral Analyst prompt
        # ---------------------------------------------------------
        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.
        
Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Risky and Safe Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}

If there are no responses from the other viewpoints, do not hallucinate and just present your point.

Engage actively by analyzing both sides critically, addressing weaknesses in the risky and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes. Output conversationally as if you are speaking without any special formatting.

At the end of your response, on two separate lines, clearly state:

Risk Percentage: [numeric value between 0 and 100]
Confidence Level: [numeric value between 0 and 100]

Output conversationally and naturally, but ensure these two metrics appear exactly at the end."""

        # ---------------------------------------------------------
        # Wrap as chat messages (system + user)
        # ---------------------------------------------------------
        system_msg = {
            "role": "system",
            "content": "You are the Neutral Risk Analyst. Provide a balanced, data-driven perspective that reconciles both the risky and safe viewpoints to guide a moderate investment strategy."
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
        # Step 4: Prepare the updated debate state
        # ---------------------------------------------------------
        argument = f"Neutral Analyst: {neutral_reply}"


        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Neutral agent Analysis
Generated: {timestamp}

{argument}"""

        return {
            "risk_debate_state": {
                **state["risk_debate_state"],
                "neutral_response": full_report,
            },
            "sender": name,
        }

    # Return a partial node with a fixed name
    return functools.partial(neutral_node, name="Neutral")


# ---------------------------------------------------------
# Example initial state with pre-existing history
# ---------------------------------------------------------
# initial_state_neutral = {
#     "market_report": "Technology and energy sectors show mixed performance as investor sentiment shifts toward stability.",
#     "sentiment_report": "Online sentiment is moderately positive, with discussions highlighting potential in renewable energy stocks but concerns about overvaluation.",
#     "news_report": "Global supply chain stabilization and steady interest rates are creating balanced market conditions.",
#     "fundamentals_report": "The company maintains consistent cash flow with moderate leverage and steady dividend payouts.",
#     "trader_investment_plan": "Trader plans to reallocate 10% of portfolio from bonds to mid-cap technology equities.",
#     "risk_debate_state": {
#         "history": (
#             "Risky Analyst: This is the perfect time to enter tech — strong momentum, and we’ll miss the upside if we wait.\n"
#             "Safe Analyst: Tech valuations are high, and reallocation from bonds could increase portfolio volatility.\n"
#             "Neutral Analyst: We should weigh near-term volatility against long-term growth potential."
#         ),
#         "risky_history": (
#             "Risky Analyst: Investors who took similar risks last cycle saw 2x returns. The fundamentals are lining up again."
#         ),
#         "safe_history": (
#             "Safe Analyst: Market cycles are unpredictable, and defensive positioning may safeguard returns."
#         ),
#         "neutral_history": (
#             "Neutral Analyst: Diversification across sectors ensures stability while capturing growth trends."
#         ),
#         "current_risky_response": "Risky view: Full exposure to mid-cap tech will maximize alpha opportunities.",
#         "current_safe_response": "Safe view: Limit exposure to 5% to minimize downside risks in volatile sectors.",
#         "count": 5,
#     },
# }

# # ---------------------------------------------------------
# # Run the Neutral node once and print outputs
# # ---------------------------------------------------------
# neutral_agent = create_neutral_debator(chat_model)
# output_neutral = neutral_agent(initial_state_neutral)

# print("\n=== Neutral Agent Report ===")
# print(output_neutral.get("report", ""))

# print("\n=== Updated Debate State ===")
# print(output_neutral.get("risk_debate_state", {}))

