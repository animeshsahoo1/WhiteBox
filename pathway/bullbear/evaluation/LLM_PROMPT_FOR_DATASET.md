# PROMPT FOR GENERATING BULL-BEAR EVALUATION DATASETS

Copy everything below this line and paste to another LLM (Claude, GPT-4, etc.):

---

## YOUR TASK

Generate evaluation datasets for a Bull-Bear investment debate AI system. Each dataset has:
- 4 input reports (news, sentiment, market, fundamental)
- Ground truth (expected BUY/HOLD/SELL and key arguments)

## OUTPUT FORMAT

Output ONLY valid JSON. For each scenario:

```json
{
  "dataset_id": "category_nnn",
  "scenario_name": "Short descriptive name",
  "category": "clear_signals OR ambiguous OR adversarial",
  "difficulty": "easy OR medium OR hard",
  "symbol": "TICKER",
  "company_name": "Full Name",
  "sector": "Industry",
  "inputs": {
    "news_report": "Full markdown report with headlines, events, analyst actions",
    "sentiment_report": "Full markdown with social metrics, analyst ratings, themes",
    "market_report": "Full markdown with price, technicals, support/resistance",
    "fundamental_report": "Full markdown with valuation, financials, growth"
  },
  "ground_truth": {
    "expected_recommendation": "BUY OR HOLD OR SELL",
    "expected_confidence": "HIGH OR MEDIUM OR LOW",
    "reasoning": "Why this is the correct answer",
    "key_bull_points": ["What Bull should argue"],
    "key_bear_points": ["What Bear should argue"]
  }
}
```

## WHAT TO GENERATE

Generate 10 scenarios for each request. Focus on these categories:

### Request 1: Clear BUY Signals (5 scenarios)
- Earnings beat + guidance raise
- Major acquisition at premium
- Analyst upgrades
- Technical breakout
- Product launch success

### Request 2: Clear SELL Signals (5 scenarios)
- Fraud/investigation
- Massive earnings miss
- CEO resignation
- Product failure/recall
- Debt crisis

### Request 3: Ambiguous/HOLD Cases (10 scenarios)
- Conflicting signals (bullish sentiment + bad fundamentals)
- Mixed earnings (beat revenue, miss EPS)
- Fair valuation with no catalysts
- Good company at expensive price
- Turnaround story with uncertainty

### Request 4: Adversarial Cases (5 scenarios)
- Meme stock with extreme sentiment but no fundamentals
- Pump and dump patterns
- Short squeeze setup
- Misleading/incomplete data
- Breaking news that contradicts other reports

## REPORT REQUIREMENTS

Each report must be realistic markdown with:

**News Report:**
- 3+ headlines with sources and dates
- Specific numbers (EPS, revenue, %)
- Key events section
- Analyst actions with price targets

**Sentiment Report:**
- Overall score /10
- Twitter/Reddit/StockTwits percentages
- Buy/Hold/Sell analyst count
- Key themes

**Market Report:**
- Current price and changes
- RSI, MACD, moving averages with interpretations
- Support/resistance levels
- Trend analysis paragraph

**Fundamental Report:**
- P/E, P/S, EV/EBITDA vs industry
- Revenue, net income, FCF with YoY growth
- Debt ratios
- Competitive position paragraph

## IMPORTANT RULES

1. ALL numbers must be realistic (P/E 5-500, RSI 0-100, prices coherent)
2. Reports must be internally consistent (if news says stock down, market report shows decline)
3. Ground truth must logically follow from the data
4. Include 3-5 key_bull_points and 3-5 key_bear_points for each
5. Use fictional ticker symbols (don't use real companies)
6. Each report should be 200-400 words

## START GENERATION

Generate 5 clear BUY signal scenarios first. Output as a JSON array.
