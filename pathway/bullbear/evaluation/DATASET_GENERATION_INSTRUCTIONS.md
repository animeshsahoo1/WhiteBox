# Bull-Bear Debate Evaluation Dataset Generation Instructions

## 1. System Overview (Context for Dataset Generator)

You are generating test data for a **Bull-Bear Investment Debate System**. This system:

1. Takes **4 input reports** for a stock symbol:
   - `news_report` - Recent news headlines, announcements, events
   - `sentiment_report` - Social media sentiment, analyst sentiment scores
   - `market_report` - Technical indicators, price action, volume, support/resistance
   - `fundamental_report` - P/E, revenue, earnings, valuation metrics

2. Optionally takes a **previous facilitator report** (for delta computation)

3. Runs a multi-round debate between:
   - **Bull Agent**: Argues for buying/bullish thesis
   - **Bear Agent**: Argues for selling/bearish thesis
   - **Facilitator**: Synthesizes and produces BUY/HOLD/SELL recommendation

4. Produces outputs we need to evaluate:
   - Debate points (arguments from each side)
   - Final recommendation (BUY/HOLD/SELL)
   - Facilitator report (investment memo)

---

## 2. Dataset Structure

Generate datasets as JSON files with this structure:

```json
{
  "dataset_id": "unique_id",
  "scenario_category": "category_name",
  "scenario_name": "descriptive_name",
  "difficulty": "easy|medium|hard|adversarial",
  
  "symbol": "TICKER",
  "company_name": "Full Company Name",
  "sector": "Technology|Healthcare|Finance|...",
  
  "inputs": {
    "news_report": "...",
    "sentiment_report": "...",
    "market_report": "...",
    "fundamental_report": "...",
    "previous_facilitator_report": "..." // Optional - for delta testing
  },
  
  "ground_truth": {
    "expected_recommendation": "BUY|HOLD|SELL",
    "expected_confidence": "HIGH|MEDIUM|LOW",
    "key_bull_points": ["point1", "point2", ...],
    "key_bear_points": ["point1", "point2", ...],
    "must_mention_facts": ["fact1", "fact2", ...],
    "must_not_hallucinate": ["false_claim1", ...]
  },
  
  "streaming_sequence": [  // For time-series scenarios
    {"timestamp": "T+0", "event_type": "news", "content": "..."},
    {"timestamp": "T+1min", "event_type": "sentiment_shift", "content": "..."},
    ...
  ],
  
  "evaluation_focus": ["metric1", "metric2", ...],
  "notes": "Additional context for evaluators"
}
```

---

## 3. Scenario Categories to Generate

### Category A: Clear Directional Signals (Baseline)

Generate scenarios where the correct recommendation is obvious:

#### A1. Strong Buy Signals
```
- Massive earnings beat (20%+ above expectations)
- Major product launch success
- Acquisition at premium
- Analyst upgrades across the board
- Technical breakout with high volume
```

**Example scenario:**
- Company: TechCorp (TECH)
- News: "TechCorp reports Q4 EPS of $3.50 vs $2.80 expected, raises FY guidance 15%"
- Sentiment: 85% positive social media, all major analysts upgraded
- Market: Stock up 12% pre-market, breaking 52-week high
- Fundamental: P/E still below sector average despite rally
- **Expected: BUY with HIGH confidence**

#### A2. Strong Sell Signals
```
- Massive earnings miss
- SEC investigation/fraud allegations
- CEO resignation under pressure
- Major product recall
- Debt downgrade to junk status
```

#### A3. Clear Hold Signals
```
- Mixed earnings (beat on revenue, miss on EPS)
- Stock at fair value by multiple metrics
- No near-term catalysts
- Balanced bull/bear arguments
```

---

### Category B: Ambiguous/Edge Cases

#### B1. Conflicting Signals
Generate scenarios where different report types contradict:

```
Scenario: "Sentiment vs Fundamentals Conflict"
- News: Neutral
- Sentiment: Extremely bullish (90% positive, trending on social media)
- Market: Overbought RSI, extended from moving averages
- Fundamental: P/E at 150x, negative free cash flow
- Dilemma: Momentum vs valuation
- Expected: HOLD or SELL (meme stock dynamics)
```

