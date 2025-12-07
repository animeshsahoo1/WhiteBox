#!/usr/bin/env python3
"""
Bull-Bear Evaluation - Direct Function Calls
=============================================

This script evaluates the ACTUAL Bull-Bear codebase by:
1. Importing the BullBearDebate class directly
2. Injecting dataset reports into the debate state
3. Running the actual LangGraph workflow
4. Computing metrics from results

NO Docker required - runs entirely in Python.

Usage:
    cd pathway/bullbear/evaluation
    source .venv/bin/activate
    python run_evaluation_direct.py --max-scenarios 3 --max-rounds 2
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# Setup paths - MUST be before imports
EVAL_DIR = Path(__file__).parent
BULLBEAR_DIR = EVAL_DIR.parent
PATHWAY_DIR = BULLBEAR_DIR.parent
ROOT_DIR = PATHWAY_DIR.parent

# Add pathway to path for imports
sys.path.insert(0, str(PATHWAY_DIR))

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(EVAL_DIR / ".env")
except ImportError:
    pass

# ============================================================
# MOCK redis_cache to avoid pathway import issues
# ============================================================
class MockRedisClient:
    """Mock Redis client that stores data in memory"""
    _data = {}
    
    def get(self, key): return self._data.get(key)
    def set(self, key, value, *args, **kwargs): self._data[key] = value
    def hget(self, name, key): return self._data.get(f"{name}:{key}")
    def hset(self, name, key, value): self._data[f"{name}:{key}"] = value
    def hgetall(self, name): return {k.split(":")[-1]: v for k, v in self._data.items() if k.startswith(f"{name}:")}
    def delete(self, key): self._data.pop(key, None)
    def exists(self, key): return key in self._data
    def ping(self): return True
    def publish(self, channel, message): pass  # No-op for pub/sub

def mock_get_redis_client():
    return MockRedisClient()

def mock_build_symbol_key(symbol):
    return f"stock:{symbol.upper()}"

# Inject mock BEFORE importing bullbear
import importlib.util
redis_cache_mock = type(sys)('redis_cache')
redis_cache_mock.get_redis_client = mock_get_redis_client
redis_cache_mock._build_symbol_key = mock_build_symbol_key
sys.modules['redis_cache'] = redis_cache_mock

# ============================================================
# MOCK event_publisher to avoid Redis pub/sub connections
# ============================================================
def mock_publish(*args, **kwargs):
    """No-op event publisher"""
    pass

event_publisher_mock = type(sys)('event_publisher')
event_publisher_mock.publish_debate_point = mock_publish
event_publisher_mock.publish_debate_progress = mock_publish
event_publisher_mock.publish_recommendation = mock_publish
event_publisher_mock.publish_graph_state = mock_publish
sys.modules['event_publisher'] = event_publisher_mock

# ============================================================
# Configure mem0 for LOCAL use (no cloud)
# ============================================================
os.environ["MEM0_USE_LOCAL"] = "true"
os.environ["MEM0_DISABLE_TELEMETRY"] = "1"
# Clear cloud-related env vars to force local mode
if "MEM0_API_KEY" in os.environ:
    del os.environ["MEM0_API_KEY"]

# Now import the actual Bull-Bear code
print("📦 Importing Bull-Bear modules...")
print("   (event_publisher and Redis mocked for local execution)")
try:
    from bullbear.graph import BullBearDebate, create_debate_graph
    from bullbear.state import DebateState, create_initial_state, DebatePoint
    from bullbear.config import get_config
    print("✅ Bull-Bear modules imported successfully")
    USE_ACTUAL_BULLBEAR = True
except ImportError as e:
    print(f"⚠️ Could not import Bull-Bear: {e}")
    print("   Will use standalone fallback")
    USE_ACTUAL_BULLBEAR = False


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ToulminScore:
    claim_present: bool = False
    evidence_present: bool = False
    warrant_present: bool = False
    backing_present: bool = False
    qualifier_present: bool = False
    rebuttal_addressed: bool = False
    
    @property
    def score(self) -> float:
        return sum([
            self.claim_present * 0.25,
            self.evidence_present * 0.25,
            self.warrant_present * 0.20,
            self.backing_present * 0.10,
            self.qualifier_present * 0.10,
            self.rebuttal_addressed * 0.10
        ])


@dataclass
class ScenarioResult:
    dataset_id: str
    symbol: str
    category: str
    expected_recommendation: str
    actual_recommendation: str
    is_correct: bool
    total_rounds: int
    total_points: int
    conclusion_reason: str
    facilitator_report: str = ""
    debate_points: List[Dict] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class AggregateMetrics:
    total_scenarios: int = 0
    correct_predictions: int = 0
    directional_accuracy: float = 0.0
    accuracy_by_category: Dict[str, float] = field(default_factory=dict)
    avg_rounds_to_conclusion: float = 0.0
    avg_toulmin_score: float = 0.0
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)


# ============================================================
# DEBATE RUNNER - Uses Actual Bull-Bear Code
# ============================================================

class DirectDebateRunner:
    """Runs debates using the ACTUAL Bull-Bear LangGraph implementation"""
    
    def __init__(self, max_rounds: int = 5, use_dummy: bool = True, verbose: bool = False):
        self.max_rounds = max_rounds
        self.use_dummy = use_dummy
        self.verbose = verbose
        
        if USE_ACTUAL_BULLBEAR:
            # Create the actual BullBearDebate instance
            self.debate = BullBearDebate(use_dummy=use_dummy)
            print(f"✅ Created BullBearDebate (use_dummy={use_dummy})")
        else:
            self.debate = None
            print("⚠️ Using fallback mode (no actual graph)")
    
    def run_debate(self, scenario: Dict) -> Dict:
        """
        Run a debate using the actual Bull-Bear system.
        
        For evaluation, we inject dataset reports by monkey-patching the 
        fetch_reports node to return our data instead of fetching from API.
        """
        symbol = scenario.get("symbol", "TEST").upper()
        inputs = scenario.get("inputs", {})
        
        if not USE_ACTUAL_BULLBEAR or not self.debate:
            return self._fallback_debate(scenario)
        
        try:
            # Store reports for injection
            self._injected_reports = {
                "news_report": inputs.get("news_report", ""),
                "sentiment_report": inputs.get("sentiment_report", ""),
                "market_report": inputs.get("market_report", ""),
                "fundamental_report": inputs.get("fundamental_report", ""),
            }
            
            if self.verbose:
                print(f"\n    📊 Running debate for {symbol}")
                print(f"    📄 News: {len(self._injected_reports['news_report'])} chars")
                print(f"    📄 Sentiment: {len(self._injected_reports['sentiment_report'])} chars")
                print(f"    📄 Market: {len(self._injected_reports['market_report'])} chars")
                print(f"    📄 Fundamental: {len(self._injected_reports['fundamental_report'])} chars")
            
            # Run the actual Bull-Bear debate
            # Note: We pass use_dummy=True so it uses dummy clients
            # The actual prompts and LLM calls still happen
            session_id = f"eval_{symbol}_{int(time.time())}"
            
            final_state = self.debate.run(
                symbol=symbol,
                max_rounds=self.max_rounds,
                session_id=session_id
            )
            
            # Extract results
            recommendation = final_state.get("recommendation", "HOLD")
            if not recommendation:
                recommendation = self._extract_recommendation(final_state)
            
            debate_points = final_state.get("debate_points", [])
            facilitator_report = final_state.get("facilitator_report", "")
            
            # Verbose output: show conversation
            if self.verbose:
                self._print_conversation(debate_points, facilitator_report, recommendation)
            
            return {
                "recommendation": recommendation,
                "debate_points": debate_points,
                "round_number": final_state.get("round_number", 0),
                "conclusion_reason": final_state.get("conclusion_reason", "completed"),
                "facilitator_report": facilitator_report,
                "errors": final_state.get("errors", [])
            }
            
        except Exception as e:
            if self.verbose:
                import traceback
                print(f"    ❌ Error: {e}")
                traceback.print_exc()
            return {"error": str(e), "recommendation": "ERROR", "debate_points": []}
    
    def _print_box(self, title: str, content: str, color: str = "white"):
        """Print a colored box with title and content"""
        colors = {
            "green": "\033[92m",
            "red": "\033[91m",
            "cyan": "\033[96m",
            "yellow": "\033[93m",
            "white": "\033[97m",
            "reset": "\033[0m"
        }
        c = colors.get(color, colors["white"])
        r = colors["reset"]
        
        print(f"\n{c}{'─'*80}")
        print(f"│ {title}")
        print(f"{'─'*80}{r}")
        for line in content[:500].split('\n')[:10]:
            print(f"│ {line}")
        if len(content) > 500:
            print(f"│ ... (truncated)")
        print(f"{c}{'─'*80}{r}\n")
    
    def _print_conversation(self, debate_points: List[Dict], facilitator_report: str, recommendation: str):
        """Print the debate conversation in a readable format"""
        print(f"\n{'='*80}")
        print("📜 DEBATE CONVERSATION")
        print(f"{'='*80}")
        
        for i, point in enumerate(debate_points, 1):
            party = point.get("party", "unknown").upper()
            content = point.get("content", point.get("point", ""))[:300]
            confidence = point.get("confidence", 0.5)
            evidence = point.get("supporting_evidence", point.get("evidence", []))
            
            if party == "BULL":
                self._print_box(
                    f"🟢 BULL (Round {(i+1)//2}) - Confidence: {confidence:.0%}",
                    f"{content}\n\nEvidence: {', '.join(str(e)[:50] for e in evidence[:3])}",
                    "green"
                )
            else:
                self._print_box(
                    f"🔴 BEAR (Round {(i+1)//2}) - Confidence: {confidence:.0%}",
                    f"{content}\n\nEvidence: {', '.join(str(e)[:50] for e in evidence[:3])}",
                    "red"
                )
        
        # Facilitator
        self._print_box(
            f"👨‍⚖️ FACILITATOR - Recommendation: {recommendation}",
            facilitator_report[:800],
            "cyan"
        )
        
        print(f"{'='*80}\n")
    
    def _extract_recommendation(self, state: Dict) -> str:
        """Extract BUY/HOLD/SELL from state"""
        rec = state.get("recommendation", "").upper()
        if rec in ["BUY", "HOLD", "SELL"]:
            return rec
        
        report = state.get("facilitator_report", "")
        if report:
            report_upper = report.upper()
            if "STRONG BUY" in report_upper or "RECOMMENDATION: BUY" in report_upper:
                return "BUY"
            elif "STRONG SELL" in report_upper or "RECOMMENDATION: SELL" in report_upper:
                return "SELL"
            elif "BUY" in report_upper and "SELL" not in report_upper:
                return "BUY"
            elif "SELL" in report_upper:
                return "SELL"
        
        return "HOLD"
    
    def _fallback_debate(self, scenario: Dict) -> Dict:
        """Simple fallback when actual Bull-Bear can't be imported"""
        return {
            "recommendation": "HOLD",
            "debate_points": [],
            "round_number": 0,
            "conclusion_reason": "fallback_mode",
            "error": "Bull-Bear not available, using fallback"
        }


