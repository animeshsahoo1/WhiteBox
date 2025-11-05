import functools
import pathway as pw
import pandas as pd
from datetime import datetime, timezone
from all_agents.utils.llm import chat_model

def create_trader(llm):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        debate_history = state["investment_debate_state"]["history"]

        market_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        
        @pw.udf
        def combine_reports(market, sentiment, news, fundamentals):
            return f"{market}\n\n{sentiment}\n\n{news}\n\n{fundamentals}"

        curr_situation = combine_reports(market_report, sentiment_report, news_report, fundamentals_report)

        TRADER_SYSTEM_PROMPT = f"""You are a Trader Agent responsible for making the final investment plan for {company_name} after reviewing
detailed analyses from both the Bull and Bear Analysts, as well as market situation. Your role is to synthesize their arguments,
weigh the supporting evidence, and arrive at a balanced, data-driven trading decision.
if no information about the current holdings of the user in this stock is there then you can assume the user has some current holdings and give 
suggestions accordingly with percentages of allocation rather than absolute amounts.
apart from saying allocation percentages of funds to invest with the assumption that the user has some current holdings in this stock you should also provide a clear exit strategy for the investment.
in the exit strategy consider both profit-taking and loss-cutting mechanisms based on market conditions and stock performance. also try to give a time horizon for the exit strategy.

Your decision-making process should:
- Objectively evaluate both perspectives without bias.
- Consider macroeconomic indicators, sentiment data, and market research provided.
- Identify the strongest points from each analyst and determine which carries more weight.
- Address conflicting reasoning logically and justify your final stance with clear rationale.
- Prioritize capital preservation, risk-adjusted returns, and long-term sustainability.

Structure your analysis as follows:
1. **Summary of Bull Position:** Briefly restate key bullish arguments.
2. **Summary of Bear Position:** Briefly restate key bearish arguments.
3. **Comparative Evaluation:** Analyze where the two positions diverge and which is better supported by data.
4. **Final Reasoning:** Provide a concise explanation of your final view.
5. **Decision:** Conclude with a clear recommendation.
6. **Investment Plan:** describe the clear investment plan for funds allocation
7. **exit strategy:** describe the clear exit strategy for the investment

"""


        trader_prompt = [
            {"role": "system", "content": TRADER_SYSTEM_PROMPT},
            {"role": "system", "content": f"""debate history:
{debate_history}

Market Situation:
{curr_situation}"""}
        ]
        
        trader_table = pw.debug.table_from_pandas(
            pd.DataFrame({"messages": [trader_prompt]})
        )

        # Pass through the model — this is the key Pathway call
        trader_response = trader_table.select(reply=llm(pw.this.messages))

        # Convert back to pandas so you can print / inspect
        trader_result = pw.debug.table_to_pandas(trader_response)
        trader_reply = trader_result["reply"].iloc[0] if not trader_result.empty else ""

        # === Write results out ===
        timestamp = datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")
        full_report = f"""Trader agent Analysis 
Generated: {timestamp}

{trader_reply}"""
        
        return {
            #TODO: later remove this messages key and get it sent by the final manager not here
            "messages": [trader_reply],
            "trader_investment_plan": full_report,
            "sender": name,
        }
    
    return functools.partial(trader_node, name="Trader")    


# Initial state dictionary for the trading agent graph
# initial_state = {
#     "company_of_interest": "Apple Inc. (AAPL)",
    
#     "bull_report": """
#     **Bull Analyst Report: Apple Inc. (AAPL)**
    
#     **Thesis:** HOLD/BUY - Apple's long-term value proposition remains unmatched, driven by its impenetrable ecosystem, accelerating services revenue, and relentless innovation.
    
#     **Key Drivers:**
#     1.  **Ecosystem Lock-In:** The integration of hardware (iPhone, Mac, Watch, AirPods) and software (iOS, macOS) creates a sticky user base with high switching costs. This ecosystem is a fortress that competitors cannot breach.
#     2.  **Services Revenue Growth:** The Services division (App Store, iCloud, Apple Music, Apple Pay) is a high-margin juggernaut. It consistently posts double-digit growth and now has over 1 billion paid subscriptions. This segment provides a stable, recurring revenue stream that smooths hardware cyclicality.
#     3.  **Financial Fortress:** Apple's balance sheet is pristine, with over $160 billion in cash and marketable securities. This allows for massive R&D spending, strategic acquisitions, and aggressive capital return programs (buybacks and dividends) that consistently reward shareholders.
#     4.  **Innovation Pipeline:** While the market fixates on quarterly iPhone numbers, Apple is planting seeds for its next decade of growth. The Apple Vision Pro, while nascent, signals a paradigm shift in spatial computing. Furthermore, Apple's on-device AI integration (Apple Intelligence) is poised to create a truly personalized and private user experience that competitors, reliant on cloud-based AI, cannot easily replicate.
    