```
Scenario: "News vs Technical Conflict"
- News: Company announces major partnership
- Sentiment: Positive
- Market: Stock already up 80% YTD, heavily overbought
- Fundamental: Now trading at 50x forward earnings
- Dilemma: Good news priced in vs momentum continuation
```

#### B2. Rapidly Changing Information
Generate time-series data where information changes:

```
Streaming Sequence:
T+0: News - "Company to acquire competitor for $2B"
T+1: Sentiment shifts to very bullish
T+5: News - "Regulators express antitrust concerns"
T+6: Sentiment drops to neutral
T+10: News - "Acquisition blocked by FTC"
T+11: Stock drops 8%

Evaluation: Does system correctly update recommendation as info changes?
```

#### B3. Incomplete Information
Generate scenarios with missing or sparse data:

```
- Only 2 sentences in news report
- No recent analyst coverage
- Low trading volume (illiquid)
- Private company financials (limited data)
```

---

### Category C: Adversarial Cases

#### C1. Misleading Data
Test if agents can identify false/misleading information:

```
Scenario: "Pump and Dump Signals"
- News: Multiple press releases with vague "partnerships"
- Sentiment: Sudden spike from bot-like accounts
- Market: Low volume, high volatility
- Fundamental: $0 revenue, no products
- Expected: SELL (scam detection)
```

#### C2. Contradictory Ground Truth
Scenarios where reasonable analysts could disagree:

```
Scenario: "Growth vs Value Debate"
- Company growing 40% YoY
- Trading at 100x earnings
- TAM expanding rapidly
- Heavy competition entering space
- No clear "right" answer - test argumentation quality
```

#### C3. Black Swan Events
Sudden, unprecedented events:

```
Scenario: "Overnight Crisis"
- Previous day: All metrics positive
- Overnight: CEO arrested for fraud
- All other reports still show old positive data
- Test: Does system properly weight breaking news?
```

---

### Category D: Report Coverage Testing

Generate scenarios that require citing specific reports:

#### D1. News-Dependent Decision
Decision hinges on news that MUST be cited:

```
- FDA approval announcement (must cite news)
- Earnings release details (must cite fundamental)
- Technical breakout (must cite market)
- Sentiment shift (must cite sentiment)
```

#### D2. Multi-Report Integration
Scenario requires synthesizing all 4 reports:

```
Expected output should reference:
- "According to the news report..." (news citation)
- "Technical indicators show..." (market citation)
- "Social sentiment has shifted..." (sentiment citation)
- "Valuation metrics indicate..." (fundamental citation)
```

---

### Category E: Temporal/Delta Scenarios

#### E1. Report Changes Over Time
Generate paired reports (old vs new) to test delta detection:

```
Old News Report: "Company announces restructuring plan"
New News Report: "Restructuring complete, 20% cost reduction achieved"
Expected Delta: Material positive development
```

#### E2. Facilitator History Testing
Generate previous facilitator reports with known outcomes:

```
Previous Report: "BUY recommendation based on expected earnings beat"
Actual Outcome: Earnings missed, stock down 15%
Current Scenario: Similar setup
Expected: System should learn from past mistake
```

---

### Category F: Evidence Density Testing

#### F1. High Evidence Scenario
Reports packed with citable facts:

```
News Report contains:
- 5 specific price targets from analysts
- 3 named sources
- 2 quantitative metrics
- Timeline of events

Expected: High evidence density in debate points
```

#### F2. Low Evidence Scenario
Vague, opinion-based reports:

```
News Report: "Some analysts think the stock could go up. Market conditions are uncertain."
No specific data points, no named sources

Expected: Debate should acknowledge evidence limitations
```

---

### Category G: Bias Detection Scenarios

#### G1. Bull-Favored Data
Generate data that makes Bull case much easier:

```
- 10 positive data points
- 2 weak negative points
- Test: Does Bear agent still make valid counter-arguments?
- Measure: Elo rating impact
```

