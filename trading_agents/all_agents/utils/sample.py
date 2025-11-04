market_report_example = """

[ Market Analyst ]:
================================== Report ==================================
Based on the analysis of AAPL ’ s recent market data and selected technical
indicators , here is a detailed and nuanced report of the trends observed :
### Momentum Indicators
- ** RSI ( Relative Strength Index ) **: The RSI values indicate significant
fluctuations , with periods of overbought conditions , particularly on November
5 and November 7 , where RSI values reached 100 and 89.85 , respectively . This
suggests strong upward price movements , potentially leading to price
corrections . The RSI stabilizes towards the end of the period , indicating
moderate buying momentum .
### Trend Indicators
- ** ADX ( Average Directional Index ) **: Initially , the ADX values are extremely
high , indicating a strong trend , but they decline significantly , suggesting a
weakening trend strength . This pattern implies a transition from a strong
directional movement to a potential consolidation phase .
- ** Supertrend **: The supertrend indicator remains constant , suggesting a stable
market trend without significant volatility . This stability might indicate a
consolidation phase , with the potential for future breakouts .
### Volatility Indicators
- ** Bollinger Bands **: The upward trend in Bollinger Bands suggests a bullish
market phase with low volatility . The consistent rise in values indicates a
positive market bias , with prices likely to continue rising if the trend
persists .
- ** ATR ( Average True Range ) **: The ATR values show an increase in market
volatility , peaking on November 7. This suggests heightened market activity ,
with sustained volatility towards the end of the period .
### Volume Indicators
- ** VR ( Volume Variation Index ) **: The VR values highlight significant
fluctuations in trading volume , with a notable spike on November 5. This
indicates heightened market activity , possibly due to external factors
influencing trader behavior .
### Price Action and Support / Resistance
- ** CCI ( Commodity Channel Index ) **: The CCI values indicate volatility , with
several instances of overbought conditions . Peaks on November 7 , November 14 ,
and November 18 suggest strong upward price movements , which could be followed
by corrections .
### Moving Averages
- ** MACD ( Moving Average Convergence Divergence ) **: The MACD values indicate a
general upward trend , with some fluctuations and minor pullbacks . The
increasing MACD values suggest bullish market sentiment , with the short - term
moving average consistently above the long - term average .
### Summary and Insights
The analysis of AAPL ’ s recent market data reveals a period of volatility with
alternating phases of strong buying momentum and stabilization . The initial
overbought conditions and high ADX values suggest a strong trend , which
weakens over time , indicating potential consolidation . The consistent upward
trend in Bollinger Bands and MACD values points to a bullish market sentiment ,
while the fluctuations in ATR and VR values highlight ongoing market
volatility .
Traders should be cautious of potential price corrections following the overbought
conditions and consider the possibility of continued volatility . The stable
supertrend value suggests a consolidation phase , with potential for future
breakouts . Overall , traders should remain vigilant , using these insights to
adjust their strategies accordingly , while being prepared for both
opportunities and risks presented by the current market conditions .
================================ Tool Calls ================================
Tool Calls :
get_YFin_data ( call_TuDo4m3U0lkgtV61Qpq3UIiT )
Call ID : call_TuDo4m3U0lkgtV61Qpq3UIiT
Args :
symbol : AAPL
curr_date : 2024 -11 -19
Based on the recent market data for Apple ( AAPL ) from November 4 , 2024 , to
November 18 , 2024 , we can observe several key trends and patterns :
1. ** Price Movement **: AAPL has shown a general upward trend over the period , with
the stock price increasing from an opening of
$220 .75 on November 4 to a closing of $228 .02 on November 18. The stock
experienced fluctuations , with notable highs on November
7 and November 14 , reaching $227 .63 and $228 .87 , respectively .
2. ** Volume Trends **: Trading volume varied significantly , with a peak on November
6 at 54 ,561 ,100 shares . This suggests heightened trading activity , possibly
due to market events or investor sentiment changes .
3. ** Dividend Payment **: A dividend of $0 .25 per share was paid on November 8 ,
which might have influenced investor behavior , potentially contributing to the
price movements observed around this date .
4. ** Volatility **: The stock showed some volatility , with daily price ranges (
highs and lows ) indicating active trading and potential market reactions to
news or earnings reports .
To provide a comprehensive analysis , I will select a set of technical indicators
that can offer diverse insights into AAPL ’ s market behavior . These indicators
will cover momentum , trend , volatility , volume , and price action aspects :
1. ** RSI ( Relative Strength Index ) **: To assess momentum and identify overbought
or oversold conditions .
2. ** ADX ( Average Directional Index ) **: To evaluate the strength of the current
trend .
3. ** Bollinger Bands **: To analyze volatility and potential price breakouts .
4. ** MACD ( Moving Average Convergence Divergence ) **: To identify trend changes and
momentum .
5. ** VWMA ( Volume Weighted Moving Average ) **: To understand price movements in
relation to volume .
6. ** ATR ( Average True Range ) **: To measure market volatility .
7. ** Supertrend **: To identify trend direction and potential reversals .
8. ** CCI ( Commodity Channel Index ) **: To identify cyclical trends and potential
reversals .
I will now retrieve detailed reports for these indicators to provide a nuanced
analysis of AAPL ’ s market conditions .
Tool Calls :
get_stockstats_indicators_report ( call_rARQhoVdv6VyzI3a3R9hyhYh )
Call ID : call_rARQhoVdv6VyzI3a3R9hyhYh
Args :
symbol : AAPL
indicator : rsi
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_ODamPSS2si621zrEPb4mIitD )
Call ID : call_ODamPSS2si621zrEPb4mIitD
Args :
symbol : AAPL
indicator : adx
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_KWgyXj3GgdviC01u5KeFZkbQ )
Call ID : call_KWgyXj3GgdviC01u5KeFZkbQ
Args :
symbol : AAPL
indicator : boll
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_hshUKMGu1yvZ4m8YbJE9SaSg )
Call ID : call_hshUKMGu1yvZ4m8YbJE9SaSg
Args :
symbol : AAPL
indicator : macd
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_Iq9kq9jA2D5E7Png9lPt9bK5 )
Call ID : call_Iq9kq9jA2D5E7Png9lPt9bK5
Args :
symbol : AAPL
indicator : vwma
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_SRSi644IhPjxaMdE7U8xn4a3 )
Call ID : call_SRSi644IhPjxaMdE7U8xn4a3
Args :
symbol : AAPL
indicator : atr
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_Ow6VLKfP52JSFtphkJocda9f )
Call ID : call_Ow6VLKfP52JSFtphkJocda9f
Args :
symbol : AAPL
indicator : supertrend
curr_date : 2024 -11 -19
get_stockstats_indicators_report ( call_FJYy18HBaxQlC8YghPphXpsB )
Call ID : call_FJYy18HBaxQlC8YghPphXpsB
Args :
symbol : AAPL
indicator : cci
curr_date : 2024 -11 -19
The data provided spans from November 4 , 2024 , to November 18 , 2024 , and includes
Commodity Channel Index ( CCI ) values , which measure the deviation of the price
from its average . The CCI values indicate the following trends and insights :

1. ** Initial Missing Data **: On November 4 , 2024 , the CCI value is missing . This
absence of data could be due to a lack of trading activity or data collection
issues , which should be noted but does not provide insight into market
conditions .
2. ** Positive Trend **: From November 5 to November 7 , there is a noticeable upward
trend in CCI values , starting at 66.67 and peaking at 133.33. This suggests a
strong deviation from the average price , indicating potential overbought
conditions . Traders might interpret this as a signal that the market could be
due for a correction or pullback .
3. ** Fluctuations and Correction **: On November 8 , the CCI decreases to 97.80 ,
indicating a slight correction from the previous peak . This is followed by a
significant drop to -9.75 on November 11 , suggesting a shift towards oversold
conditions . Such a rapid change could indicate increased volatility or a
reaction to external market factors .
4. ** Recovery and Stabilization **: From November 12 to November 14 , the CCI values
recover , moving from 10.83 to 109.26. This recovery suggests a return to
positive momentum , potentially indicating renewed buying interest or
stabilization in the market .
5. ** Moderate Fluctuations **: On November 15 , the CCI drops to 30.79 , followed by
an increase to 104.68 on November 18. These fluctuations suggest ongoing
market adjustments , with the CCI remaining in positive territory , indicating
that the market is still experiencing deviations above the average price .
Overall , the data reflects a period of volatility with significant swings in
market sentiment . The initial rise and subsequent fluctuations in CCI values
suggest that traders should be cautious of potential overbought or oversold
conditions . Monitoring these trends can help in making informed decisions
about potential entry or exit points in the market .

"""

