#!/usr/bin/env python3
"""
Bull-Bear Debate Benchmark (Original 73% Accuracy Version)
===========================================================

Replicates the original evaluation that achieved 73.3% accuracy.

Usage:
    python benchmark.py --parallel 15
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    print("❌ Error: openai package not installed")
    sys.exit(1)


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class DebateQualityMetrics:
    cogency: float = 0.0
    persuasiveness_bull: float = 0.0
    persuasiveness_bear: float = 0.0
    civility: float = 0.0
    convergence: float = 0.0
    evidence_novelty: float = 0.0


@dataclass 
class ScenarioResult:
    dataset_id: str
    symbol: str
    category: str
    expected: str
    actual: str
    is_correct: bool
    bull_toulmin_score: float = 0.0
    bear_toulmin_score: float = 0.0
    avg_toulmin_score: float = 0.0
    rounds: int = 0
    execution_time: float = 0.0
    winner: str = "TIE"
    bull_confidence: float = 0.0
    bear_confidence: float = 0.0
    bull_evidence_count: int = 0
    bear_evidence_count: int = 0
    quality: DebateQualityMetrics = field(default_factory=DebateQualityMetrics)


@dataclass
class BenchmarkResults:
    total: int = 0
    correct: int = 0
    directional_accuracy: float = 0.0
    accuracy_by_category: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    avg_toulmin_bull: float = 0.0
    avg_toulmin_bear: float = 0.0
    avg_toulmin_overall: float = 0.0
    avg_rounds: float = 0.0
    bull_wins: int = 0
    bear_wins: int = 0
    ties: int = 0
    bull_elo: float = 1500.0
    bear_elo: float = 1500.0
    avg_bull_confidence: float = 0.0
    avg_bear_confidence: float = 0.0
    avg_confidence_gap: float = 0.0
    avg_bull_evidence_count: float = 0.0
    avg_bear_evidence_count: float = 0.0
    avg_evidence_per_point: float = 0.0
    avg_cogency: float = 0.0
    avg_persuasiveness_bull: float = 0.0
    avg_persuasiveness_bear: float = 0.0
    avg_civility: float = 0.0
    avg_convergence: float = 0.0
    avg_evidence_novelty: float = 0.0
    scenarios: List[ScenarioResult] = field(default_factory=list)


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)
        self.model = model
    
    def complete(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content


# ============================================================
# ORIGINAL PROMPTS (from run_eval_simple.py that got 73.3%)
# ============================================================

BULL_PROMPT = """You are a BULLISH investment analyst presenting a STRONG CASE TO BUY {symbol}.

## YOUR OBJECTIVE
Make the most compelling BULLISH argument using the Toulmin argumentation model.
DO NOT BE TIMID - if the data supports buying, advocate strongly for BUY!

## TOULMIN MODEL - YOU MUST INCLUDE ALL 5 COMPONENTS:

1. **CLAIM** - Clear, specific: "Investors should BUY {symbol} because..."
2. **EVIDENCE** - Use SPECIFIC NUMBERS: percentages, dollar amounts, ratios (minimum 3 points)
3. **WARRANT** - Explain WHY this evidence supports buying
4. **QUALIFIER** - State your confidence (0.6-0.95)
5. **REBUTTAL** - Counter the BEAR's argument directly

## DATA
NEWS: {news_report}
SENTIMENT: {sentiment_report}
MARKET: {market_report}
FUNDAMENTAL: {fundamental_report}

## BEAR'S ARGUMENT TO COUNTER
{opponent_point}

## OUTPUT (strict JSON):
{{
    "claim": "Clear BUY recommendation with specific thesis",
    "evidence": ["Evidence 1 with numbers", "Evidence 2 with metrics", "Evidence 3 with data"],
    "warrant": "Why this evidence supports buying",
    "qualifier": "Confidence level and conditions",
    "rebuttal": "Counter to bear's main argument",
    "confidence": 0.7
}}

REMEMBER: Be DECISIVE. If data supports buying, say BUY with conviction!"""


BEAR_PROMPT = """You are a BEARISH investment analyst presenting a STRONG CASE TO SELL/AVOID {symbol}.

## YOUR OBJECTIVE
Make the most compelling BEARISH argument using the Toulmin argumentation model.
DO NOT BE TIMID - if the data shows risks, advocate strongly for SELL or AVOID!

## TOULMIN MODEL - YOU MUST INCLUDE ALL 5 COMPONENTS:

1. **CLAIM** - Clear, specific: "Investors should SELL/AVOID {symbol} because..."
2. **EVIDENCE** - Use SPECIFIC NUMBERS: losses, ratios, negative trends (minimum 3 points)
3. **WARRANT** - Explain WHY this evidence indicates risk
4. **QUALIFIER** - State your confidence (0.6-0.95)
5. **REBUTTAL** - Counter the BULL's argument directly

## DATA
NEWS: {news_report}
SENTIMENT: {sentiment_report}
MARKET: {market_report}
FUNDAMENTAL: {fundamental_report}

## BULL'S ARGUMENT TO COUNTER
{opponent_point}

## OUTPUT (strict JSON):
{{
    "claim": "Clear SELL recommendation with specific thesis",
    "evidence": ["Risk 1 with numbers", "Risk 2 with metrics", "Risk 3 with data"],
    "warrant": "Why this evidence supports selling",
    "qualifier": "Confidence level and conditions",
    "rebuttal": "Counter to bull's main argument",
    "confidence": 0.7
}}

REMEMBER: Be DECISIVE. If data shows risks, say SELL with conviction!"""


FACILITATOR_PROMPT = """You are the Chief Investment Officer making the FINAL decision for {symbol}.

## DEBATE FORMAT
This used ASIAN PARLIAMENTARY format: Bull spoke LAST with the closing argument.
Evaluate based on PRIMARY EVIDENCE quality, not speaking order.

## BULL'S CASE
{bull_points}

## BEAR'S CASE
{bear_points}

## TOULMIN QUALITY SCORING (1-5 each)
For EACH side evaluate:
1. **Claim Clarity**: Is the recommendation specific?
2. **Evidence Quality**: Are there 3+ concrete data points?
3. **Warrant Strength**: Does logic connect evidence to claim?
4. **Qualifier Honesty**: Is confidence realistic?
5. **Rebuttal Effectiveness**: Did they counter the opposing view?

## DECISION RULES

Calculate: BULL_TOTAL = sum of Bull's 5 scores (max 25)
Calculate: BEAR_TOTAL = sum of Bear's 5 scores (max 25)

**Check confidence levels:**
- If Bull confidence > 0.75 AND Bear confidence < 0.60 → Lean **BUY**
- If Bear confidence > 0.75 AND Bull confidence < 0.60 → Lean **SELL**

**Score-based decision:**
- If BULL_TOTAL > BEAR_TOTAL + 2: Recommend **BUY**
- If BEAR_TOTAL > BULL_TOTAL + 2: Recommend **SELL**  
- If within 2 points AND similar confidence: Recommend **HOLD**