#### G2. Bear-Favored Data
Generate data that makes Bear case much easier:

```
- Opposite of above
- Test: Does Bull agent avoid capitulating entirely?
```

---

## 4. Report Content Guidelines

### News Report Format
```markdown
# News Summary for {SYMBOL}
## Latest Headlines

1. **{Headline 1}** - {Source, Date}
   {2-3 sentence summary with specific numbers}

2. **{Headline 2}** - {Source, Date}
   {Summary}

## Key Events
- {Event 1 with date and impact}
- {Event 2}

## Analyst Actions
- {Analyst firm}: {Action} with PT ${price}

Last Updated: {timestamp}
```

### Sentiment Report Format
```markdown
# Sentiment Analysis for {SYMBOL}

## Overall Sentiment: {BULLISH|BEARISH|NEUTRAL} (Score: X.X/10)

### Social Media Metrics
- Twitter: X% Positive, Y% Neutral, Z% Negative
- Reddit: {Sentiment description}, {mention count} mentions
- StockTwits: {Message count} messages, {sentiment}

### Analyst Sentiment
- Buy ratings: X
- Hold ratings: Y
- Sell ratings: Z
- Average PT: ${price}

### Key Themes
- {Theme 1}
- {Theme 2}
```

### Market Report Format
```markdown
# Technical Analysis for {SYMBOL}

## Price Action
- Current Price: ${price}
- 24h Change: {+/-X.X%}
- 52-Week Range: ${low} - ${high}
- Volume: {X}M ({vs average})

## Technical Indicators
- RSI (14): {value} ({interpretation})
- MACD: {bullish/bearish crossover, X days ago}
- 50-Day MA: ${value} (price {above/below})
- 200-Day MA: ${value} (price {above/below})

## Support/Resistance
- Support: ${level1}, ${level2}
- Resistance: ${level1}, ${level2}

## Trend Analysis
{2-3 sentences on overall trend}
```

### Fundamental Report Format
```markdown
# Fundamental Analysis for {SYMBOL}

## Valuation Metrics
- P/E Ratio: {X.X} (Industry avg: {Y.Y})
- Forward P/E: {X.X}
- P/S Ratio: {X.X}
- EV/EBITDA: {X.X}

## Financial Health
- Revenue (TTM): ${X}B ({+/-X%} YoY)
- Net Income: ${X}B ({+/-X%} YoY)
- Free Cash Flow: ${X}B
- Debt/Equity: {X.XX}

## Growth Metrics
- Revenue Growth (3Y CAGR): {X.X%}
- EPS Growth (3Y CAGR): {X.X%}

## Competitive Position
{2-3 sentences on moat, market share}
```

---

## 5. Quantity Requirements

Generate the following minimum counts:

| Category | Min. Scenarios | Priority |
|----------|---------------|----------|
| A. Clear Signals | 15 (5 each: buy/sell/hold) | High |
| B. Ambiguous Cases | 20 | Critical |
| C. Adversarial | 10 | High |
| D. Report Coverage | 10 | Medium |
| E. Temporal/Delta | 10 | High |
| F. Evidence Density | 6 (3 high, 3 low) | Medium |
| G. Bias Detection | 10 (5 bull-favored, 5 bear-favored) | High |

**Total: 81+ scenarios minimum**

---

## 6. Streaming Data Sequences

For real-time testing, generate streaming sequences:

```json
{
  "sequence_id": "stream_001",
  "scenario": "earnings_day",
  "duration_simulated": "4 hours",
  "events": [
    {
      "timestamp": "T+0:00",
      "report_type": "all",
      "description": "Initial state - 30 min before earnings",
      "news_report": "...",
      "sentiment_report": "...",
      "market_report": "...",
      "fundamental_report": "..."
    },
    {
      "timestamp": "T+0:30",
      "report_type": "news",
      "event": "EARNINGS_RELEASE",
      "content": "Company reports Q4 EPS of $X.XX vs $Y.YY expected...",
      "expected_reaction": "If beat: bullish shift. If miss: bearish shift."
    },
    {
      "timestamp": "T+0:35",
      "report_type": "market",
      "event": "PRICE_REACTION",
      "content": "Stock moves {direction} {X%} on earnings..."
    },
    {
      "timestamp": "T+1:00",
      "report_type": "sentiment",
      "event": "SOCIAL_REACTION",
      "content": "Sentiment shifts to {bullish/bearish}..."
    },
    {
      "timestamp": "T+2:00",
      "report_type": "news",
      "event": "EARNINGS_CALL_HIGHLIGHTS",
      "content": "CEO announces {guidance/news}..."
    }
  ],
  "checkpoints": [
    {"at": "T+0:00", "expected_recommendation": "HOLD"},
    {"at": "T+0:45", "expected_recommendation": "BUY/SELL based on beat/miss"},
    {"at": "T+2:30", "expected_recommendation": "Final based on call"}
  ]
}
```

---

## 7. Edge Cases Checklist

Ensure dataset covers these edge cases:

### Data Quality Edge Cases
- [ ] Empty report (one report is blank)
- [ ] Very short report (< 50 words)
- [ ] Very long report (> 5000 words)
- [ ] Report with only bullet points
- [ ] Report with only prose
- [ ] Report with tables/structured data
- [ ] Report with contradictory statements within itself

### Logical Edge Cases
- [ ] All reports agree (unanimous bullish)
- [ ] All reports agree (unanimous bearish)
- [ ] All reports neutral (no signal)
- [ ] 3 bullish, 1 strongly bearish
- [ ] 2 bullish, 2 bearish (split)
- [ ] Reports contradict each other explicitly

### Temporal Edge Cases
- [ ] Old data (reports from 1 week ago)
- [ ] Breaking news (T+0 scenario)
- [ ] After-hours event
- [ ] Pre-market event
- [ ] Weekend event (delayed reaction)

### Market Condition Edge Cases
- [ ] General market crash (systematic risk)
- [ ] Sector rotation event
- [ ] Interest rate decision day
- [ ] Black swan event (pandemic, war, etc.)

### Company-Specific Edge Cases
- [ ] Pre-earnings (uncertainty)
- [ ] Post-earnings (reaction analysis)
- [ ] M&A announcement
- [ ] Stock split/dividend announcement
- [ ] Management change
- [ ] Product launch
- [ ] Regulatory action

---

## 8. Output File Structure

Organize generated datasets as:

```
evaluation/
├── datasets/
│   ├── clear_signals/
│   │   ├── strong_buy_001.json
│   │   ├── strong_buy_002.json
│   │   └── ...
│   ├── ambiguous_cases/
│   │   ├── conflicting_signals_001.json
│   │   └── ...
│   ├── adversarial/
│   │   └── ...
│   ├── temporal/
│   │   └── ...
│   └── streaming/
│       ├── earnings_sequence_001.json
│       └── ...
├── ground_truth_summary.json  # Aggregated ground truths
└── dataset_manifest.json       # Index of all datasets
```

---

## 9. Validation Criteria

Each generated scenario MUST:

1. **Be internally consistent** - Numbers should add up, dates should be chronological
2. **Have realistic values** - P/E between 5-500, prices within reason, volumes realistic
3. **Include ground truth** - Expected recommendation with reasoning
4. **Specify evaluation focus** - Which metrics this scenario tests
5. **Use real-world patterns** - Based on actual market dynamics, not fantasy

---

## 10. Example Complete Scenario

