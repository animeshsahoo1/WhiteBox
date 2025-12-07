"""
Bull-Bear Dataset Generator
===========================

This script helps you create evaluation datasets for the Bull-Bear debate system.
You can either:
1. Manually create scenarios using the template
2. Use the LLM prompt to bulk-generate scenarios
3. Run this script to validate your datasets

Usage:
    python generate_dataset.py --create-example
    python generate_dataset.py --validate datasets/
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# ============================================================
# TEMPLATES - Copy these and fill in the blanks
# ============================================================

NEWS_REPORT_TEMPLATE = """# News Summary for {symbol}

## Latest Headlines

1. **{headline_1}** - {source_1}, {date_1}
   {summary_1}

2. **{headline_2}** - {source_2}, {date_2}
   {summary_2}

3. **{headline_3}** - {source_3}, {date_3}
   {summary_3}

## Key Events
- {event_1}
- {event_2}

## Analyst Actions
- {analyst_action_1}
- {analyst_action_2}

Last Updated: {timestamp}
"""

SENTIMENT_REPORT_TEMPLATE = """# Sentiment Analysis for {symbol}

## Overall Sentiment: {overall_sentiment} (Score: {sentiment_score}/10)

### Social Media Metrics
- Twitter: {twitter_positive}% Positive, {twitter_neutral}% Neutral, {twitter_negative}% Negative
- Reddit: {reddit_sentiment}, {reddit_mentions} mentions
- StockTwits: {stocktwits_messages} messages, {stocktwits_sentiment}

### Analyst Sentiment
- Buy ratings: {buy_ratings}
- Hold ratings: {hold_ratings}
- Sell ratings: {sell_ratings}
- Average Price Target: ${avg_price_target}

### Key Themes
- {theme_1}
- {theme_2}
- {theme_3}

Last Updated: {timestamp}
"""

MARKET_REPORT_TEMPLATE = """# Technical Analysis for {symbol}

## Price Action
- Current Price: ${current_price}
- 24h Change: {price_change_24h}%
- 52-Week Range: ${week_52_low} - ${week_52_high}
- Volume: {volume} ({volume_vs_avg})

## Technical Indicators
- RSI (14): {rsi} ({rsi_interpretation})
- MACD: {macd_status}
- 50-Day MA: ${ma_50} (price {ma_50_relation})
- 200-Day MA: ${ma_200} (price {ma_200_relation})

## Support/Resistance
- Support: ${support_1}, ${support_2}
- Resistance: ${resistance_1}, ${resistance_2}

## Trend Analysis
{trend_analysis}

Last Updated: {timestamp}
"""

FUNDAMENTAL_REPORT_TEMPLATE = """# Fundamental Analysis for {symbol}

## Valuation Metrics
- P/E Ratio: {pe_ratio} (Industry avg: {industry_pe})
- Forward P/E: {forward_pe}
- P/S Ratio: {ps_ratio}
- EV/EBITDA: {ev_ebitda}

## Financial Health
- Revenue (TTM): ${revenue} ({revenue_growth} YoY)
- Net Income: ${net_income} ({income_growth} YoY)
- Free Cash Flow: ${fcf}
- Debt/Equity: {debt_equity}
- Current Ratio: {current_ratio}

## Growth Metrics
- Revenue Growth (3Y CAGR): {revenue_cagr}%
- EPS Growth (3Y CAGR): {eps_cagr}%

## Competitive Position
{competitive_position}

