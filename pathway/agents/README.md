# Pathway AI Agents

LLM-powered analysis agents that process streaming data and generate comprehensive reports.

## 📋 Overview

Each agent:
- Receives Pathway tables from consumers
- Applies windowing and aggregation
- Calculates domain-specific metrics
- Generates LLM-powered analysis
- Outputs structured reports

## 🗂️ Files

- **market_agent.py** - Technical market analysis
- **news_agent.py** - News synthesis and impact analysis
- **sentiment_agent.py** - Social media sentiment interpretation
- **fundamental_agent.py** - Fundamental financial analysis

## 🤖 Agent Implementations

### Market Agent

**Purpose**: Technical analysis of price movements

**Process Flow**:
```
Market Table → Calculate Indicators → Window (1-min) → 
Aggregate Metrics → LLM Analysis → Report
```

**Technical Indicators**:
```python
# Price metrics
price_range = high - low
typical_price = (high + low + close) / 3
price_vs_open = ((close - open) / open) * 100

# Volatility
intraday_volatility = ((high - low) / low) * 100

# Window aggregates
max_price = reducers.max(current_price)
min_price = reducers.min(current_price)
avg_price = reducers.avg(current_price)
price_std = reducers.stddev(current_price)
```

**LLM Prompt Template**:
```
You are a market analyst. Analyze this data:

Symbol: {symbol}
Price: ${current_price} ({change_percent:+.2f}%)
Range: ${low} - ${high}
Volatility: {volatility:.2f}%
Avg Price: ${avg_price:.2f}

Provide:
1. Technical Overview
2. Price Action Analysis
3. Key Levels
4. Short-term Outlook
```

**Usage**:
```python
from agents.market_agent import process_market_stream

reports = process_market_stream(
    market_table,
    reports_directory="./reports/market"
)
```

### News Agent

**Purpose**: Synthesize news articles and assess impact

**Process Flow**:
```
News Table → Window (5-min) → Group by Symbol → 
Aggregate Articles → LLM Synthesis → Report
```

**Aggregation**:
```python
# Collect all news within window
news_list = reducers.tuple(
    title=pw.this.title,
    description=pw.this.description,
    source=pw.this.source,
    sentiment=pw.this.sentiment,
    url=pw.this.url
)
```

**LLM Prompt Template**:
```
You are a financial news analyst. Synthesize these articles:

Symbol: {symbol}
Period: {window_start} to {window_end}
Articles: {article_count}

[Article 1]
Title: {title_1}
Description: {desc_1}
Source: {source_1}
Sentiment: {sentiment_1}

[Article 2]
...

Provide:
1. Executive Summary
2. Key Developments
3. Market Implications
4. Sentiment Assessment
```

**Usage**:
```python
from agents.news_agent import process_news_stream

reports = process_news_stream(
    news_table,
    reports_directory="./reports/news"
)
```

### Sentiment Agent

**Purpose**: Interpret social media sentiment and discussion

**Process Flow**:
```
Sentiment Table → Window (5-min) → Calculate Metrics → 
Aggregate Posts → LLM Interpretation → Report
```

**Metrics Calculated**:
```python
# Sentiment metrics
avg_sentiment = reducers.avg(sentiment_score)
positive_pct = (positive_count / total) * 100
negative_pct = (negative_count / total) * 100
neutral_pct = (neutral_count / total) * 100

# Platform breakdown
reddit_mentions = reducers.count_if(platform == 'reddit')
twitter_mentions = reducers.count_if(platform == 'twitter')

# Engagement
avg_score = reducers.avg(score)  # Upvotes/likes
total_comments = reducers.sum(comments)
```

**LLM Prompt Template**:
```
You are a social media analyst. Interpret this sentiment data:

Symbol: {symbol}
Period: {window_start} to {window_end}

Metrics:
- Total Mentions: {total_mentions}
- Avg Sentiment: {avg_sentiment:.2f} (-1 to 1)
- Positive: {positive_pct:.1f}%
- Negative: {negative_pct:.1f}%
- Neutral: {neutral_pct:.1f}%

Platform Breakdown:
- Reddit: {reddit_mentions} posts
- Twitter: {twitter_mentions} tweets

Top Posts:
[Post 1]: {top_post_1}
[Post 2]: {top_post_2}

Provide:
1. Overall Sentiment Assessment
2. Key Discussion Points
3. Platform Insights
4. Trend Analysis
```

