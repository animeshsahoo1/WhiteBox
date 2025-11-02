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

def create_bull_researcher(llm):
    def bull_node(state, name):
        # Extract investment debate state
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")
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
        
        # System prompt defining the Bull Analyst's role and objectives
        BULL_SYSTEM_PROMPT = f"""You are a Bull Analyst advocating for investing in {company_name}. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position. You must also address reflections and learn from lessons and mistakes you made in the past."""

        # Construct the prompt with system instructions and current debate context
        bull_prompt = [
            {"role": "system", "content": BULL_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Market Research and Current Situation:
{curr_situation}

Full Conversation History:
{history}

Your Previous Arguments (Bull History):
{bull_history}

Latest Bear Analyst Response:
{current_response}

Round {count + 1}:
Your turn to argue as the Bull Analyst. Address the bear's latest points and present your bullish case."""}
        ]
        
        # Create a Pathway table from the prompt for processing
        bull_table = pw.debug.table_from_pandas(
            pd.DataFrame({"messages": [bull_prompt]})
        )

        # Pass through the model — this is the key Pathway call
        bull_response = bull_table.select(reply=llm(pw.this.messages))

        # Convert back to pandas so you can print / inspect
        bull_result = pw.debug.table_to_pandas(bull_response)
        bull_reply = bull_result["reply"].iloc[0] if not bull_result.empty else ""

        # === Write results out ===
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Bull Analyst Response - Round {count + 1}
Generated: {timestamp}

{bull_reply}"""
        
        # Return structured output for orchestration layer
        return {
            "report": full_report,
            "sender": name,
            "current_response": bull_reply
        }
    
    return functools.partial(bull_node, name="Bull Analyst")


# Example usage with sample state (commented out - uncomment to test standalone)
# if __name__ == "__main__":
#     # Initial state dictionary for testing the bull analyst
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
#         1. Strong services revenue growth reported.
#         2. New product launches expected.""",
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
#             "current_response": "Apple faces significant regulatory headwinds and slowing growth.",
#             "count": 0,
#             "judge_decision": ""
#         }
#     }
#     
#     # Create and run the bull analyst
#     bull_agent = create_bull_researcher(chat_model)
#     bull_output = bull_agent(test_state)
#     
#     print(bull_output['report'])