Last Updated: {timestamp}
"""

# ============================================================
# SCENARIO TEMPLATE
# ============================================================

SCENARIO_TEMPLATE = {
    "dataset_id": "",           # e.g., "strong_buy_001"
    "scenario_name": "",        # e.g., "Massive Earnings Beat"
    "category": "",             # e.g., "clear_signals" or "ambiguous" or "adversarial"
    "difficulty": "",           # "easy", "medium", "hard"
    
    "symbol": "",               # e.g., "AAPL"
    "company_name": "",         # e.g., "Apple Inc."
    "sector": "",               # e.g., "Technology"
    
    "inputs": {
        "news_report": "",
        "sentiment_report": "",
        "market_report": "",
        "fundamental_report": ""
    },
    
    "ground_truth": {
        "expected_recommendation": "",  # "BUY", "HOLD", or "SELL"
        "expected_confidence": "",      # "HIGH", "MEDIUM", "LOW"
        "reasoning": "",                # Why this is the right answer
        "key_bull_points": [],          # What Bull SHOULD argue
        "key_bear_points": []           # What Bear SHOULD argue
    }
}

# ============================================================
# EXAMPLE SCENARIOS (Copy and modify these)
# ============================================================

EXAMPLE_STRONG_BUY = {
    "dataset_id": "strong_buy_001",
    "scenario_name": "Massive Earnings Beat with Guidance Raise",
    "category": "clear_signals",
    "difficulty": "easy",
    
    "symbol": "TECH",
    "company_name": "TechCorp Inc.",
    "sector": "Technology",
    
    "inputs": {
        "news_report": """# News Summary for TECH

## Latest Headlines

1. **TechCorp Crushes Q4 Earnings: EPS $3.50 vs $2.80 Expected** - Bloomberg, Dec 6
   The company reported earnings 25% above analyst expectations, driven by strong cloud services growth. Management raised full-year guidance by 15%.

2. **Three Major Analysts Upgrade TechCorp to Strong Buy** - Reuters, Dec 6
   Morgan Stanley, Goldman Sachs, and JP Morgan all upgraded the stock following earnings, with price targets ranging from $220-$250.

3. **TechCorp Announces $10B Buyback Program** - PR Newswire, Dec 6
   The board approved a new share repurchase authorization, representing 8% of market cap.

## Key Events
- Dec 6, 8AM: Q4 earnings released, beat on all metrics
- Dec 6, 10AM: Earnings call with bullish guidance commentary

## Analyst Actions
- Morgan Stanley: Upgrade to Overweight, PT $250 (from $180)
- Goldman Sachs: Upgrade to Buy, PT $240 (from $185)
- JP Morgan: Upgrade to Overweight, PT $220 (from $175)

Last Updated: 2024-12-06T14:00:00Z""",

        "sentiment_report": """# Sentiment Analysis for TECH

## Overall Sentiment: VERY BULLISH (Score: 9.2/10)

### Social Media Metrics
- Twitter: 88% Positive, 8% Neutral, 4% Negative
- Reddit: Extremely Bullish, 5,200 mentions in last 24h
- StockTwits: 3,400 messages, 92% bullish

### Analyst Sentiment
- Buy ratings: 28 (up from 20 yesterday)
- Hold ratings: 5
- Sell ratings: 0
- Average Price Target: $235 (up from $188)

### Key Themes
- Earnings beat celebration
- Cloud growth acceleration
- Buyback announcement enthusiasm

Last Updated: 2024-12-06T14:00:00Z""",

        "market_report": """# Technical Analysis for TECH

## Price Action
- Current Price: $195.50
- 24h Change: +12.5%
- 52-Week Range: $125.00 - $198.00 (near 52-week high)
- Volume: 85M (4x average)

## Technical Indicators
- RSI (14): 72 (Overbought but strong)
- MACD: Strong bullish crossover, widening
- 50-Day MA: $168.50 (price 16% above)
- 200-Day MA: $155.20 (price 26% above)

## Support/Resistance
- Support: $180, $168
- Resistance: $198 (52-week high), $210 (target)

## Trend Analysis
The stock is in a strong uptrend, breaking out to new highs on massive volume. The gap up on earnings creates a new support zone around $180.

Last Updated: 2024-12-06T14:00:00Z""",

        "fundamental_report": """# Fundamental Analysis for TECH

## Valuation Metrics
- P/E Ratio: 24.5 (Industry avg: 28.0)
- Forward P/E: 20.2 (below peers)
- P/S Ratio: 6.8
- EV/EBITDA: 18.5

## Financial Health
- Revenue (TTM): $125B (+18% YoY)
- Net Income: $28B (+25% YoY)
- Free Cash Flow: $32B
- Debt/Equity: 0.45
- Current Ratio: 1.8

## Growth Metrics
- Revenue Growth (3Y CAGR): 15.5%
- EPS Growth (3Y CAGR): 22.0%

## Competitive Position
Market leader in cloud services with 35% market share. Strong moat from enterprise relationships and switching costs. R&D spending of $15B annually maintains technology lead.

