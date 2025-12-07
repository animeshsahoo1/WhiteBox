#!/usr/bin/env python3
"""
Bull-Bear Simple Evaluation with Toulmin Scoring
=================================================

A clean, minimal evaluation script that:
1. Takes 4 reports (news, sentiment, market, fundamental) from datasets
2. Runs Bull/Bear debate using Toulmin-structured prompts
3. Calculates proper metrics: Directional Accuracy, Toulmin Scores, Convergence

Usage:
    python run_eval_simple.py --max-scenarios 10 -v
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# Setup paths
EVAL_DIR = Path(__file__).parent
ROOT_DIR = EVAL_DIR.parent.parent.parent

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(EVAL_DIR / ".env")
except ImportError:
    pass

# Check for OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    print("❌ OpenAI not installed. Run: pip install openai")
    OPENAI_AVAILABLE = False


# ============================================================
# TOULMIN-STRUCTURED PROMPTS (Balanced for Accuracy)
# ============================================================

BULL_PROMPT = """You are analyzing {symbol} from a BULLISH perspective. Your job is to find the STRONGEST case for buying.

## DATA TO ANALYZE
NEWS: {news_report}
SENTIMENT: {sentiment_report}
MARKET: {market_report}
FUNDAMENTAL: {fundamental_report}

## OPPONENT'S ARGUMENT
{opponent_point}

## INSTRUCTIONS
Build your BEST bullish case using Toulmin argumentation:

1. **CLAIM**: State why investors should BUY. Include a specific upside target or % gain if data supports it.
2. **EVIDENCE**: List 3+ specific data points WITH NUMBERS from the reports above.
3. **WARRANT**: Explain the logical connection - WHY does this evidence mean BUY?
4. **QUALIFIER**: Be honest about your confidence (0.5-0.95). Lower if data is mixed.
5. **REBUTTAL**: Address the bear's main concern if any.

## OUTPUT (JSON):
{{
    "claim": "Investors should BUY {symbol} because [thesis with target]",
    "evidence": ["Data point 1 with number", "Data point 2", "Data point 3"],
    "warrant": "This evidence supports buying because...",
    "qualifier": "X% confident because [condition]",
    "rebuttal": "Regarding bear's concern, [response]",
    "confidence": 0.75
}}

NOTE: Only argue strongly if data genuinely supports it. Weak data = lower confidence."""


BEAR_PROMPT = """You are analyzing {symbol} from a BEARISH perspective. Your job is to find the STRONGEST case for selling/avoiding.

## DATA TO ANALYZE
NEWS: {news_report}
SENTIMENT: {sentiment_report}
MARKET: {market_report}
FUNDAMENTAL: {fundamental_report}

## OPPONENT'S ARGUMENT
{opponent_point}

## INSTRUCTIONS
Build your BEST bearish case using Toulmin argumentation:

1. **CLAIM**: State why investors should SELL or AVOID. Include downside target or % risk.
2. **EVIDENCE**: List 3+ specific RISKS WITH NUMBERS from the reports above.
3. **WARRANT**: Explain WHY this evidence means SELL - what's the causal mechanism?
4. **QUALIFIER**: Be honest about confidence (0.5-0.95). Lower if risks are speculative.
5. **REBUTTAL**: Address the bull's main claim directly.

## OUTPUT (JSON):
{{
    "claim": "Investors should SELL/AVOID {symbol} because [risk thesis]",
    "evidence": ["Risk 1 with data", "Risk 2 with metric", "Risk 3"],
    "warrant": "This evidence indicates sell because...",
    "qualifier": "X% confident because [trigger condition]",
    "rebuttal": "The bull's argument fails because...",
    "confidence": 0.75
}}

NOTE: Only argue strongly if risks are genuine and quantified. Speculative risks = lower confidence."""


FACILITATOR_PROMPT = """You are an OBJECTIVE Chief Investment Officer evaluating a debate about {symbol}.

## BULL'S CASE
{bull_points}

## BEAR'S CASE
{bear_points}

## YOUR ANALYSIS PROCESS

Step 1: Score each argument on Toulmin quality (1-5 scale):
- CLAIM CLARITY: Is it specific with a target price/percentage?
- EVIDENCE QUALITY: Are there 3+ concrete numbers from actual data?
- WARRANT STRENGTH: Is the logical reasoning sound and complete?
- QUALIFIER HONESTY: Does confidence match the evidence strength?
- REBUTTAL: Did they address the opponent's core point?

Step 2: Determine winner based on QUALITY of argumentation, not bias.