#     **Valuation:** While the P/E multiple is elevated, it is justified by Apple's quality, profitability (net margin > 25%), and dominant market position. It should be valued as a high-end consumer luxury brand with a software-as-a-service component, not as a simple hardware manufacturer.
#     """,
    
#     "bear_report": """
#     **Bear Analyst Report: Apple Inc. (AAPL)**
    
#     **Thesis:** SELL/HOLD - Apple faces significant headwinds, including regulatory scrutiny, slowing hardware innovation, and an over-reliance on the iPhone, all at a historically high valuation.
    
#     **Key Risks:**
#     1.  **Regulatory Assault:** Apple is in the crosshairs of regulators globally (US DOJ, EU DMA). Lawsuits targeting the App Store's 30% commission and anti-steering policies threaten to dismantle its high-margin services "walled garden." A negative outcome could materially impact profitability.
#     2.  **iPhone Dependency:** The iPhone still accounts for nearly 50% of total revenue. The smartphone market is mature and saturated. In key growth markets like China, Apple is facing intense, state-backed competition from rivals like Huawei, leading to market share erosion and pricing pressure.
#     3.  **Slowing Growth & High Valuation:** Revenue growth has decelerated to the low single digits. At a forward P/E of ~30x, Apple is priced for perfection. Any miss on earnings or guidance could trigger a significant price correction. The stock is "priced in" and offers limited upside.
#     4.  **"What's Next?" Problem:** The Apple Vision Pro is a niche, ultra-expensive product with a limited market. It is not the "next iPhone." Apple's AI features are perceived as catching up rather than leading. Without a clear new mass-market category, growth will stagnate.
#     """,
    
#     "market_report": """
#     **Macroeconomic & Market Overview**
    
#     The current market environment is characterized by persistent uncertainty. The Federal Reserve has signaled a "higher for longer" stance on interest rates to combat sticky inflation, which remains above the 2% target. This puts pressure on growth stock valuations, particularly in the tech sector. 
    
#     While corporate earnings have been resilient, consumer discretionary spending is showing signs of weakness as savings rates decline and credit card debt rises. A 'soft landing' is the base case, but the risk of a mild recession in the next 6-8 months cannot be discounted.
#     """,
    
#     "sentiment_report": """
#     **Market Sentiment Analysis for AAPL**
    
#     -   **Social Media:** Overall sentiment on platforms like X (Twitter) and Reddit is cautiously optimistic. Retail investors remain bullish on the brand, but "value" investors are increasingly vocal, calling the stock "overpriced."
#     -   **News Sentiment:** Financial news headlines are mixed. Positive stories focus on the upcoming M4-powered MacBooks, while negative coverage is dominated by the ongoing DOJ antitrust lawsuit and slowing sales in China.
#     -   **Analyst Ratings:** Consensus remains a 'Buy', but the number of 'Hold' ratings has increased in the last quarter.
#     """,
    
#     "news_report": """
#     **Key News Items (Last 72 Hours)**
    
#     1.  **"AppleInsider" reports rumors of a new, lower-cost "iPhone SE 4" with an updated design and 5G, potentially launching next spring to target emerging markets.**
#     2.  **EU regulators have officially opened a second investigation into Apple's App Store, focusing on its new fee structure for "sideloaded" apps, claiming it violates the Digital Markets Act (DMA).**
#     3.  **A major hedge fund manager stated in an interview that they have "trimmed" their position in Apple, citing "valuation concerns and geopolitical risk in its supply chain."**
#     """,
    
#     "fundamentals_report": """
#     **AAPL Key Financial Metrics (TTM)**
    
#     -   **P/E Ratio:** 31.2x (vs. S&P 500 avg. of ~21x)
#     -   **Revenue Growth (YoY):** +1.8%
#     -   **Net Profit Margin:** 26.3%
#     -   **Services Revenue Growth (YoY):** +12.5%
#     -   **Hardware Revenue Growth (YoY):** -1.5%
#     -   **Cash & Marketable Securities:** $162 Billion
#     -   **Debt:** $108 Billion
#     """,
    
#     "investment_plan": """
#     **Initial Investment Plan Draft:**
    
#     -   **Goal:** Long-term capital appreciation with moderate risk.
#     -   **Current Holding:** Hold 500 shares of AAPL.
#     -   **Proposed Action:** Looking to deploy new capital. 
#     -   **Strategy:** Consider a "buy the dip" strategy. If the stock drops 5-10% due to macro fears or regulatory news (but not fundamental weakness), add 100 shares. 
#     -   **Risk Management:** Implement a stop-loss on new shares if the price falls 15% below the purchase price.
#     """
# }

# trader_agent = create_trader(chat_model)

# # Run the trader node with the initial state
# trader_output = trader_agent(initial_state)

# print(trader_output['report'])