Last Updated: 2024-12-06T14:00:00Z"""
    },
    
    "ground_truth": {
        "expected_recommendation": "BUY",
        "expected_confidence": "HIGH",
        "reasoning": "Massive earnings beat, guidance raise, multiple analyst upgrades, buyback announcement, strong technicals, and reasonable valuation create a clear buy case.",
        "key_bull_points": [
            "Earnings beat by 25% shows execution excellence",
            "Guidance raise signals management confidence",
            "Triple analyst upgrade is rare consensus",
            "Buyback provides downside support",
            "Forward P/E below industry average despite growth"
        ],
        "key_bear_points": [
            "RSI at 72 suggests short-term overbought",
            "Gap up may see profit-taking",
            "High expectations now priced in"
        ]
    }
}


EXAMPLE_STRONG_SELL = {
    "dataset_id": "strong_sell_001",
    "scenario_name": "Fraud Investigation and Earnings Miss",
    "category": "clear_signals",
    "difficulty": "easy",
    
    "symbol": "FRAUD",
    "company_name": "FraudCorp Holdings",
    "sector": "Finance",
    
    "inputs": {
        "news_report": """# News Summary for FRAUD

## Latest Headlines

1. **SEC Opens Formal Investigation into FraudCorp Accounting** - WSJ, Dec 6
   The Securities and Exchange Commission has launched a formal investigation into the company's revenue recognition practices. The CFO resigned effective immediately.

2. **FraudCorp Misses Earnings by 40%, Withdraws Guidance** - Bloomberg, Dec 6
   The company reported EPS of $0.60 vs $1.00 expected. Management withdrew full-year guidance citing "accounting review."

3. **Short Seller Releases 100-Page Report Alleging Fraud** - CNBC, Dec 5
   Hindenburg Research published a detailed report alleging systematic revenue fabrication going back 3 years.

## Key Events
- Dec 6, 6AM: CFO resignation announced
- Dec 6, 8AM: Earnings miss with no guidance
- Dec 6, 10AM: SEC investigation confirmed

## Analyst Actions
- All 15 covering analysts suspended ratings pending review
- Average PT withdrawn

Last Updated: 2024-12-06T14:00:00Z""",

        "sentiment_report": """# Sentiment Analysis for FRAUD

## Overall Sentiment: EXTREMELY BEARISH (Score: 1.5/10)

### Social Media Metrics
- Twitter: 5% Positive, 10% Neutral, 85% Negative
- Reddit: Panic selling discussion, 12,000 mentions
- StockTwits: 8,500 messages, 95% bearish

### Analyst Sentiment
- Buy ratings: 0 (all suspended)
- Hold ratings: 0
- Sell ratings: 0
- Average Price Target: Suspended

### Key Themes
- Fraud allegations dominating discussion
- CFO resignation seen as admission
- Comparisons to Enron and Wirecard

Last Updated: 2024-12-06T14:00:00Z""",

        "market_report": """# Technical Analysis for FRAUD

## Price Action
- Current Price: $12.50
- 24h Change: -55%
- 52-Week Range: $8.00 - $45.00
- Volume: 200M (50x average)

## Technical Indicators
- RSI (14): 8 (Extremely Oversold)
- MACD: Crashed through signal line
- 50-Day MA: $38.50 (price 67% below)
- 200-Day MA: $35.20 (price 64% below)

## Support/Resistance
- Support: $8.00 (52-week low), $5.00 (2020 low)
- Resistance: $20, $25

## Trend Analysis
Complete technical breakdown. Stock is in freefall with no visible support. The gap down has created a massive overhead supply. Any bounce likely to be sold.

Last Updated: 2024-12-06T14:00:00Z""",

        "fundamental_report": """# Fundamental Analysis for FRAUD

## Valuation Metrics
- P/E Ratio: N/A (earnings now questionable)
- Forward P/E: N/A (guidance withdrawn)
- P/S Ratio: 0.8
- EV/EBITDA: N/A

## Financial Health
- Revenue (TTM): $5B (now under investigation)
- Net Income: Unknown (restating)
- Free Cash Flow: -$500M
- Debt/Equity: 4.5 (highly leveraged)
- Current Ratio: 0.6 (liquidity concerns)