Step 3: Make recommendation based on who made the BETTER CASE:
- If Bull clearly has better evidence and logic → BUY
- If Bear clearly has better evidence and logic → SELL
- If scores are close (within 2 points) OR data is unclear → HOLD

## OUTPUT (JSON with INTEGER scores 1-5):
{{
    "bull_scores": {{
        "claim_clarity": 4,
        "evidence_quality": 3,
        "warrant_strength": 4,
        "qualifier_honesty": 3,
        "rebuttal_effectiveness": 3
    }},
    "bear_scores": {{
        "claim_clarity": 3,
        "evidence_quality": 4,
        "warrant_strength": 3,
        "qualifier_honesty": 4,
        "rebuttal_effectiveness": 3
    }},
    "bull_total": 17,
    "bear_total": 17,
    "winner": "TIE",
    "recommendation": "HOLD",
    "conviction": "LOW",
    "key_evidence": "Both sides had comparable evidence",
    "rationale": "Explain your scoring"
}}

NOTE: 
- Use ACTUAL INTEGER SCORES (1, 2, 3, 4, or 5), not "[1-5]"
- When data supports clear action, pick BUY or SELL
- HOLD is for genuinely unclear situations"""


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ToulminScores:
    claim_clarity: int = 0
    evidence_quality: int = 0
    warrant_strength: int = 0
    qualifier_honesty: int = 0
    rebuttal_effectiveness: int = 0
    
    @property
    def total(self) -> int:
        return sum([self.claim_clarity, self.evidence_quality, 
                   self.warrant_strength, self.qualifier_honesty, 
                   self.rebuttal_effectiveness])
    
    @property
    def normalized(self) -> float:
        return self.total / 25.0


@dataclass
class DebateResult:
    symbol: str
    bull_argument: Dict
    bear_argument: Dict
    facilitator_decision: Dict
    bull_toulmin: ToulminScores
    bear_toulmin: ToulminScores
    recommendation: str
    rounds: int
    execution_time: float


@dataclass
class ScenarioResult:
    dataset_id: str
    symbol: str
    category: str
    expected: str
    actual: str
    is_correct: bool
    bull_toulmin_score: float
    bear_toulmin_score: float
    avg_toulmin_score: float
    rounds: int
    execution_time: float
    winner: str = "TIE"  # BULL, BEAR, or TIE
    bull_confidence: float = 0.0
    bear_confidence: float = 0.0
    bull_evidence_count: int = 0
    bear_evidence_count: int = 0


@dataclass 
class Metrics:
    """Comprehensive metrics matching run_evaluation.py"""
    # Core accuracy
    total: int = 0
    correct: int = 0
    directional_accuracy: float = 0.0
    accuracy_by_category: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Toulmin scores
    avg_toulmin_bull: float = 0.0
    avg_toulmin_bear: float = 0.0
    avg_toulmin_overall: float = 0.0
    
    # Convergence
    avg_rounds: float = 0.0
    
    # Win/Loss tracking
    bull_wins: int = 0
    bear_wins: int = 0
    ties: int = 0
    
    # Elo ratings
    bull_elo: float = 1500.0
    bear_elo: float = 1500.0
    
    # Confidence analysis
    avg_bull_confidence: float = 0.0
    avg_bear_confidence: float = 0.0
    avg_confidence_gap: float = 0.0
    
    # Evidence density
    avg_bull_evidence_count: float = 0.0
    avg_bear_evidence_count: float = 0.0
    avg_evidence_per_point: float = 0.0


# ============================================================
# LLM CLIENT
# ============================================================

class LLMClient:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
        model = "google/gemini-2.5-flash-lite"
        
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        self.model = model
        print(f"  🔌 LLM: {model}")
    
    def complete_json(self, prompt: str, system: str = "Output valid JSON only.") -> Dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"  ⚠️ LLM error: {e}")
            return {}


# ============================================================
# DEBATE RUNNER
# ============================================================

class DebateRunner:
    def __init__(self, max_rounds: int = 2, verbose: bool = False):
        self.max_rounds = max_rounds
        self.verbose = verbose
        self.llm = LLMClient()
    
    def run(self, scenario: Dict) -> DebateResult:
        symbol = scenario.get("symbol", "TEST").upper()
        inputs = scenario.get("inputs", {})
        
        news = inputs.get("news_report", "")
        sentiment = inputs.get("sentiment_report", "")
        market = inputs.get("market_report", "")
        fundamental = inputs.get("fundamental_report", "")
        
        if self.verbose:
            print(f"\n  🏁 Starting debate for {symbol}")
        
        bull_points = []
        bear_points = []
        opponent_point = "None - you start the debate."
        
        # Run debate rounds
        for round_num in range(self.max_rounds):
            if self.verbose:
                print(f"    📍 Round {round_num + 1}")
            
            # Bull's turn
            bull_prompt = BULL_PROMPT.format(
                symbol=symbol,
                news_report=news[:1500],
                sentiment_report=sentiment[:1000],
                market_report=market[:1000],
                fundamental_report=fundamental[:1000],
                opponent_point=opponent_point
            )
            bull_response = self.llm.complete_json(bull_prompt, f"You are a bullish analyst for {symbol}.")
            bull_points.append(bull_response)
            opponent_point = bull_response.get("claim", "Bull argued to buy.")
            
            if self.verbose:
                claim = bull_response.get("claim", "")[:80]
                print(f"      🟢 BULL: {claim}...")
            
            # Bear's turn
            bear_prompt = BEAR_PROMPT.format(
                symbol=symbol,
                news_report=news[:1500],
                sentiment_report=sentiment[:1000],
                market_report=market[:1000],
                fundamental_report=fundamental[:1000],
                opponent_point=opponent_point
            )
            bear_response = self.llm.complete_json(bear_prompt, f"You are a bearish analyst for {symbol}.")
            bear_points.append(bear_response)
            opponent_point = bear_response.get("claim", "Bear argued to sell.")
            
            if self.verbose:
                claim = bear_response.get("claim", "")[:80]
                print(f"      🔴 BEAR: {claim}...")
        
        # Facilitator decision
        facilitator_prompt = FACILITATOR_PROMPT.format(
            symbol=symbol,
            bull_points=json.dumps(bull_points, indent=2),
            bear_points=json.dumps(bear_points, indent=2)
        )
        facilitator_response = self.llm.complete_json(
            facilitator_prompt, 
            "You are the Chief Investment Officer. Score arguments and decide."
        )
        
        # Extract Toulmin scores with safe int conversion
        bull_scores = facilitator_response.get("bull_scores", {})
        bear_scores = facilitator_response.get("bear_scores", {})
        
        def safe_int(val, default=3):
            """Safely convert value to int, handling lists and strings"""
            if isinstance(val, int):
                return val
            if isinstance(val, float):
                return int(val)
            if isinstance(val, list) and len(val) > 0:
                return safe_int(val[0], default)
            if isinstance(val, str):
                try:
                    return int(val.strip().replace("[", "").replace("]", ""))
                except:
                    return default
            return default
        
        bull_toulmin = ToulminScores(
            claim_clarity=safe_int(bull_scores.get("claim_clarity", 3)),
            evidence_quality=safe_int(bull_scores.get("evidence_quality", 3)),
            warrant_strength=safe_int(bull_scores.get("warrant_strength", 3)),
            qualifier_honesty=safe_int(bull_scores.get("qualifier_honesty", 3)),
            rebuttal_effectiveness=safe_int(bull_scores.get("rebuttal_effectiveness", 3))
        )
        
        bear_toulmin = ToulminScores(
            claim_clarity=safe_int(bear_scores.get("claim_clarity", 3)),
            evidence_quality=safe_int(bear_scores.get("evidence_quality", 3)),
            warrant_strength=safe_int(bear_scores.get("warrant_strength", 3)),
            qualifier_honesty=safe_int(bear_scores.get("qualifier_honesty", 3)),
            rebuttal_effectiveness=safe_int(bear_scores.get("rebuttal_effectiveness", 3))
        )
        
        recommendation = facilitator_response.get("recommendation", "HOLD").upper()
        
        if self.verbose:
            print(f"      👨‍⚖️ DECISION: {recommendation}")
            print(f"         Bull Toulmin: {bull_toulmin.total}/25 ({bull_toulmin.normalized:.0%})")
            print(f"         Bear Toulmin: {bear_toulmin.total}/25 ({bear_toulmin.normalized:.0%})")
        
        return DebateResult(
            symbol=symbol,
            bull_argument=bull_points[-1] if bull_points else {},
            bear_argument=bear_points[-1] if bear_points else {},
            facilitator_decision=facilitator_response,
            bull_toulmin=bull_toulmin,
            bear_toulmin=bear_toulmin,
            recommendation=recommendation,
            rounds=self.max_rounds,
            execution_time=0.0
        )


# ============================================================
# EVALUATION RUNNER
# ============================================================

class Evaluator:
    def __init__(self, max_rounds: int = 2, verbose: bool = False):
        self.runner = DebateRunner(max_rounds=max_rounds, verbose=verbose)
        self.verbose = verbose
    
    def load_datasets(self, path: Path) -> List[Dict]:
        datasets = []
        for f in path.rglob("*.json"):
            if f.name == "manifest.json":
                continue
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    datasets.append(data)
            except:
                pass
        return datasets
    
    def evaluate(self, datasets_dir: Path, max_scenarios: int = None) -> tuple:
        datasets = self.load_datasets(datasets_dir)
        if max_scenarios:
            datasets = datasets[:max_scenarios]
        
        print(f"\n📁 Loaded {len(datasets)} scenarios")
        print("=" * 60)
        
        results = []
        for i, scenario in enumerate(datasets, 1):
            dataset_id = scenario.get("dataset_id", f"scenario_{i}")
            symbol = scenario.get("symbol", "TEST").upper()
            category = scenario.get("category", "unknown")
            expected = scenario.get("ground_truth", {}).get("expected_recommendation", "HOLD").upper()
            
            print(f"\n[{i}/{len(datasets)}] {dataset_id} ({symbol})", end="", flush=True)
            
            start = time.time()
            try:
                result = self.runner.run(scenario)
                exec_time = time.time() - start
                
                actual = result.recommendation
                is_correct = actual == expected
                
                icon = "✅" if is_correct else "❌"
                print(f" {icon} Exp:{expected} Got:{actual} ({exec_time:.1f}s)")
                
                results.append(ScenarioResult(
                    dataset_id=dataset_id,
                    symbol=symbol,
                    category=category,
                    expected=expected,
                    actual=actual,
                    is_correct=is_correct,
                    bull_toulmin_score=result.bull_toulmin.normalized,
                    bear_toulmin_score=result.bear_toulmin.normalized,
                    avg_toulmin_score=(result.bull_toulmin.normalized + result.bear_toulmin.normalized) / 2,
                    rounds=result.rounds,
                    execution_time=exec_time,
                    winner=result.facilitator_decision.get("winner", "TIE"),
                    bull_confidence=result.bull_argument.get("confidence", 0.75),
                    bear_confidence=result.bear_argument.get("confidence", 0.75),
                    bull_evidence_count=len(result.bull_argument.get("evidence", [])),
                    bear_evidence_count=len(result.bear_argument.get("evidence", []))
                ))
                
            except Exception as e:
                print(f" ❌ Error: {e}")
                results.append(ScenarioResult(
                    dataset_id=dataset_id, symbol=symbol, category=category,
                    expected=expected, actual="ERROR", is_correct=False,
                    bull_toulmin_score=0, bear_toulmin_score=0, avg_toulmin_score=0,
                    rounds=0, execution_time=time.time() - start
                ))
        
        # Compute metrics
        metrics = self.compute_metrics(results)
        return results, metrics
    
    def compute_metrics(self, results: List[ScenarioResult]) -> Metrics:
        valid = [r for r in results if r.actual != "ERROR"]
        if not valid:
            return Metrics(total=len(results))
        
        m = Metrics(
            total=len(results),
            correct=sum(1 for r in valid if r.is_correct),
            directional_accuracy=sum(1 for r in valid if r.is_correct) / len(valid),
            avg_toulmin_bull=sum(r.bull_toulmin_score for r in valid) / len(valid),
            avg_toulmin_bear=sum(r.bear_toulmin_score for r in valid) / len(valid),
            avg_toulmin_overall=sum(r.avg_toulmin_score for r in valid) / len(valid),
            avg_rounds=sum(r.rounds for r in valid) / len(valid)
        )
        
        # By category
        by_cat = defaultdict(list)
        for r in valid:
            by_cat[r.category].append(r.is_correct)
        m.accuracy_by_category = {c: sum(v)/len(v) for c, v in by_cat.items()}
        
        # Confusion matrix
        conf = defaultdict(lambda: defaultdict(int))
        for r in valid:
            conf[r.expected][r.actual] += 1
        m.confusion_matrix = {k: dict(v) for k, v in conf.items()}
        
        # Win/Loss tracking
        for r in valid:
            if r.winner == "BULL":
                m.bull_wins += 1
            elif r.winner == "BEAR":
                m.bear_wins += 1
            else:
                m.ties += 1
        
        # Elo ratings calculation
        bull_elo, bear_elo = 1500.0, 1500.0
        K = 32  # K-factor
        for r in valid:
            if r.winner == "BULL":
                actual_bull, actual_bear = 1.0, 0.0
            elif r.winner == "BEAR":
                actual_bull, actual_bear = 0.0, 1.0
            else:
                actual_bull, actual_bear = 0.5, 0.5
            
            expected_bull = 1 / (1 + 10 ** ((bear_elo - bull_elo) / 400))
            expected_bear = 1 - expected_bull
            
            bull_elo += K * (actual_bull - expected_bull)
            bear_elo += K * (actual_bear - expected_bear)
        
        m.bull_elo = bull_elo
        m.bear_elo = bear_elo
        
        # Confidence analysis
        m.avg_bull_confidence = sum(r.bull_confidence for r in valid) / len(valid)
        m.avg_bear_confidence = sum(r.bear_confidence for r in valid) / len(valid)
        m.avg_confidence_gap = abs(m.avg_bull_confidence - m.avg_bear_confidence)
        
        # Evidence density
        m.avg_bull_evidence_count = sum(r.bull_evidence_count for r in valid) / len(valid)
        m.avg_bear_evidence_count = sum(r.bear_evidence_count for r in valid) / len(valid)
        m.avg_evidence_per_point = (m.avg_bull_evidence_count + m.avg_bear_evidence_count) / 2
        
        return m
    
    def print_report(self, m: Metrics):
        print(f"""
{'='*70}
📊 EVALUATION RESULTS
{'='*70}

