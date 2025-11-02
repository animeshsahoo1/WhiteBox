import functools
import pathway as pw
import pandas as pd
from datetime import datetime, timezone

from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os

load_dotenv()

chat_model = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
)

def create_bear_researcher(llm):
    def bear_node(state, name):
        # Extract investment debate state
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")
        current_response = investment_debate_state.get("current_response", "")
        count = investment_debate_state.get("count", 0)
        
        # Extract research reports
        market_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        
        # Get company name
        company_name = state.get("company_of_interest", "the stock")
        
        # UDF to combine all research reports into a single formatted string
        @pw.udf
        def combine_reports(market, sentiment, news, fundamentals):
            return f"{market}\n\n{sentiment}\n\n{news}\n\n{fundamentals}"

        # Combine all research data into current situation
        curr_situation = combine_reports(market_report, sentiment_report, news_report, fundamentals_report)
        
        # System prompt defining the Bear Analyst's role and objectives
        BEAR_SYSTEM_PROMPT = f"""You are a Bear Analyst making the case against investing in {company_name}. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the stock. You must also address reflections and learn from lessons and mistakes you made in the past."""

        # Construct the prompt with system instructions and current debate context
        bear_prompt = [
            {"role": "system", "content": BEAR_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Market Research and Current Situation:
{curr_situation}

Full Conversation History:
{history}

Your Previous Arguments (Bear History):
{bear_history}

Latest Bull Analyst Response:
{current_response}

Round {count + 1}:
Your turn to argue as the Bear Analyst. Address the bull's latest points and present your bearish case."""}
        ]
        
        # Create a Pathway table from the prompt for processing
        bear_table = pw.debug.table_from_pandas(
            pd.DataFrame({"messages": [bear_prompt]})
        )

        # Pass through the model — this is the key Pathway call
        bear_response = bear_table.select(reply=llm(pw.this.messages))

        # Convert back to pandas so you can print / inspect
        bear_result = pw.debug.table_to_pandas(bear_response)
        bear_reply = bear_result["reply"].iloc[0] if not bear_result.empty else ""

        # === Write results out ===
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Bear Analyst Response - Round {count + 1}
Generated: {timestamp}

{bear_reply}"""
        
        # Return structured output for orchestration layer
        return {
            "report": full_report,
            "sender": name,
            "current_response": bear_reply
        }
    
    return functools.partial(bear_node, name="Bear Analyst")


# Example usage with sample state (commented out - uncomment to test standalone)
# if __name__ == "__main__":
#     # Initial state dictionary for testing the bear analyst
#     test_state = {
#         "company_of_interest": "Apple Inc. (AAPL)",
#         
#         "market_report": """**Macroeconomic & Market Overview**
#         The current market environment is characterized by persistent uncertainty. The Federal Reserve has signaled a "higher for longer" stance on interest rates to combat sticky inflation.""",
#         
#         "sentiment_report": """**Market Sentiment Analysis for AAPL**
#         - **Social Media:** Overall sentiment is cautiously optimistic.
#         - **News Sentiment:** Mixed with regulatory concerns.""",
#         
#         "news_report": """**Key News Items**
#         1. EU regulators opened investigation into App Store practices.
#         2. Slowing sales in China market reported.""",
#         
#         "fundamentals_report": """**AAPL Key Financial Metrics**
#         - **P/E Ratio:** 31.2x
#         - **Revenue Growth:** +1.8%
#         - **Net Profit Margin:** 26.3%""",
#         
#         "investment_debate_state": {
#             "history": "",
#             "bear_history": "",
#             "bull_history": "",
#             "current_response": "Apple's ecosystem and services revenue provide strong long-term value.",
#             "count": 0,
#             "judge_decision": ""
#         }
#     }
#     
#     # Create and run the bear analyst
#     bear_agent = create_bear_researcher(chat_model)
#     bear_output = bear_agent(test_state)
#     
#     print(bear_output['report'])