## Growth Metrics
- Revenue Growth: Under review
- EPS Growth: Under review

## Competitive Position
Previously reported market share now being investigated. Multiple lawsuits from customers alleging misrepresentation.

Last Updated: 2024-12-06T14:00:00Z"""
    },
    
    "ground_truth": {
        "expected_recommendation": "SELL",
        "expected_confidence": "HIGH",
        "reasoning": "SEC investigation, CFO resignation, massive earnings miss, withdrawn guidance, fraud allegations, and complete technical breakdown make this an obvious sell.",
        "key_bull_points": [
            "RSI at 8 suggests extremely oversold bounce possible",
            "If fraud allegations unfounded, stock heavily discounted"
        ],
        "key_bear_points": [
            "SEC investigation rarely ends well for investors",
            "CFO resignation suggests internal awareness of issues",
            "40% earnings miss shows real business problems",
            "Withdrawn guidance means no visibility",
            "Debt/equity of 4.5 creates bankruptcy risk"
        ]
    }
}


EXAMPLE_AMBIGUOUS = {
    "dataset_id": "ambiguous_001",
    "scenario_name": "Sentiment vs Valuation Conflict",
    "category": "ambiguous",
    "difficulty": "hard",
    
    "symbol": "HYPE",
    "company_name": "HypeTech AI",
    "sector": "Technology",
    
    "inputs": {
        "news_report": """# News Summary for HYPE

## Latest Headlines

1. **HypeTech AI Stock Triples in 2024 on AI Excitement** - Reuters, Dec 6
   The stock has risen 200% YTD as investors pile into AI-related names. The company's AI assistant product has gained 50M users.

2. **CEO Featured on Magazine Cover as "AI Visionary"** - Forbes, Dec 5
   Growing media attention has fueled retail investor interest.

3. **No New Product Announcements at Developer Conference** - TechCrunch, Dec 4
   The company's annual conference focused on existing products, disappointing some who expected new AI features.

## Key Events
- Stock up 200% YTD
- 50M users on AI product (up from 20M in Jan)

## Analyst Actions
- Mixed: 10 Buy, 8 Hold, 5 Sell
- Price targets range from $50 to $200

Last Updated: 2024-12-06T14:00:00Z""",

        "sentiment_report": """# Sentiment Analysis for HYPE

## Overall Sentiment: BULLISH (Score: 7.8/10)

### Social Media Metrics
- Twitter: 75% Positive, 15% Neutral, 10% Negative
- Reddit: Heavily bullish, 8,000 mentions
- StockTwits: 4,200 messages, 80% bullish

### Analyst Sentiment
- Buy ratings: 10
- Hold ratings: 8
- Sell ratings: 5
- Average Price Target: $140 (stock at $150)

### Key Themes
- AI hype driving enthusiasm
- Comparisons to Nvidia early days
- Some valuation concerns emerging

Last Updated: 2024-12-06T14:00:00Z""",

        "market_report": """# Technical Analysis for HYPE

## Price Action
- Current Price: $150.00
- 24h Change: +2.5%
- 52-Week Range: $48.00 - $165.00
- Volume: 25M (1.5x average)

## Technical Indicators
- RSI (14): 68 (Near Overbought)
- MACD: Bullish but momentum slowing
- 50-Day MA: $135.00 (price 11% above)
- 200-Day MA: $95.00 (price 58% above)

## Support/Resistance
- Support: $135, $120
- Resistance: $165 (52-week high)

## Trend Analysis
Stock is extended from moving averages but holding uptrend. Momentum indicators showing fatigue but no breakdown yet.

Last Updated: 2024-12-06T14:00:00Z""",

        "fundamental_report": """# Fundamental Analysis for HYPE

## Valuation Metrics
- P/E Ratio: 150 (Industry avg: 35)
- Forward P/E: 85
- P/S Ratio: 45
- EV/EBITDA: 120

## Financial Health
- Revenue (TTM): $2B (+60% YoY)
- Net Income: $200M (+40% YoY)
- Free Cash Flow: $300M
- Debt/Equity: 0.2
- Current Ratio: 2.5

## Growth Metrics
- Revenue Growth (3Y CAGR): 55%
- EPS Growth (3Y CAGR): 45%