┌────────────────────────────────────────────────────────────────────┐
│ 1. DIRECTIONAL ACCURACY: {m.directional_accuracy:.1%} ({m.correct}/{m.total})
├────────────────────────────────────────────────────────────────────┤
│ 2. TOULMIN SCORES (Argumentation Quality)
│    Bull Average:  {m.avg_toulmin_bull:.1%}
│    Bear Average:  {m.avg_toulmin_bear:.1%}
│    Overall:       {m.avg_toulmin_overall:.1%}
├────────────────────────────────────────────────────────────────────┤
│ 3. CONVERGENCE: {m.avg_rounds:.1f} rounds avg
├────────────────────────────────────────────────────────────────────┤
│ 4. WIN/LOSS RECORD
│    Bull Wins: {m.bull_wins}  |  Bear Wins: {m.bear_wins}  |  Ties: {m.ties}
├────────────────────────────────────────────────────────────────────┤
│ 5. ELO RATINGS (Starting: 1500)
│    Bull: {m.bull_elo:.0f}  |  Bear: {m.bear_elo:.0f}
├────────────────────────────────────────────────────────────────────┤
│ 6. EVIDENCE DENSITY
│    Bull: {m.avg_bull_evidence_count:.1f}/point  |  Bear: {m.avg_bear_evidence_count:.1f}/point
│    Average: {m.avg_evidence_per_point:.1f} evidence items/point
├────────────────────────────────────────────────────────────────────┤
│ 7. CONFIDENCE ANALYSIS
│    Bull Avg: {m.avg_bull_confidence:.1%}  |  Bear Avg: {m.avg_bear_confidence:.1%}
│    Gap: {m.avg_confidence_gap:.1%}
└────────────────────────────────────────────────────────────────────┘

