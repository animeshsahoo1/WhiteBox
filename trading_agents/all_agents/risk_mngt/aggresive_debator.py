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
        # ---------------------------------------------------------
        # Extract the debate and context data from the state object
        # ---------------------------------------------------------
        risk_debate_state = state.get("risk_debate_state", {}) or {}
        history = (risk_debate_state.get("history", "") or "")
        risky_history = risk_debate_state.get("risky_history", "") or ""
        current_safe_response = risk_debate_state.get("current_safe_response", "") or ""
        current_neutral_response = risk_debate_state.get("current_neutral_response", "") or ""

        # Get supporting reports and trader decision (ensure strings)
        market_research_report = str(state.get("market_report", ""))
        sentiment_report = str(state.get("sentiment_report", ""))
        news_report = str(state.get("news_report", ""))
        fundamentals_report = str(state.get("fundamentals_report", ""))
        trader_decision = str(state.get("trader_investment_plan", ""))

        # ---------------------------------------------------------
        # Defensive: limit history size to avoid token limits
        # ---------------------------------------------------------
        MAX_HISTORY_CHARS = 4000
        if len(history) > MAX_HISTORY_CHARS:
            history = history[-MAX_HISTORY_CHARS:]

        # ---------------------------------------------------------
        # Build the complete prompt and wrap it in chat-style messages
        # ---------------------------------------------------------
        prompt = prompt = f"""As the Risky Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views. Specifically, respond directly to each point made by the conservative and neutral analysts, countering with data-driven rebuttals and persuasive reasoning. Highlight where their caution might miss critical opportunities or where their assumptions may be overly conservative.

Here is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward. Incorporate insights from the following sources into your arguments:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}

Here is the current conversation history: {history}
Here are the last arguments from the conservative analyst: {current_safe_response}
Here are the last arguments from the neutral analyst: {current_neutral_response}

If there are no responses from the other viewpoints, do not hallucinate and just present your point.

Engage actively by addressing any specific concerns raised, refuting the weaknesses in their logic, and asserting the benefits of risk-taking to outpace market norms. Maintain a focus on debating and persuading, not just presenting data.

At the end of your response, on two separate lines, clearly state:

Risk Percentage: [numeric value between 0 and 100]
Confidence Level: [numeric value between 0 and 100]

Output conversationally and naturally, but ensure these two metrics appear exactly at the end."""

        # Wrap as chat messages (system + user)
        system_msg = {
            "role": "system",
            "content": "You are the Risky Risk Analyst. Advocate high-reward, high-risk opportunities and rebut conservative/neutral arguments using provided data."
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

        # ---------------------------------------------------------
        # Step 4: Prepare the updated state of the debate
        # ---------------------------------------------------------
        argument = f"Risky Analyst: {risky_reply}"
        old_count = int(risk_debate_state.get("count", 0) or 0)

        new_risk_debate_state = {
            "history": (history + "\n" + argument).strip(),
            "risky_history": (risky_history + "\n" + argument).strip(),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Risky",
            "current_risky_response": argument,
            "current_safe_response": current_safe_response,
            "current_neutral_response": current_neutral_response,
            "count": old_count + 1,
        }

        # ---------------------------------------------------------
        # Step 5: Add a timestamped report for logging or debugging
        # ---------------------------------------------------------
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Risky agent Analysis
Generated: {timestamp}

{argument}"""

        # ---------------------------------------------------------
        # Step 6: Return the updated state and report
        # ---------------------------------------------------------
        return {
            "risk_debate_state": new_risk_debate_state,
            "report": full_report,
            "sender": name,
        }

    # Return a partial node with a fixed name
    return functools.partial(risky_node, name="Risky")

# ---------------------------------------------------------
# Example initial state with pre-existing history
# ---------------------------------------------------------
initial_state = {
    "market_report": "Tech stocks are rebounding as investors rotate back into growth sectors.",
    "sentiment_report": "Social media sentiment is bullish on innovation-driven companies.",
    "news_report": "A major hedge fund increased exposure to emerging AI companies.",
    "fundamentals_report": "Company shows improving profit margins and aggressive R&D expansion.",
    "trader_investment_plan": "Trader plans to allocate 15% more capital into high-growth AI startups.",
    "risk_debate_state": {
        "history": (
            "Safe Analyst: The trader’s decision seems too risky given market volatility.\n"
            "Neutral Analyst: A phased approach would reduce downside exposure.\n"
            "Risky Analyst: Previous opportunities like this have yielded outsized gains when timed correctly."
        ),
        "risky_history": (
            "Risky Analyst: Investing in innovation often requires bold conviction, "
            "and waiting too long could forfeit first-mover advantage."
        ),
        "safe_history": (
            "Safe Analyst: I recommend a smaller allocation to mitigate potential drawdowns."
        ),
        "neutral_history": (
            "Neutral Analyst: It may be prudent to monitor macroeconomic conditions before scaling up exposure."
        ),
        "current_safe_response": "Conservative view: The plan is too aggressive given volatility.",
        "current_neutral_response": "Neutral view: Consider staged investment over time.",
        "count": 3,
    },
}

# ---------------------------------------------------------
# Run the node once and print outputs
# ---------------------------------------------------------
risky_agent = create_risky_debator(chat_model)
output = risky_agent(initial_state)

print("\n=== Risky Agent Report ===")
print(output["report"])
print("\n=== Updated Debate State ===")
print(output["risk_debate_state"])