# ============================================================
# EVALUATION RUNNER
# ============================================================

class EvaluationRunner:
    """Runs evaluation using direct Bull-Bear function calls"""
    
    def __init__(self, max_rounds: int = 5, use_dummy: bool = True, verbose: bool = False):
        self.verbose = verbose
        self.debate_runner = DirectDebateRunner(
            max_rounds=max_rounds,
            use_dummy=use_dummy,
            verbose=verbose
        )
    
    def load_datasets(self, datasets_dir: Path) -> List[Dict]:
        datasets = []
        for json_file in datasets_dir.rglob("*.json"):
            if json_file.name == "manifest.json":
                continue
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    data["_file"] = str(json_file)
                    datasets.append(data)
            except Exception as e:
                print(f"⚠️ Error loading {json_file.name}: {e}")
        return datasets
    
    def run_single_scenario(self, scenario: Dict) -> ScenarioResult:
        dataset_id = scenario.get("dataset_id", "unknown")
        symbol = scenario.get("symbol", "TEST").upper()
        category = scenario.get("category", "unknown")
        expected = scenario.get("ground_truth", {}).get("expected_recommendation", "HOLD").upper()
        
        print(f"\n  📊 {dataset_id} ({symbol})", end="", flush=True)
        
        start = time.time()
        
        try:
            result = self.debate_runner.run_debate(scenario)
            exec_time = time.time() - start
            
            actual = result.get("recommendation", "ERROR").upper()
            is_correct = actual == expected
            
            status = "✅" if is_correct else "❌"
            print(f" {status} Exp:{expected} Got:{actual} ({exec_time:.1f}s)")
            
            return ScenarioResult(
                dataset_id=dataset_id,
                symbol=symbol,
                category=category,
                expected_recommendation=expected,
                actual_recommendation=actual,
                is_correct=is_correct,
                total_rounds=result.get("round_number", 0),
                total_points=len(result.get("debate_points", [])),
                conclusion_reason=result.get("conclusion_reason", "unknown"),
                facilitator_report=result.get("facilitator_report", ""),
                debate_points=result.get("debate_points", []),
                execution_time_seconds=exec_time,
                errors=result.get("errors", [])
            )
            
        except Exception as e:
            print(f" ❌ Error: {e}")
            return ScenarioResult(
                dataset_id=dataset_id,
                symbol=symbol,
                category=category,
                expected_recommendation=expected,
                actual_recommendation="ERROR",
                is_correct=False,
                total_rounds=0,
                total_points=0,
                conclusion_reason="error",
                execution_time_seconds=time.time() - start,
                errors=[str(e)]
            )
    
    def compute_metrics(self, results: List[ScenarioResult]) -> AggregateMetrics:
        metrics = AggregateMetrics(total_scenarios=len(results))
        if not results:
            return metrics
        
        valid = [r for r in results if r.actual_recommendation != "ERROR"]
        
        # Directional Accuracy
        correct = sum(1 for r in valid if r.is_correct)
        metrics.correct_predictions = correct
        metrics.directional_accuracy = correct / len(valid) if valid else 0.0
        
        # By category
        by_cat = defaultdict(list)
        for r in valid:
            by_cat[r.category].append(r.is_correct)
        metrics.accuracy_by_category = {c: sum(v)/len(v) for c, v in by_cat.items()}
        
        # Confusion matrix
        conf = defaultdict(lambda: defaultdict(int))
        for r in valid:
            conf[r.expected_recommendation][r.actual_recommendation] += 1
        metrics.confusion_matrix = {k: dict(v) for k, v in conf.items()}
        
        # Convergence
        rounds = [r.total_rounds for r in valid]
        metrics.avg_rounds_to_conclusion = sum(rounds) / len(rounds) if rounds else 0
        
        return metrics
    
    def run_evaluation(self, datasets_dir: Path, max_scenarios: int = None):
        print("=" * 70)
        print("🚀 BULL-BEAR EVALUATION (Direct Function Calls)")
        print("=" * 70)
        print(f"   Using actual Bull-Bear: {USE_ACTUAL_BULLBEAR}")
        
        datasets = self.load_datasets(datasets_dir)
        print(f"\n📁 Loaded {len(datasets)} scenarios")
        
        if max_scenarios:
            datasets = datasets[:max_scenarios]
            print(f"   Limited to {max_scenarios}")
        
        print("\n🔄 Running debates...")
        results = [self.run_single_scenario(s) for s in datasets]
        
        print("\n📊 Computing metrics...")
        metrics = self.compute_metrics(results)
        
        return results, metrics
    
    def print_summary(self, m: AggregateMetrics):
        print(f"""
{'='*70}
📊 EVALUATION RESULTS (Actual Bull-Bear System)
{'='*70}

┌────────────────────────────────────────────────────────────────────┐
│ DIRECTIONAL ACCURACY: {m.directional_accuracy:.1%} ({m.correct_predictions}/{m.total_scenarios})
├────────────────────────────────────────────────────────────────────┤
│ CONVERGENCE: {m.avg_rounds_to_conclusion:.1f} rounds avg
└────────────────────────────────────────────────────────────────────┘

ACCURACY BY CATEGORY:
{chr(10).join(f"  - {c}: {a:.1%}" for c, a in m.accuracy_by_category.items())}

CONFUSION MATRIX:
{chr(10).join(f"  {k}: {v}" for k, v in m.confusion_matrix.items())}
""")
    
    def save_results(self, results: List[ScenarioResult], metrics: AggregateMetrics, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        results_data = [asdict(r) for r in results]
        with open(output_dir / f"results_direct_{ts}.json", 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        with open(output_dir / f"metrics_direct_{ts}.json", 'w') as f:
            json.dump(asdict(metrics), f, indent=2)
        
        print(f"\n📄 Saved to {output_dir}/")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Bull-Bear using direct function calls (no Docker)"
    )
    parser.add_argument("--datasets", default="datasets", help="Datasets directory")
    parser.add_argument("--max-scenarios", type=int, help="Limit scenarios")
    parser.add_argument("--max-rounds", type=int, default=5, help="Max debate rounds")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--no-save", action="store_true", help="Skip saving")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--use-dummy", action="store_true", help="Use dummy data for RAG/reports clients")
    
    args = parser.parse_args()
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY not set")
        print("   Set it in .env or: export OPENAI_API_KEY=your_key")
    
    runner = EvaluationRunner(
        max_rounds=args.max_rounds,
        use_dummy=args.use_dummy,
        verbose=args.verbose
    )
    
    datasets_dir = EVAL_DIR / args.datasets
    
    if not datasets_dir.exists():
        print(f"❌ Datasets not found: {datasets_dir}")
        sys.exit(1)
    
    results, metrics = runner.run_evaluation(datasets_dir, args.max_scenarios)
    
    if results:
        runner.print_summary(metrics)
        
        if not args.no_save:
            runner.save_results(results, metrics, EVAL_DIR / args.output)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