ACCURACY BY CATEGORY:
{chr(10).join(f"  • {c}: {a:.1%}" for c, a in m.accuracy_by_category.items())}

CONFUSION MATRIX:
{chr(10).join(f"  {k}: {v}" for k, v in m.confusion_matrix.items())}
""")
    
    def save_results(self, results: List[ScenarioResult], metrics: Metrics, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        with open(output_dir / f"results_simple_{ts}.json", 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        
        with open(output_dir / f"metrics_simple_{ts}.json", 'w') as f:
            json.dump(asdict(metrics), f, indent=2)
        
        print(f"\n📄 Saved to {output_dir}/")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Simple Bull-Bear Evaluation with Toulmin Scoring")
    parser.add_argument("--datasets", default="datasets", help="Datasets directory")
    parser.add_argument("--max-scenarios", type=int, help="Limit scenarios")
    parser.add_argument("--max-rounds", type=int, default=2, help="Debate rounds")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--no-save", action="store_true", help="Skip saving")
    
    args = parser.parse_args()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set")
        return
    
    print("=" * 60)
    print("🚀 BULL-BEAR EVALUATION (Simple Toulmin)")
    print("=" * 60)
    
    evaluator = Evaluator(max_rounds=args.max_rounds, verbose=args.verbose)
    datasets_dir = EVAL_DIR / args.datasets
    
    if not datasets_dir.exists():
        print(f"❌ Datasets not found: {datasets_dir}")
        return
    
    results, metrics = evaluator.evaluate(datasets_dir, args.max_scenarios)
    
    if results:
        evaluator.print_report(metrics)
        if not args.no_save:
            evaluator.save_results(results, metrics, EVAL_DIR / args.output)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