## OUTPUT (JSON only):
{{
    "bull_scores": {{"claim": X, "evidence": X, "warrant": X, "qualifier": X, "rebuttal": X}},
    "bear_scores": {{"claim": X, "evidence": X, "warrant": X, "qualifier": X, "rebuttal": X}},
    "bull_total": X,
    "bear_total": X,
    "recommendation": "BUY or SELL or HOLD",
    "confidence": 0.0-1.0,
    "rationale": "Brief explanation"
}}"""


# ============================================================
# DEBATE RUNNER
# ============================================================

class DebateRunner:
    def __init__(self, llm: LLMClient, max_rounds: int = 2):
        self.llm = llm
        self.max_rounds = max_rounds
    
    def run(self, scenario: Dict) -> Tuple[str, float, List[Dict], List[Dict], int, int]:
        symbol = scenario.get("symbol", "STOCK")
        inputs = scenario["inputs"]
        bull_points, bear_points = [], []
        
        for round_num in range(self.max_rounds):
            is_final = (round_num == self.max_rounds - 1)
            
            if is_final:
                # Asian debate: Bear first, Bull closes
                bear_opponent = bull_points[-1] if bull_points else None
                bear_points.append(self._get_point("bear", symbol, inputs, bear_opponent))
                bull_points.append(self._get_point("bull", symbol, inputs, bear_points[-1]))
            else:
                bull_opponent = bear_points[-1] if bear_points else None
                bull_points.append(self._get_point("bull", symbol, inputs, bull_opponent))
                bear_points.append(self._get_point("bear", symbol, inputs, bull_points[-1]))
        
        rec, conf, bull_total, bear_total = self._get_decision(symbol, bull_points, bear_points)
        return rec, conf, bull_points, bear_points, bull_total, bear_total
    
    def _get_point(self, party: str, symbol: str, inputs: Dict, opponent: Optional[Dict]) -> Dict:
        prompt_template = BULL_PROMPT if party == "bull" else BEAR_PROMPT
        opponent_text = "None - you speak first." if not opponent else json.dumps(opponent, indent=2)
        
        prompt = prompt_template.format(
            symbol=symbol,
            news_report=inputs["news_report"],
            sentiment_report=inputs["sentiment_report"],
            market_report=inputs["market_report"],
            fundamental_report=inputs["fundamental_report"],
            opponent_point=opponent_text
        )
        
        response = self.llm.complete(prompt)
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return {"claim": "Parse error", "evidence": [], "confidence": 0.5}
    
    def _get_decision(self, symbol: str, bull_points: List[Dict], bear_points: List[Dict]) -> Tuple[str, float, int, int]:
        prompt = FACILITATOR_PROMPT.format(
            symbol=symbol,
            bull_points=json.dumps(bull_points, indent=2),
            bear_points=json.dumps(bear_points, indent=2)
        )
        response = self.llm.complete(prompt)
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            data = json.loads(response.strip())
            return (
                data.get("recommendation", "HOLD").upper(),
                float(data.get("confidence", 0.5)),
                int(data.get("bull_total", 15)),
                int(data.get("bear_total", 15))
            )
        except:
            return "HOLD", 0.5, 15, 15


# ============================================================
# QUALITY METRICS
# ============================================================

def calculate_quality_parallel(llm: LLMClient, bull_points: List[Dict], bear_points: List[Dict]) -> DebateQualityMetrics:
    def calc_cogency():
        prompt = f"Rate logical quality 1-5. Output JSON: {{\"overall\": X}}\n\nBULL: {json.dumps(bull_points)}\nBEAR: {json.dumps(bear_points)}"
        try:
            resp = llm.complete(prompt)
            if "```" in resp:
                resp = resp.split("```")[1].split("```")[0].replace("json", "")
            return json.loads(resp.strip()).get("overall", 3) / 5.0
        except:
            return 0.6
    
    def calc_persuasiveness():
        prompt = f"Rate persuasiveness 1-10 for each. Output JSON: {{\"bull\": X, \"bear\": X}}\n\nBULL: {json.dumps(bull_points)}\nBEAR: {json.dumps(bear_points)}"
        try:
            resp = llm.complete(prompt)
            if "```" in resp:
                resp = resp.split("```")[1].split("```")[0].replace("json", "")
            data = json.loads(resp.strip())
            bull_score = float(data.get("bull", 5))
            bear_score = float(data.get("bear", 5))
            return (bull_score, bear_score)
        except:
            return (5.0, 5.0)
    
    def calc_civility():
        debate = "\n".join([f"Bull: {b.get('claim','')} Bear: {r.get('claim','')}" for b, r in zip(bull_points, bear_points)])
        prompt = f"Rate civility 1-5. Output JSON: {{\"civility\": X}}\n\n{debate}"
        try:
            resp = llm.complete(prompt)
            if "```" in resp:
                resp = resp.split("```")[1].split("```")[0].replace("json", "")
            return json.loads(resp.strip()).get("civility", 3)
        except:
            return 3.0
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_cog = executor.submit(calc_cogency)
        future_pers = executor.submit(calc_persuasiveness)
        future_civ = executor.submit(calc_civility)
        cogency = future_cog.result()
        bull_pers, bear_pers = future_pers.result()
        civility = future_civ.result()
    
    # Non-LLM metrics
    convergence = 0.5
    if bull_points and bear_points:
        initial_gap = abs(bull_points[0].get("confidence", 0.5) - bear_points[0].get("confidence", 0.5))
        final_gap = abs(bull_points[-1].get("confidence", 0.5) - bear_points[-1].get("confidence", 0.5))
        if initial_gap > 0:
            convergence = max(0, min(1, 0.5 + (initial_gap - final_gap) / initial_gap * 0.5))
    
    all_evidence = []
    novelty_per_point = []
    for point in bull_points + bear_points:
        evidence = point.get("evidence", [])
        if evidence:
            new_count = sum(1 for e in evidence if e not in all_evidence)
            novelty_per_point.append(new_count / len(evidence))
            all_evidence.extend(evidence)
    novelty = sum(novelty_per_point) / len(novelty_per_point) if novelty_per_point else 0.0
    
    return DebateQualityMetrics(
        cogency=cogency,
        persuasiveness_bull=bull_pers,
        persuasiveness_bear=bear_pers,
        civility=civility,
        convergence=convergence,
        evidence_novelty=novelty
    )


def update_elo(bull_elo: float, bear_elo: float, winner: str, k: float = 32) -> Tuple[float, float]:
    expected_bull = 1 / (1 + 10 ** ((bear_elo - bull_elo) / 400))
    if winner == "BULL":
        actual_bull = 1
    elif winner == "BEAR":
        actual_bull = 0
    else:
        actual_bull = 0.5
    new_bull = bull_elo + k * (actual_bull - expected_bull)
    new_bear = bear_elo + k * ((1 - actual_bull) - (1 - expected_bull))
    return new_bull, new_bear


def run_scenario(scenario: Dict, max_rounds: int) -> ScenarioResult:
    llm = LLMClient(DEFAULT_MODEL)
    scenario_id = scenario.get("dataset_id", "unknown")
    symbol = scenario.get("symbol", "STOCK")
    category = scenario.get("category", "unknown")
    expected = scenario.get("ground_truth", {}).get("expected_recommendation", "HOLD")
    
    start_time = time.time()
    
    runner = DebateRunner(llm, max_rounds)
    rec, conf, bull_pts, bear_pts, bull_total, bear_total = runner.run(scenario)
    
    is_correct = rec == expected
    
    if bull_total > bear_total + 1:
        winner = "BULL"
    elif bear_total > bull_total + 1:
        winner = "BEAR"
    else:
        winner = "TIE"
    
    quality = calculate_quality_parallel(llm, bull_pts, bear_pts)
    exec_time = time.time() - start_time
    
    bull_conf = bull_pts[-1].get("confidence", 0.7) if bull_pts else 0.7
    bear_conf = bear_pts[-1].get("confidence", 0.7) if bear_pts else 0.7
    bull_ev = sum(len(p.get("evidence", [])) for p in bull_pts) / max(len(bull_pts), 1)
    bear_ev = sum(len(p.get("evidence", [])) for p in bear_pts) / max(len(bear_pts), 1)
    
    return ScenarioResult(
        dataset_id=scenario_id,
        symbol=symbol,
        category=category,
        expected=expected,
        actual=rec,
        is_correct=is_correct,
        bull_toulmin_score=bull_total / 25.0,
        bear_toulmin_score=bear_total / 25.0,
        avg_toulmin_score=(bull_total + bear_total) / 50.0,
        rounds=max_rounds,
        execution_time=exec_time,
        winner=winner,
        bull_confidence=bull_conf,
        bear_confidence=bear_conf,
        bull_evidence_count=int(bull_ev),
        bear_evidence_count=int(bear_ev),
        quality=quality
    )


def load_scenarios(max_scenarios: int = 15) -> List[Dict]:
    datasets_dir = Path(__file__).parent / "datasets"
    scenarios = []
    if not datasets_dir.exists():
        return []
    for json_file in sorted(datasets_dir.rglob("*.json")):
        if json_file.name == "manifest.json":
            continue
        with open(json_file, "r") as f:
            scenarios.append(json.load(f))
        if len(scenarios) >= max_scenarios:
            break
    return scenarios


def run_benchmark(max_scenarios: int = 15, max_rounds: int = 2, parallel: int = 5):
    print("=" * 70)
    print("🚀 BULL-BEAR BENCHMARK (Original 73% Version)")
    print("=" * 70)
    print(f"  Model: {DEFAULT_MODEL}")
    print(f"  Scenarios: {max_scenarios} | Rounds: {max_rounds} | Parallel: {parallel}")
    print()
    
    scenarios = load_scenarios(max_scenarios)
    if not scenarios:
        print("❌ No scenarios found")
        return
    
    print(f"📁 Loaded {len(scenarios)} scenarios")
    print("=" * 70)
    
    start_total = time.time()
    results_list = []
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(run_scenario, s, max_rounds): s for s in scenarios}
        for future in as_completed(futures):
            try:
                result = future.result()
                results_list.append(result)
                status = "✅" if result.is_correct else "❌"
                print(f"[{len(results_list)}/{len(scenarios)}] {result.dataset_id} {status} {result.expected}→{result.actual} ({result.execution_time:.1f}s)")
            except Exception as e:
                print(f"ERROR: {e}")
    
    total_time = time.time() - start_total
    results = aggregate_results(results_list, max_rounds)
    
    print(f"\n⏱️ Total: {total_time:.1f}s ({total_time/len(scenarios):.1f}s/scenario)")
    print_report(results)
    save_results(results)
    return results


def aggregate_results(scenario_results: List[ScenarioResult], max_rounds: int) -> BenchmarkResults:
    results = BenchmarkResults()
    n = len(scenario_results)
    results.total = n
    results.scenarios = scenario_results
    
    category_correct = defaultdict(int)
    category_total = defaultdict(int)
    confusion = defaultdict(lambda: defaultdict(int))
    bull_elo, bear_elo = 1500.0, 1500.0
    
    for r in scenario_results:
        results.correct += int(r.is_correct)
        category_correct[r.category] += int(r.is_correct)
        category_total[r.category] += 1
        confusion[r.expected][r.actual] += 1
        
        if r.winner == "BULL":
            results.bull_wins += 1
        elif r.winner == "BEAR":
            results.bear_wins += 1
        else:
            results.ties += 1
        bull_elo, bear_elo = update_elo(bull_elo, bear_elo, r.winner)
    
    results.directional_accuracy = results.correct / n
    results.accuracy_by_category = {cat: category_correct[cat] / category_total[cat] for cat in category_total}
    results.confusion_matrix = {k: dict(v) for k, v in confusion.items()}
    results.avg_toulmin_bull = sum(r.bull_toulmin_score for r in scenario_results) / n
    results.avg_toulmin_bear = sum(r.bear_toulmin_score for r in scenario_results) / n
    results.avg_toulmin_overall = (results.avg_toulmin_bull + results.avg_toulmin_bear) / 2
    results.avg_rounds = max_rounds
    results.bull_elo = bull_elo
    results.bear_elo = bear_elo
    results.avg_bull_confidence = sum(r.bull_confidence for r in scenario_results) / n
    results.avg_bear_confidence = sum(r.bear_confidence for r in scenario_results) / n
    results.avg_confidence_gap = abs(results.avg_bull_confidence - results.avg_bear_confidence)
    results.avg_bull_evidence_count = sum(r.bull_evidence_count for r in scenario_results) / n
    results.avg_bear_evidence_count = sum(r.bear_evidence_count for r in scenario_results) / n
    results.avg_evidence_per_point = (results.avg_bull_evidence_count + results.avg_bear_evidence_count) / 2
    results.avg_cogency = sum(r.quality.cogency for r in scenario_results) / n
    results.avg_persuasiveness_bull = sum(r.quality.persuasiveness_bull for r in scenario_results) / n
    results.avg_persuasiveness_bear = sum(r.quality.persuasiveness_bear for r in scenario_results) / n
    results.avg_civility = sum(r.quality.civility for r in scenario_results) / n
    results.avg_convergence = sum(r.quality.convergence for r in scenario_results) / n
    results.avg_evidence_novelty = sum(r.quality.evidence_novelty for r in scenario_results) / n
    return results


def print_report(results: BenchmarkResults):
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " BENCHMARK RESULTS".center(68) + "║")
    print("╠" + "═" * 68 + "╣")
    print("║" + f"  Accuracy: {results.directional_accuracy*100:.1f}% ({results.correct}/{results.total})".ljust(68) + "║")
    for cat, acc in sorted(results.accuracy_by_category.items()):
        print("║" + f"    • {cat}: {acc*100:.1f}%".ljust(68) + "║")
    print("╠" + "═" * 68 + "╣")
    print("║" + f"  Toulmin: Bull={results.avg_toulmin_bull:.1%} Bear={results.avg_toulmin_bear:.1%}".ljust(68) + "║")
    print("║" + f"  Wins: Bull={results.bull_wins} Bear={results.bear_wins} Ties={results.ties}".ljust(68) + "║")
    print("║" + f"  Elo: Bull={results.bull_elo:.0f} Bear={results.bear_elo:.0f}".ljust(68) + "║")
    print("╠" + "═" * 68 + "╣")
    print("║" + f"  Quality: Cogency={results.avg_cogency:.2f} Civility={results.avg_civility:.1f}".ljust(68) + "║")
    print("║" + f"  Persuasion: Bull={results.avg_persuasiveness_bull:.1f} Bear={results.avg_persuasiveness_bear:.1f}".ljust(68) + "║")
    print("╚" + "═" * 68 + "╝")


def save_results(results: BenchmarkResults):
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    metrics = {k: v for k, v in asdict(results).items() if k != "scenarios"}
    with open(output_dir / f"metrics_{timestamp}.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    with open(output_dir / f"results_{timestamp}.json", "w") as f:
        json.dump([asdict(s) for s in results.scenarios], f, indent=2)
    
    print(f"\n📄 Saved to results/metrics_{timestamp}.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-scenarios", type=int, default=15)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--parallel", type=int, default=5)
    args = parser.parse_args()
    run_benchmark(args.max_scenarios, args.max_rounds, args.parallel)


if __name__ == "__main__":
    main()