**Usage**:
```python
from agents.sentiment_agent import process_sentiment_stream

reports = process_sentiment_stream(
    sentiment_table,
    reports_directory="./reports/sentiment"
)
```

### Fundamental Agent

**Purpose**: Evaluate company fundamentals and financials

**Process Flow**:
```
Fundamental Table → Latest Data → Parse Metrics → 
LLM Analysis → Report
```

**Data Extracted**:
```python
# Company info
company_name = profile["companyName"]
industry = profile["industry"]
sector = profile["sector"]

# Financial metrics
revenue = financials["revenue"]
net_income = financials["netIncome"]
total_assets = financials["totalAssets"]
total_debt = financials["totalDebt"]

# Ratios
pe_ratio = ratios["peRatio"]
pb_ratio = ratios["pbRatio"]
roe = ratios["returnOnEquity"]
debt_to_equity = ratios["debtToEquity"]

# Growth
revenue_growth = growth["revenueGrowth"]
earnings_growth = growth["earningsGrowth"]
```

**LLM Prompt Template**:
```
You are a fundamental analyst. Evaluate this company:

Company: {company_name}
Sector: {sector} | Industry: {industry}

Financial Metrics:
- Revenue: ${revenue:,.0f}
- Net Income: ${net_income:,.0f}
- Total Assets: ${total_assets:,.0f}
- Total Debt: ${total_debt:,.0f}

Valuation Ratios:
- P/E Ratio: {pe_ratio:.2f}
- P/B Ratio: {pb_ratio:.2f}
- ROE: {roe:.2f}%
- Debt/Equity: {debt_to_equity:.2f}

Growth Rates:
- Revenue Growth: {revenue_growth:+.2f}%
- Earnings Growth: {earnings_growth:+.2f}%

Provide:
1. Company Overview
2. Financial Health Analysis
3. Valuation Assessment
4. Growth Outlook
5. Investment Thesis
```

**Usage**:
```python
from agents.fundamental_agent import process_fundamental_stream

reports = process_fundamental_stream(
    fundamental_table,
    reports_directory="./reports/fundamental"
)
```

## 🔧 Configuration

### LLM Settings

All agents use OpenAI's GPT models:
```python
from pathway.xpacks.llm import llms

chat = llms.OpenAIChat(
    model="gpt-4o-mini",          # Model selection
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.0,              # Deterministic (0) or creative (0.7)
    cache_strategy=pw.udfs.DefaultCache()  # Cache responses
)
```

**Available Models**:
- `gpt-4o-mini` - Fast, cost-effective (recommended)
- `gpt-4o` - Most capable
- `gpt-4-turbo` - Balanced
- `gpt-3.5-turbo` - Budget option

### Window Configuration

```python
# Market: 1-minute windows (high frequency)
window = pw.temporal.tumbling(duration=timedelta(minutes=1))

# News/Sentiment: 5-minute windows (moderate frequency)
window = pw.temporal.tumbling(duration=timedelta(minutes=5))

# Fundamentals: No windowing (latest data only)
```

### Report Output

Each agent saves reports to:
- **Redis cache** - Real-time distribution
- **CSV files** - Historical archive
- **Markdown files** - Human-readable format (per symbol)

```python
# Redis caching
observer = get_report_observer("market")
pw.io.python.write(table, observer)

# CSV output
pw.io.csv.write(table, "reports/market/stream.csv")

# File output
table.subscribe(save_report_to_file)
```

## 📊 Report Structure

All reports follow this structure:

### Markdown Format
```markdown
# {Symbol} {Report Type} Report

**Last Updated**: {timestamp}

## Section 1
Analysis content...

## Section 2
More analysis...

## Key Takeaways
- Point 1
- Point 2
- Point 3
```