news_report_example = """

[ News Analyst ]:
================================== Report ==================================
Based on the recent news from EODHD and Finnhub , here is a comprehensive report on
the current state of the world relevant for trading and macroeconomics :
### Global Economic and Political Environment
1. ** US - China Relations and Trade **: There is ongoing tension between the US and
China , particularly affecting companies like Apple that have significant
operations in China . Jim Cramer highlighted the challenges of doing business
in China amidst political tensions , which could impact Apple ’ s operations and
stock performance .
2. ** US Economic Policy **: The return of Donald Trump to the presidency is
creating mixed reactions in the business community . Some tech executives are
optimistic about potential deregulation and increased innovation , which could
lead to more spending and dealmaking .
3. ** Inflation and Federal Reserve Policy **: The October CPI inflation report
showed a rise to 2.6% , indicating that the Federal Reserve ’ s management of
inflation is on track . However , this has increased the likelihood of a pause
in rate cuts , affecting market expectations and investor sentiment .
### Sector - Specific Insights
1. ** Technology and AI **:
- ** Apple **: Apple is expanding into the smart home market with a new AI - powered
device , competing with Amazon and Google . Despite strong earnings , there are
concerns about overvaluation and challenges in China .
- ** Google ( Alphabet ) **: Google is facing pressure from AI competition in the
search ad business and ongoing DOJ lawsuits . Analysts have mixed views on its
stock , with some not considering it a favored stock currently .
- ** Amazon **: Amazon is making significant moves into full autonomy and expanding
its AI services through AWS . However , its stock recently declined due to
broader market corrections and Federal Reserve comments on interest rates .
2. ** Semiconductors **:
- ** Taiwan Semiconductor Manufacturing Company ( TSMC ) **: The US has finalized a $6
.6 billion subsidy for TSMC ’ s semiconductor production in Arizona ,
highlighting the strategic importance of semiconductor manufacturing . Despite
high demand driven by AI , TSMC is considered overvalued by some analysts due
to geopolitical risks and its role in US - China economic competition .
3. ** Investment Trends **:
- ** AI and Tech Stocks **: There is a continued focus on AI - centric tech giants
like Google , Meta , TSMC , Adobe , and Broadcom for potential double - digit
returns . The rapid adoption of generative AI is likened to the growth of
Facebook , indicating significant investment opportunities in AI technologies .
### Market Sentiment and Investor Behavior
1. ** Portfolio Management **: Major investment firms like Fisher Asset Management
and GMO Capital have shown increased portfolio values , with significant
holdings in tech giants such as Apple , Microsoft , Nvidia , Amazon , and Alphabet
.
2. ** Investor Interest **: There is heightened investor interest in Apple , as
indicated by increased searches and discussions about its stock prospects .
This reflects broader market attention on tech stocks amidst evolving economic
conditions .
### Conclusion
The current global economic landscape is characterized by geopolitical tensions ,
particularly between the US and China , impacting multinational companies . The
technology sector , especially AI and semiconductor industries , remains a focal
point for investors , with significant government support and market interest .
Inflation management by the Federal Reserve continues to influence market
dynamics , affecting investor expectations and stock performance . Traders
should consider these factors when making investment decisions , focusing on
sectors with strong growth potential and navigating geopolitical risks .
================================ Tool Calls ================================
Tool Calls :
get_EODHD_news ( call_RCXogBfhGwyi0IuWCWhpNpQJ )
Call ID : call_RCXogBfhGwyi0IuWCWhpNpQJ
Args :
start_date : 2024 -11 -12
end_date : 2024 -11 -19
get_finnhub_news ( call_zXlMVeXHxfA2X4bDTXmIfeij )
Call ID : call_zXlMVeXHxfA2X4bDTXmIfeij
Args :
ticker : AAPL
start_date : 2024 -11 -12
end_date : 2024 -11 -19
get_finnhub_news ( call_jSKV1zMfHVqrR4GYAeEzjsoy )
Call ID : call_jSKV1zMfHVqrR4GYAeEzjsoy
Args :
ticker : TSM
start_date : 2024 -11 -12
end_date : 2024 -11 -19
get_finnhub_news ( call_7rrmR2Qo5K8O2WbxQc8zDpxB )
Call ID : call_7rrmR2Qo5K8O2WbxQc8zDpxB
Args :
ticker : GOOGL
start_date : 2024 -11 -12
end_date : 2024 -11 -19
get_finnhub_news ( call_XmPHBNBRJINGDZmBeUSnUgps )
Call ID : call_XmPHBNBRJINGDZmBeUSnUgps
Args :
ticker : AMZN
start_date : 2024 -11 -12
end_date : 2024 -11 -19

"""

