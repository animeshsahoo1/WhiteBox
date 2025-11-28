# Bull-Bear Debate System with Facilitator

This system implements a bull-bear debate workflow using LangGraph and Pathway, with automatic facilitator report generation.

## Architecture

```
┌─────────────────┐
│  Pathway API    │ ──→ Serves 4 reports (market, sentiment, news, fundamental)
└─────────────────┘
         ↓
┌─────────────────┐
│ bull_bear_main  │ ──→ FastAPI server that orchestrates the debate
└─────────────────┘
         ↓
┌─────────────────┐
│bull_bear_graph  │ ──→ LangGraph workflow (bull ↔ bear debate)
└─────────────────┘
         ↓
┌─────────────────┐
│debate_points.json│ ──→ Stores debate transcript and arguments
└─────────────────┘
         ↓
┌─────────────────┐
│facilitator_main │ ──→ Pathway streaming processor for summary
└─────────────────┘
         ↓
┌─────────────────┐
│facilitator_report│ ──→ Final summary markdown report
└─────────────────┘
```

## Files

### Core Files

1. **`bull_bear_graph.py`**
   - LangGraph implementation of bull-bear debate
   - Uses actual bull/bear researchers from `all_agents/researchers/`
   - Alternates between bull and bear arguments
   - Saves results to `debate_points.json`

2. **`bull_bear_main.py`**
   - FastAPI server with `/begin_debate` endpoint
   - Fetches 4 reports from Pathway API
   - Runs the LangGraph debate
   - Converts output to jsonlines format for facilitator

3. **`facilitator_main.py`**
   - Pathway streaming processor (follows `news_agent.py` pattern)
   - Reads from `debate_points.jsonl`
   - Uses LLM to generate balanced summary
   - Saves to `reports/{symbol}/facilitator_report.md`

### Output Files

- **`debate_points.json`** - Full debate transcript and metadata
- **`debate_points.jsonl`** - JSONL format for Pathway streaming
- **`reports/{SYMBOL}/facilitator_report.md`** - Facilitator summary report

## Workflow

### Step 1: Start the Pathway API (reports source)

```bash
cd pathway
python main_news.py  # or docker-compose up
```

This should run on `http://localhost:8000` and provide:
- `/reports/{symbol}` endpoint with 4 reports

### Step 2: Start the Bull-Bear API

```bash
cd bullbear
pip install -r requirements.txt
python bull_bear_main.py
```

Runs on `http://localhost:8001`

### Step 3: Trigger a Debate

```bash
curl -X POST http://localhost:8001/begin_debate \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "max_rounds": 2}'
```

This will:
1. Fetch 4 reports from Pathway API
2. Run bull-bear debate using LangGraph
3. Save debate to `debate_points.json`
4. Convert to `debate_points.jsonl`

### Step 4: Generate Facilitator Report

```bash
python facilitator_main.py
```

This will:
1. Read from `debate_points.jsonl`
2. Process through Pathway streaming pipeline
3. Use LLM to generate balanced summary
4. Save to `reports/AAPL/facilitator_report.md`

## Environment Variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key
PATHWAY_API_URL=http://localhost:8000
```

## Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:
- `langgraph` - Graph orchestration
- `pathway` - Streaming data processing
- `fastapi` - API server
- `httpx` - HTTP client
- `python-dotenv` - Environment variables

## Testing

Run the test workflow:

```bash
python test_workflow.py
```

This creates mock debate data and tests the facilitator report generation.

## Agent Configuration

The bull and bear researchers:
- Use **Pathway LiteLLMChat** for LLM calls
- Access **A-Mem** (AgenticMemorySystem) for historical context
- Can call **`retrieve_from_pathway()`** tool for evidence
- Use **strict JSON output format** for structured responses

## Report Structure

### Debate Points JSON
```json
{
  "symbol": "AAPL",
  "timestamp": "2025-11-18T10:30:00",
  "rounds_completed": 2,
  "total_exchanges": 4,
  "bull_history": "...",
  "bear_history": "...",
  "full_debate_transcript": "...",
  "summary": {...}
}
```

### Facilitator Report Sections
1. Executive Summary
2. Recent Debate Overview
3. Key Arguments (Bull & Bear)
4. Consensus & Divergence Points
5. Facilitator's Assessment (with BUY/SELL/HOLD)
6. Risk Considerations
7. Action Items

## Notes

- The facilitator uses **Pathway's streaming pattern** (like news_agent)
- Reports are **incremental** - new debates update existing reports
- The system is **symbol-aware** - one report per symbol
- All LLM calls use **OpenRouter** with GPT-4o-mini

## Troubleshooting

**Problem**: Pathway API not responding
- Check if `main_news.py` is running
- Verify port 8000 is available

**Problem**: No debate data found
- Ensure `debate_points.json` exists
- Check if `begin_debate` completed successfully

**Problem**: LLM not responding
- Verify `OPENAI_API_KEY` in `.env`
- Check OpenRouter API status