## Competitive Position
Strong product with 50M users but facing increasing competition from Google, Microsoft, and OpenAI. First mover advantage but moat uncertain.

Last Updated: 2024-12-06T14:00:00Z"""
    },
    
    "ground_truth": {
        "expected_recommendation": "HOLD",
        "expected_confidence": "MEDIUM",
        "reasoning": "Stock is above average analyst PT, extreme valuation (P/E 150), but strong growth (60% revenue) creates genuine debate. Neither strong buy nor sell.",
        "key_bull_points": [
            "60% revenue growth is exceptional",
            "50M users shows product-market fit",
            "Low debt and strong cash flow",
            "AI megatrend tailwind"
        ],
        "key_bear_points": [
            "P/E of 150 is extreme even for growth",
            "Stock above average analyst PT",
            "No new product announcements disappointing",
            "Competition intensifying from big tech",
            "Extended 58% above 200-day MA"
        ]
    }
}


def create_example_dataset():
    """Create example dataset files"""
    base_dir = Path(__file__).parent / "datasets"
    
    # Create directories
    (base_dir / "clear_signals").mkdir(parents=True, exist_ok=True)
    (base_dir / "ambiguous").mkdir(parents=True, exist_ok=True)
    (base_dir / "adversarial").mkdir(parents=True, exist_ok=True)
    
    # Save examples
    examples = [
        ("clear_signals/strong_buy_001.json", EXAMPLE_STRONG_BUY),
        ("clear_signals/strong_sell_001.json", EXAMPLE_STRONG_SELL),
        ("ambiguous/ambiguous_001.json", EXAMPLE_AMBIGUOUS),
    ]
    
    for filename, data in examples:
        filepath = base_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Created: {filepath}")
    
    # Create manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "total_scenarios": len(examples),
        "scenarios": [e[0] for e in examples]
    }
    with open(base_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n📁 Dataset structure created at: {base_dir}")
    print("📝 Modify these examples or use the LLM prompt to generate more!")


def validate_scenario(scenario: Dict) -> List[str]:
    """Validate a scenario has all required fields"""
    errors = []
    
    required_fields = ["dataset_id", "scenario_name", "symbol", "inputs", "ground_truth"]
    for field in required_fields:
        if field not in scenario:
            errors.append(f"Missing required field: {field}")
    
    if "inputs" in scenario:
        for report in ["news_report", "sentiment_report", "market_report", "fundamental_report"]:
            if report not in scenario["inputs"]:
                errors.append(f"Missing input: {report}")
            elif len(scenario["inputs"].get(report, "")) < 100:
                errors.append(f"Input {report} seems too short (< 100 chars)")
    
    if "ground_truth" in scenario:
        if "expected_recommendation" not in scenario["ground_truth"]:
            errors.append("Missing ground_truth.expected_recommendation")
        elif scenario["ground_truth"]["expected_recommendation"] not in ["BUY", "HOLD", "SELL"]:
            errors.append("expected_recommendation must be BUY, HOLD, or SELL")
    
    return errors


def validate_dataset_folder(folder_path: str):
    """Validate all JSON files in a folder"""
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ Folder not found: {folder}")
        return
    
    total = 0
    valid = 0
    
    for json_file in folder.rglob("*.json"):
        if json_file.name == "manifest.json":
            continue
        
        total += 1
        try:
            with open(json_file, 'r') as f:
                scenario = json.load(f)
            
            errors = validate_scenario(scenario)
            if errors:
                print(f"❌ {json_file.name}:")
                for e in errors:
                    print(f"   - {e}")
            else:
                print(f"✅ {json_file.name}")
                valid += 1
        except json.JSONDecodeError as e:
            print(f"❌ {json_file.name}: Invalid JSON - {e}")
    
    print(f"\n📊 Validated {valid}/{total} scenarios successfully")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python generate_dataset.py --create-example   # Create example datasets")
        print("  python generate_dataset.py --validate <path>  # Validate datasets")
        sys.exit(1)
    
    if sys.argv[1] == "--create-example":
        create_example_dataset()
    elif sys.argv[1] == "--validate" and len(sys.argv) > 2:
        validate_dataset_folder(sys.argv[2])
    else:
        print("Unknown command. Use --create-example or --validate <path>")