sentiment_report_example = """

[ Social Media Analyst ]:
================================== Report ==================================
### Comprehensive Analysis of Apple Inc . ( AAPL ) Social Media and Sentiment Trends
( November 12 - November 19 , 2024)
#### Social Media Insights
Upon reviewing the Reddit data for Apple Inc . over the past week , it appears there
were no significant posts or discussions captured in the dataset . This
absence of data could suggest a lack of major events or announcements that
typically drive social media engagement , or it might indicate a gap in data
collection . For investors , this means relying more heavily on sentiment
analysis and news reports for insights during this period .
#### Sentiment Analysis
The sentiment data for Apple Inc . ( AAPL ) from November 4 , 2024 , to November 17 ,
2024 , reveals a dynamic landscape of public perception :
1. ** Positive Sentiment Peaks **:
- ** November 15 , 2024**: A significant positive sentiment was recorded with a
normalized score of 0.5445 , indicating favorable news or developments .
- ** November 11 , 2024**: Another strong positive sentiment day with a score of
0.426 , suggesting positive market reactions or announcements .
2. ** Moderate Positive Sentiment **:
- Several days , including November 14 , 13 , 10 , and 9 , showed moderately positive
sentiment , reflecting a generally favorable outlook towards AAPL .
3. ** Negative Sentiment **:
- ** November 12 , 2024**: A negative sentiment score of -0.201 was observed ,
possibly due to unfavorable news or market conditions .
- ** November 4 , 2024**: The period started with a negative sentiment score of
-0.141 , indicating initial concerns or negative news .
4. ** Neutral Sentiment **:
- ** November 17 , 2024**: The sentiment was neutral , suggesting a lack of
significant positive or negative news impacting perceptions .
5. ** Engagement Levels **:
- The highest engagement was noted on November 6 , 2024 , with a sentiment score of
0.0756 , indicating increased interest or discussions , albeit with a slightly
positive sentiment .
#### Implications for Traders and Investors
- ** Positive Sentiment Days **: The spikes in positive sentiment , particularly on
November 15 and 11 , could be indicative of favorable developments or market
conditions that investors might want to capitalize on .
- ** Negative Sentiment Days **: The negative sentiment on November 12 and 4
suggests caution , as these days might have been influenced by adverse news or
market reactions .
- ** Overall Trend **: The sentiment trend over the period is predominantly positive
, suggesting a generally favorable outlook for AAPL . However , the occasional
dips into negative sentiment highlight the importance of staying informed
about potential risks or negative news .
In conclusion , while the lack of Reddit data limits insights from social media
discussions , the sentiment analysis provides a valuable perspective on market
perceptions of Apple Inc . during this period . Investors should consider these
sentiment trends alongside other market data and news to make informed
decisions .
================================ Tool Calls ================================
Tool Calls :
get_reddit_stock_info ( call_MfJT2mtj22GO32q7Xu5z2htS )
Call ID : call_MfJT2mtj22GO32q7Xu5z2htS
Args :
query : Apple Inc
start_date : 2024 -11 -12
end_date : 2024 -11 -19
get_EODHD_sentiment ( call_So5Csrkq4CJKpi9jiY4ibbB2 )
Call ID : call_So5Csrkq4CJKpi9jiY4ibbB2
Args :
symbol : AAPL
curr_date : 2024 -11 -19
EODHD client initialized
Reddit client initialized
Searching in subreddit : wallstreetbets
Searching in subreddit : stocks
Searching in subreddit : investing
Searching in subreddit : SecurityAnalysis
Searching in subreddit : Finance
Searching in subreddit : Economics
The market sentiment data for AAPL over the period from November 4 , 2024 , to
November 17 , 2024 , provides insights into the prevailing attitudes and
perceptions surrounding the stock . Below is a detailed analysis of the
sentiment trends observed during this period :
1. ** November 17 , 2024**: The sentiment count was 1 , with a normalized sentiment
score of 0. This indicates a neutral sentiment on this day , suggesting no
significant positive or negative sentiment was detected .
2. ** November 16 , 2024**: The sentiment count was 1 , with a normalized sentiment
score of -0.06. This reflects a slightly negative sentiment , although the
impact appears minimal given the low count and score .
3. ** November 15 , 2024**: The sentiment count increased to 2 , with a normalized
sentiment score of 0.5445. This marks a significant positive sentiment ,
indicating a favorable perception of AAPL on this day .
4. ** November 14 , 2024**: The sentiment count was 2 , with a normalized sentiment
score of 0.17. This suggests a moderately positive sentiment , showing a
generally favorable outlook .
5. ** November 13 , 2024**: The sentiment count was 2 , with a normalized sentiment
score of 0.3245. This indicates a positive sentiment , with a noticeable
improvement in perception compared to the previous day .
6. ** November 12 , 2024**: The sentiment count was 2 , with a normalized sentiment
score of -0.201. This reflects a negative sentiment , suggesting some
unfavorable views or news impacting AAPL .
7. ** November 11 , 2024**: The sentiment count was 3 , with a normalized sentiment
score of 0.426. This indicates a strong positive sentiment , with increased
engagement and favorable perception .
8. ** November 10 , 2024**: The sentiment count was 3 , with a normalized sentiment
score of 0.3157. This suggests a positive sentiment , maintaining a favorable
outlook similar to the previous day .
9. ** November 09 , 2024**: The sentiment count was 3 , with a normalized sentiment
score of 0.221. This indicates a positive sentiment , though slightly less
pronounced than the previous days .
10. ** November 08 , 2024**: The sentiment count was 1 , with a normalized sentiment
score of 0.422. This reflects a strong positive sentiment , despite the lower
engagement count .
11. ** November 07 , 2024**: The sentiment count was 2 , with a normalized sentiment
score of 0.144. This suggests a mildly positive sentiment , indicating a
generally favorable view .
12. ** November 06 , 2024**: The sentiment count was 5 , with a normalized sentiment
score of 0.0756. This shows a slightly positive sentiment with the highest
engagement count , suggesting increased interest or discussion around AAPL .
13. ** November 05 , 2024**: The sentiment count was 4 , with a normalized sentiment
score of 0.304. This indicates a positive sentiment , with a relatively high
level of engagement .
14. ** November 04 , 2024**: The sentiment count was 3 , with a normalized sentiment
score of -0.141. This reflects a negative sentiment , suggesting some
unfavorable sentiment or news at the start of the period .
** Summary **: Over the analyzed period , AAPL experienced fluctuations in market
sentiment , with notable positive sentiment spikes on November 15 and November
11. The sentiment was predominantly positive , with occasional dips into
negative territory , particularly on November 12 and November 04. The
engagement levels varied , with the highest count observed on November 06 ,
indicating heightened interest or discussion on that day . Overall , the
sentiment trend suggests a generally favorable outlook for AAPL during this
period , with some days of negative sentiment that may warrant further
investigation .

"""