### Redis Cache Format
```json
{
  "symbol": "AAPL",
  "report_type": "market",
  "content": "markdown content...",
  "last_updated": "2025-11-11T10:01:00",
  "received_at": "2025-11-11T10:01:05",
  "processing_time": 123456789
}
```

## 🧪 Testing

### Test Agent Locally

```python
import pathway as pw
from agents.market_agent import process_market_stream
from consumers.market_data_consumer import MarketDataConsumer

# Create test data
test_data = pw.debug.table_from_pandas(pd.DataFrame({
    "symbol": ["AAPL"],
    "current_price": [178.50],
    "high": [179.20],
    "low": [176.80],
    "sent_at": ["2025-11-11T10:00:00.000"]
}))

# Process
reports = process_market_stream(test_data, "./test_reports")
pw.debug.compute_and_print(reports)
```

### Verify LLM Calls

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run agent
# Will log: "Calling OpenAI API with prompt: ..."
```

### Check Output

```bash
# View Redis cache
docker exec -it redis redis-cli
HGET reports:AAPL market

# View CSV output
cat pathway/reports/market/market_analysis_stream.csv

# View markdown files
cat pathway/reports/market/AAPL/market_report.md
```

## 📈 Performance

### Processing Time
- Market analysis: ~2-4 seconds per window
- News synthesis: ~3-5 seconds per window
- Sentiment interpretation: ~2-4 seconds per window
- Fundamental analysis: ~4-6 seconds per update

### LLM Costs (gpt-4o-mini)
- Market report: ~$0.001 per analysis
- News report: ~$0.002 per synthesis
- Sentiment report: ~$0.001 per interpretation
- Fundamental report: ~$0.003 per analysis

### Caching Benefits
- Cache hit: <1ms (no LLM call)
- Cache miss: 2-5 seconds (LLM call)
- Cache strategy: Based on input hash

## 🛡️ Error Handling

### LLM API Failures
```python
try:
    response = chat(prompt)
except Exception as e:
    logger.error(f"LLM error: {e}")
    response = "Analysis unavailable due to API error"
```

### Missing Data
```python
# Use pw.coalesce for safe field access
current_price = pw.coalesce(pw.this.current_price, 0.0)
```

### Window Triggers
```python
# Handle empty windows gracefully
if not window_data:
    return "No data in window"
```

## 📝 Creating New Agent

```python
import pathway as pw
from pathway.xpacks.llm import llms
import os

def process_custom_stream(table: pw.Table, reports_directory: str) -> pw.Table:
    """Process custom data stream"""
    
    # 1. Initialize LLM
    chat = llms.OpenAIChat(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.0
    )
    
    # 2. Apply windowing
    windowed = table.windowby(
        pw.this.sent_at.dt.strptime("%Y-%m-%dT%H:%M:%S.%f"),
        window=pw.temporal.tumbling(duration=timedelta(minutes=5))
    )
    
    # 3. Calculate metrics
    metrics = windowed.reduce(
        symbol=pw.this.symbol,
        metric1=pw.reducers.avg(pw.this.value),
        metric2=pw.reducers.count(),
        window_end=pw.this._pw_window_end
    )
    
    # 4. Generate LLM analysis
    @pw.udf
    def create_prompt(symbol, metric1, metric2):
        return f"""Analyze this data for {symbol}:
        Metric 1: {metric1}
        Metric 2: {metric2}
        
        Provide analysis..."""
    
    analyzed = metrics.select(
        symbol=pw.this.symbol,
        prompt=create_prompt(pw.this.symbol, pw.this.metric1, pw.this.metric2),
        window_end=pw.this.window_end
    ).select(
        symbol=pw.this.symbol,
        llm_analysis=chat(pw.this.prompt),
        window_end=pw.this.window_end
    )
    
    # 5. Cache in Redis
    from redis_cache import get_report_observer
    observer = get_report_observer("custom")
    pw.io.python.write(analyzed, observer)
    
    return analyzed
```

## 🔗 Related

- [../consumers/](../consumers/) - Data consumers feeding these agents
- [../main_*.py](../) - Pipeline entry points
- [../redis_cache.py](../redis_cache.py) - Redis caching utilities