```json
{
  "dataset_id": "ambig_conflict_001",
  "scenario_category": "ambiguous_cases",
  "scenario_name": "Meme Stock Dynamics - Sentiment vs Valuation",
  "difficulty": "hard",
  
  "symbol": "MEME",
  "company_name": "Meme Entertainment Corp",
  "sector": "Consumer Discretionary",
  
  "inputs": {
    "news_report": "# News Summary for MEME\n\n## Latest Headlines\n\n1. **MEME Stock Surges 150% This Week on Reddit Frenzy** - Reuters, Dec 6\n   The stock has become the most discussed on r/wallstreetbets with over 50,000 mentions. Short interest remains at 45% of float.\n\n2. **Company Has No Comment on Stock Movement** - PR Newswire, Dec 5\n   Management declined to comment on the unusual trading activity.\n\n## Key Events\n- Dec 4: Stock added to list of securities with heightened volatility\n- Dec 3: Options volume hit 500% of average\n\nLast Updated: 2024-12-06T14:00:00Z",
    
    "sentiment_report": "# Sentiment Analysis for MEME\n\n## Overall Sentiment: EXTREMELY BULLISH (Score: 9.5/10)\n\n### Social Media Metrics\n- Twitter: 92% Positive, 5% Neutral, 3% Negative\n- Reddit: #1 trending on WSB, 50,000+ mentions\n- StockTwits: 15,000 messages today, 95% bullish\n\n### Analyst Sentiment\n- No active analyst coverage\n\n### Key Themes\n- Short squeeze potential\n- Diamond hands mentality\n- Retail vs institutional narrative",
    
    "market_report": "# Technical Analysis for MEME\n\n## Price Action\n- Current Price: $45.00\n- 24h Change: +35%\n- 52-Week Range: $2.50 - $48.00 (near high)\n- Volume: 150M (25x average)\n\n## Technical Indicators\n- RSI (14): 95 (Extremely Overbought)\n- MACD: Parabolic, off the charts\n- 50-Day MA: $8.50 (price 430% above)\n- 200-Day MA: $5.20 (price 765% above)\n\n## Trend Analysis\nStock is in a parabolic short squeeze pattern with no technical support until $15.",
    
    "fundamental_report": "# Fundamental Analysis for MEME\n\n## Valuation Metrics\n- P/E Ratio: N/A (negative earnings)\n- P/S Ratio: 450x (industry avg: 2x)\n- Market Cap: $9B\n- Enterprise Value: $9.5B\n\n## Financial Health\n- Revenue (TTM): $20M (-15% YoY)\n- Net Income: -$50M (widening losses)\n- Free Cash Flow: -$40M\n- Cash on hand: $30M (8 months runway)\n- Debt: $80M\n\n## Competitive Position\nLegacy retailer with declining foot traffic. No clear digital strategy. Competing against Amazon and major retailers."
  },
  
  "ground_truth": {
    "expected_recommendation": "SELL",
    "expected_confidence": "HIGH",
    "reasoning": "Despite extreme bullish sentiment, fundamentals show a failing business trading at absurd valuations. This is a speculative frenzy, not investment.",
    "key_bull_points": [
      "Short squeeze potential with 45% short interest",
      "Unprecedented retail momentum",
      "Historical examples of squeezes reaching higher"
    ],
    "key_bear_points": [
      "Zero fundamental support for current price",
      "Negative earnings with no path to profitability",
      "RSI at 95 indicates extreme overbought",
      "No analyst coverage suggests institutional avoidance",
      "Price 765% above 200-day MA is unsustainable"
    ],
    "must_mention_facts": [
      "45% short interest",
      "Negative earnings",
      "P/S of 450x",
      "RSI at 95"
    ],
    "must_not_hallucinate": [
      "Positive earnings",
      "Analyst buy ratings",
      "Revenue growth"
    ]
  },
  
  "evaluation_focus": [
    "directional_accuracy",
    "evidence_density",
    "bias_detection",
    "argumentation_quality"
  ],
  
  "notes": "Tests if system can resist extreme sentiment and make fundamentals-based decision. Both Bull and Bear should make valid points, but recommendation should be SELL."
}
```

---

## 11. Instructions Summary

1. **Generate 80+ diverse scenarios** across all categories
2. **Use realistic market data patterns** - not random numbers
3. **Include ground truth** for every scenario
4. **Create streaming sequences** for temporal testing
5. **Cover all edge cases** in the checklist
6. **Maintain consistent JSON format**
7. **Organize by category** in folder structure

When generating, think like a hedge fund analyst creating test cases for a trading system. The goal is to stress-test the Bull-Bear debate system's ability to:
- Identify correct recommendations
- Make well-supported arguments
- Handle ambiguity appropriately
- Resist manipulation/noise
- Cite evidence properly
- Converge on conclusions efficiently