fundamentals_report_example = """

[ Fundamentals Analyst ]:
================================== Report ==================================
### Comprehensive Fundamental Analysis Report for Apple Inc . ( AAPL )
#### Company Profile
Apple Inc . is a prominent player in the Technology sector , known for its
innovative products and significant market influence . Incorporated in 1980 ,
Apple has a market capitalization of approximately $3 .55 trillion USD , with
15 ,115.82 million shares outstanding . The company is listed on the NASDAQ
under the ticker AAPL .
#### Financial Overview
- **52 - Week Price Range **: $164 .075 - $237 .49
- ** Price Returns **:
- 5 - Day : 2.805%
- 13 - Week : 3.7264%
- 26 - Week : 23.6604%
- 52 - Week : 24.0587%
- Year - to - Date : 22.0225%
- ** Relative Performance **: Underperformed the S & P 500 by -7.6652% over the past
year .
#### Profitability Metrics
- ** Gross Margin **: 46.21%
- ** Operating Margin **: 31.51%
- ** Net Profit Margin **: 23.97%
- ** Return on Equity ( ROE ) **: 164.59%
- ** Return on Assets ( ROA ) **: 25.68%
#### Growth Metrics
- ** EPS Growth **:
- 3 - Year : 2.71%
- 5 - Year : 15.41%
- Quarterly YoY : -34%
- ** Revenue Growth **:
- 3 - Year : 2.25%
- 5 - Year : 8.49%
- Quarterly YoY : 6.07%
#### Liquidity and Solvency
- ** Current Ratio **: 0.8673
- ** Quick Ratio **: 0.826
- ** Long - Term Debt to Equity **: 1.5057
- ** Total Debt to Equity **: 1.8723
#### Valuation Metrics
- ** P / E Ratio **: 37.793
- ** P / B Ratio **: 62.2048
- ** P / CF Ratio **: 30.0517
#### Cash Flow and Dividends
- ** Cash Flow Per Share **: $7 .1978
- ** Dividend Yield **: 0.4287%
- ** Payout Ratio **: 16.25%
#### Insider Sentiment
The insider sentiment for 2024 shows a predominantly negative trend , with several
months exhibiting the most negative Monthly Share Purchase Ratio ( MSPR )
possible . Notably , September showed a dramatic shift to positive sentiment ,
suggesting a temporary bullish outlook .
#### Insider Transactions
Recent insider transactions include significant sales by executives :
- ** Chris Kondo ** sold 4 ,130 shares at $228 .87.
- ** Arthur D . Levinson ** sold 150 ,000 shares over two transactions at prices
around $224 .68 to $228 .66.
- ** Katherine L . Adams ** gifted 8 ,000 shares .
#### Analysis and Insights
- ** Strengths **: Apple demonstrates strong profitability and growth potential ,
supported by high margins and efficient asset utilization .
- ** Weaknesses **: Liquidity constraints and high leverage pose potential risks ,
especially in a rising interest rate environment .
- ** Valuation **: The stock is trading at a premium , which may be justified by its
strong brand and growth prospects , but caution is advised due to potential
overvaluation .
#### Investment Considerations
- ** Caution on Valuation **: Insider sales suggest potential concerns about stock
valuation . Investors should consider reviewing their positions .
- ** Monitor Insider Activity **: Continued monitoring of insider transactions is
recommended to validate concerns about stock valuation or company performance .
- ** Short - term Strategy **: Given the negative insider sentiment , short - term
bearish strategies might be considered .
#### Conclusion
Apple Inc . remains a financially robust company with impressive profitability and
growth metrics . However , potential investors should weigh the high valuation
and leverage against the company ’ s strong market position and growth potential
. The insider sentiment and transactions suggest caution , particularly
regarding stock valuation . Investors should consider these factors alongside
broader market conditions and company performance when making investment
decisions .
================================ Tool Calls ================================
Tool Calls :
get_finnhub_company_profile ( call_ScxiITX7Hf6yUuOr8g41a6WP )
Call ID : call_ScxiITX7Hf6yUuOr8g41a6WP
Args :
ticker : AAPL
Tool Calls :
get_finnhub_company_financials_history ( call_jwgyq9XbocVWIMsOpagIArQO )
Call ID : call_jwgyq9XbocVWIMsOpagIArQO
Args :
ticker : AAPL
freq : quarterly
end_date : 2024 -11 -19
get_finnhub_basic_company_financials ( call_o2JV2EjmMuTK3Z85debseS9C )
Call ID : call_o2JV2EjmMuTK3Z85debseS9C
Args :
ticker : AAPL
get_finnhub_company_insider_sentiment ( call_DqhGKetFeNB3zWlHLJdrTE8H )
Call ID : call_DqhGKetFeNB3zWlHLJdrTE8H
Args :
ticker : AAPL
curr_date : 2024 -11 -19
get_finnhub_company_insider_transactions ( call_v78N7hIUA4CufM6EIgErEroZ )
Call ID : call_v78N7hIUA4CufM6EIgErEroZ
Args :
ticker : AAPL
curr_date : 2024 -11 -19

"""