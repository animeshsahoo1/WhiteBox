# Galileo Agent Evaluation Framework

This folder contains the evaluation framework for testing the multi-agent trading system using Galileo observability platform.

## Overview

The evaluation framework tests 64 queries across 27 MCP (Model Context Protocol) tools, categorized into three difficulty levels:

| Difficulty | Description | Example |
|------------|-------------|---------|
| **Easy** | Single-tool invocation with direct mappings | "Get sentiment for AAPL" |
| **Medium** | 2-3 tool orchestrations or parameter extraction | "Compare news and market reports for Apple" |
| **Difficult** | Multi-step reasoning, tool chaining, and synthesis | "Build a complete trading plan: analyze sentiment, create a strategy, and recommend entry/exit points" |

## Files

| File | Description |
|------|-------------|
| `run_evaluation.py` | Main evaluation script - runs all 64 test queries and generates metrics |
| `galileo_agent_eval.py` | Core evaluation framework - defines AgentTrace, ToolCall, metrics calculation |

## Prerequisites

### 1. Install Dependencies

```bash
pip install galileo tiktoken requests python-dotenv
```

### 2. Environment Variables

Create a `.env` file in the project root with:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key

# Optional - defaults shown
API_BASE_URL=http://localhost:8000
OPENAI_API_BASE=https://openrouter.ai/api/v1
EVAL_MODEL=google/gemini-2.0-flash-001
GALILEO_PROJECT=stock-trading-agent
GALILEO_API_KEY=your-galileo-api-key  # Optional for dashboard logging
```

### 3. Start the Trading System

Make sure the unified API and all required services are running:

```bash
cd pathway
docker-compose up -d unified-api
```

Verify the API is accessible:
```bash
curl http://localhost:8000/health
```

## Running the Evaluation

### Full Evaluation (64 queries)

```bash
cd validation/galileo_eval
python run_evaluation.py
```

This will:
1. Run all 64 test queries against the agent
2. Track tool selection accuracy, errors, and completion rates
3. Save results to `eval_results.json`
4. Print a summary with aggregate metrics

### Expected Output

```
╔═══════════════════════════════════════════════════════════════╗
║     Galileo Agent Evaluation - Stock Trading Assistant        ║
╚═══════════════════════════════════════════════════════════════╝

Running 64 evaluation queries...

[1/64] sentiment_easy: What is the current sentiment for AAPL?
   ✅ Success | Tools: ['get_symbol_sentiment'] | Time: 2.3s

[2/64] sentiment_easy: Get the sentiment report for Apple stock
   ✅ Success | Tools: ['get_sentiment_report'] | Time: 3.1s
...

════════════════════════════════════════════════════════════════
                    EVALUATION SUMMARY
════════════════════════════════════════════════════════════════

Total Tests: 64
Successful: 64 (100.0%)
Failed: 0

Average Metrics:
  - Tool Selection Score: 0.88 (88%)
  - Action Completion: 0.76 (76%)
  - Total Tool Errors: 12

Results saved to: eval_results.json
```

## Metrics Explained

| Metric | Description |
|--------|-------------|
| **Tool Selection Score** | F1 score comparing expected vs actual tools used |
| **Tool Errors** | Count of failed tool invocations |
| **Action Completion** | Whether the task was fully completed (0-1) |
| **Latency** | Time taken per query in seconds |

## Test Categories

The 64 queries cover these categories:

1. **Sentiment Analysis** - get_symbol_sentiment, get_market_sentiment, get_sentiment_report
2. **Report Retrieval** - get_fundamental_report, get_market_report, get_news_report, get_all_reports
3. **Strategy Management** - create_strategy, list_all_strategies, search_strategies, get_strategy_details
4. **Risk Assessment** - assess_single_risk_tier, assess_risk_all_tiers
5. **Knowledge Base** - query_knowledge_base, ingest_text_to_kb, list_kb_files
6. **Historical Analysis** - run_historical_analysis
7. **Bull/Bear Debate** - run_bull_bear_debate, get_debate_status, get_facilitator_report
8. **Combined/Complex** - Multi-tool queries requiring reasoning and synthesis

## Customizing Tests

To add or modify test queries, edit the `TEST_QUERIES` list in `run_evaluation.py`:

```python
TEST_QUERIES = [
    {
        "query": "Your test query here",
        "category": "category_difficulty",
        "difficulty": "easy|medium|complex",
        "expected_tools": ["tool1", "tool2"]
    },
    ...
]
```

## Troubleshooting

### API Connection Error
```
Error: Connection refused to http://localhost:8000
```
**Solution**: Ensure the unified-api container is running:
```bash
docker-compose up -d unified-api
docker logs pathway-unified-api
```

### Missing Environment Variables
```
Error: OPENAI_API_KEY not set
```
**Solution**: Create `.env` file with required variables (see Prerequisites)

### Timeout Errors
Some complex queries (especially `run_historical_analysis`) may take 30+ seconds. The default timeout is 120 seconds per query.
