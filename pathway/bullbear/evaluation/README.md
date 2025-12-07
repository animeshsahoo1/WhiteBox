# Bull-Bear Debate Evaluation

This folder contains tools to generate evaluation datasets and benchmark the Bull-Bear debate system.

## Files

| File | Description |
|------|-------------|
| `run_evaluation.py` | Main evaluation script - runs debates and measures accuracy |
| `generate_dataset.py` | Generates test scenarios using OpenRouter API |
| `datasets/` | Generated evaluation scenarios (JSON files) |
| `results/` | Evaluation results and metrics |
| `.env` | API keys (OPENAI_API_KEY for OpenRouter) |

## Quick Start

### 1. Generate Dataset
```bash
# Generate 3 scenarios per category (15 total)
python generate_dataset.py --count 3 --category all
```

### 2. Run Evaluation
```bash
# Run with 2 debate rounds
python run_evaluation.py --max-scenarios 15 --max-rounds 2
```

## Categories

| Category | Description | Expected Outcome |
|----------|-------------|------------------|
| `clear_buy` | Strong bullish scenarios | BUY recommendation |
| `clear_sell` | Strong bearish scenarios | SELL recommendation |
| `clear_hold` | Balanced/stable scenarios | HOLD recommendation |
| `ambiguous` | Mixed signals | HOLD (uncertainty) |
| `adversarial` | Misleading/tricky data | Varies |

## Key Features

### Asian Parliamentary Debate Format
- **Normal rounds**: Bull speaks first, Bear second
- **Final round**: Order REVERSED - Bear first, Bull gets closing argument
- This balances the debate by giving both sides equal opportunity

### Toulmin Argumentation Scoring
Each argument is scored on 5 criteria (1-5 each, max 25):
1. Claim Clarity
2. Evidence Quality
3. Warrant Strength
4. Qualifier Honesty
5. Rebuttal Effectiveness

### Decision Rules
- Bull wins by 2+ points → **BUY**
- Bear wins by 2+ points → **SELL**
- Within 2 points → **HOLD**

## Metrics Reported

- **Directional Accuracy**: % of correct BUY/SELL/HOLD predictions
- **Toulmin Scores**: Argumentation quality (Bull vs Bear)
- **Win/Loss Record**: Bull wins, Bear wins, Ties
- **Elo Ratings**: Relative strength of Bull vs Bear
- **Confusion Matrix**: Breakdown of predictions vs expected

## Example Output

```
DIRECTIONAL ACCURACY: 73.3% (11/15)

BY CATEGORY:
  • clear_buy:   100.0% ✅
  • clear_sell:  100.0% ✅
  • clear_hold:   66.7%
  • adversarial:  66.7%
  • ambiguous:    33.3%

WIN/LOSS:
  Bull Wins: 6  |  Bear Wins: 5  |  Ties: 4
```

## Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install openai

# Set API key in .env
echo "OPENAI_API_KEY=your_openrouter_key" > .env
```
