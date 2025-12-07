#!/usr/bin/env python3
"""
Bull-Bear Evaluation Pipeline - Using ACTUAL Codebase
======================================================

This script evaluates the REAL Bull-Bear debate system by:
1. Writing dataset reports to the reports/ directories
2. Calling the actual Bull-Bear API (Docker service)
3. Collecting results and computing metrics

Prerequisites:
- Docker services running: `docker compose up -d redis unified-api`
- API accessible at http://localhost:8000

Usage:
    # Start Docker services first
    cd /path/to/Pathway_InterIIT && docker compose up -d redis unified-api
    
    # Run evaluation
    cd pathway/bullbear/evaluation
    source .venv/bin/activate
    python run_evaluation_actual.py --max-scenarios 5
"""

import os
import sys
import json
import argparse
import time
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# Constants
EVAL_DIR = Path(__file__).parent
BULLBEAR_DIR = EVAL_DIR.parent
PATHWAY_DIR = BULLBEAR_DIR.parent

# Reports directories (where the actual system reads from)
REPORTS_DIR = PATHWAY_DIR / "reports"
NEWS_REPORTS_DIR = REPORTS_DIR / "news"
SENTIMENT_REPORTS_DIR = REPORTS_DIR / "sentiment"
MARKET_REPORTS_DIR = REPORTS_DIR / "market"
FUNDAMENTAL_REPORTS_DIR = REPORTS_DIR / "fundamental"

# API Configuration
API_BASE_URL = os.getenv("BULLBEAR_API_URL", "http://localhost:8000")
DEBATE_ENDPOINT = f"{API_BASE_URL}/debate"

try:
    from dotenv import load_dotenv
    load_dotenv(EVAL_DIR / ".env")
except ImportError:
    pass


# ============================================================
# DATA CLASSES FOR METRICS
# ============================================================

@dataclass
class ToulminScore:
    """Toulmin Model argumentation quality score"""
    claim_present: bool = False
    evidence_present: bool = False
    warrant_present: bool = False
    backing_present: bool = False
    qualifier_present: bool = False
    rebuttal_addressed: bool = False
    
    @property
    def score(self) -> float:
        components = [
            self.claim_present * 0.25,
            self.evidence_present * 0.25,
            self.warrant_present * 0.20,
            self.backing_present * 0.10,
            self.qualifier_present * 0.10,
            self.rebuttal_addressed * 0.10
        ]
        return sum(components)


@dataclass
class ScenarioResult:
    """Results from running one scenario"""
    dataset_id: str
    symbol: str
    category: str
    expected_recommendation: str
    actual_recommendation: str
    is_correct: bool
    total_rounds: int
    conclusion_reason: str
    facilitator_report: str = ""
    execution_time_seconds: float = 0.0
    api_response: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all scenarios"""
    total_scenarios: int = 0
    correct_predictions: int = 0
    directional_accuracy: float = 0.0
    accuracy_by_category: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    avg_rounds_to_conclusion: float = 0.0
    conclusion_reasons: Dict[str, int] = field(default_factory=dict)


# ============================================================
# REPORT INJECTION
# ============================================================

class ReportInjector:
    """Injects dataset reports into the filesystem where Bull-Bear reads them"""
    
    def __init__(self):
        self.reports_dir = REPORTS_DIR
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create report directories if they don't exist"""
        for d in [NEWS_REPORTS_DIR, SENTIMENT_REPORTS_DIR, MARKET_REPORTS_DIR, FUNDAMENTAL_REPORTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
    
    def inject_reports(self, symbol: str, inputs: Dict) -> bool:
        """
        Write dataset reports to the filesystem.
        
        Args:
            symbol: Stock symbol (used as directory name)
            inputs: Dict with news_report, sentiment_report, market_report, fundamental_report
            
        Returns:
            True if successful
        """
        symbol = symbol.upper()
        
        try:
            # Create symbol-specific directories
            for d in [NEWS_REPORTS_DIR, SENTIMENT_REPORTS_DIR, MARKET_REPORTS_DIR, FUNDAMENTAL_REPORTS_DIR]:
                (d / symbol).mkdir(parents=True, exist_ok=True)
            
            # Write each report
            report_mappings = [
                (NEWS_REPORTS_DIR / symbol / "report.json", "news_report", "news"),
                (SENTIMENT_REPORTS_DIR / symbol / "report.json", "sentiment_report", "sentiment"),
                (MARKET_REPORTS_DIR / symbol / "report.json", "market_report", "market"),
                (FUNDAMENTAL_REPORTS_DIR / symbol / "report.json", "fundamental_report", "fundamental"),
            ]
            
            for path, input_key, report_type in report_mappings:
                content = inputs.get(input_key, "")
                report_data = {
                    "symbol": symbol,
                    "report_type": report_type,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "evaluation_dataset"
                }
                path.write_text(json.dumps(report_data, indent=2))
            
            print(f"    📄 Injected reports for {symbol}")
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to inject reports for {symbol}: {e}")
            return False
    
    def cleanup_reports(self, symbol: str):
        """Remove injected reports after evaluation"""
        symbol = symbol.upper()
        for d in [NEWS_REPORTS_DIR, SENTIMENT_REPORTS_DIR, MARKET_REPORTS_DIR, FUNDAMENTAL_REPORTS_DIR]:
            report_dir = d / symbol
            if report_dir.exists():
                for f in report_dir.glob("*"):
                    f.unlink()


# ============================================================
# API CLIENT
# ============================================================

class BullBearAPIClient:
    """Client for calling the actual Bull-Bear API"""
    
    def __init__(self, base_url: str = None, timeout: int = 300):
        self.base_url = base_url or API_BASE_URL
        self.timeout = timeout
    
    def check_health(self) -> bool:
        """Check if the API is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def run_debate(self, symbol: str, max_rounds: int = 5, use_dummy: bool = False) -> Dict:
        """
        Run a debate via the API.
        
        Args:
            symbol: Stock symbol
            max_rounds: Maximum debate rounds
            use_dummy: If True, use dummy data (don't use - we inject real reports)
            
        Returns:
            API response dict
        """
        try:
            # Start debate synchronously (background=False)
            response = requests.post(
                f"{self.base_url}/debate/{symbol}",
                json={
                    "max_rounds": max_rounds,
                    "background": False,  # Wait for completion
                    "use_dummy": use_dummy
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.Timeout:
            return {"error": "Timeout waiting for debate to complete", "status": "error"}
        except requests.RequestException as e:
            return {"error": str(e), "status": "error"}
    
    def get_debate_status(self, symbol: str) -> Dict:
        """Get current debate status"""
        try:
            response = requests.get(
                f"{self.base_url}/debate/{symbol}/status",
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}


# ============================================================
# EVALUATION RUNNER
# ============================================================

class EvaluationRunner:
    """Runs evaluation using actual Bull-Bear system"""
    
    def __init__(self, max_rounds: int = 5, api_url: str = None, verbose: bool = False):
        self.max_rounds = max_rounds
        self.verbose = verbose
        self.injector = ReportInjector()
        self.api = BullBearAPIClient(api_url)
    
    def check_prerequisites(self) -> bool:
        """Check if Docker services are running"""
        print("\n🔍 Checking prerequisites...")
        
        if not self.api.check_health():
            print("""
❌ Bull-Bear API not accessible at {url}

Please start Docker services:
    cd /path/to/Pathway_InterIIT
    docker compose up -d redis unified-api
    
Or start with full stack:
    docker compose up -d
    
Wait for services to be healthy, then retry.
""".format(url=self.api.base_url))
            return False
        
        print(f"✅ API healthy at {self.api.base_url}")
        return True
    
    def load_datasets(self, datasets_dir: Path) -> List[Dict]:
        """Load all dataset JSON files"""
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
    
    def extract_recommendation(self, api_response: Dict) -> str:
        """Extract BUY/HOLD/SELL from API response or facilitator report"""
        # Try direct recommendation field
        rec = api_response.get("recommendation", "").upper()
        if rec in ["BUY", "HOLD", "SELL"]:
            return rec
        
        # Try parsing facilitator report
        report = api_response.get("facilitator_report", "")
        if not report:
            return "HOLD"
        
        report_upper = report.upper()
        if "STRONG BUY" in report_upper or "RECOMMENDATION: BUY" in report_upper:
            return "BUY"
        elif "STRONG SELL" in report_upper or "RECOMMENDATION: SELL" in report_upper:
            return "SELL"
        elif "BUY" in report_upper and "SELL" not in report_upper:
            return "BUY"
        elif "SELL" in report_upper and "BUY" not in report_upper:
            return "SELL"
        return "HOLD"
    
    def run_single_scenario(self, scenario: Dict) -> ScenarioResult:
        """Run a single evaluation scenario"""
        dataset_id = scenario.get("dataset_id", "unknown")
        symbol = scenario.get("symbol", "TEST").upper()
        category = scenario.get("category", "unknown")
        expected = scenario.get("ground_truth", {}).get("expected_recommendation", "HOLD").upper()
        inputs = scenario.get("inputs", {})
        
        print(f"\n  📊 {dataset_id} ({symbol})", end="", flush=True)
        
        start = time.time()
        errors = []
        
        try:
            # Step 1: Inject reports to filesystem
            if not self.injector.inject_reports(symbol, inputs):
                errors.append("Failed to inject reports")
            
            # Step 2: Call the actual Bull-Bear API
            result = self.api.run_debate(symbol, max_rounds=self.max_rounds, use_dummy=False)
            exec_time = time.time() - start
            
            if self.verbose:
                print(f"\n      API Response: {json.dumps(result, indent=2)[:500]}...")
            
            # Step 3: Extract recommendation
            if "error" in result:
                errors.append(result["error"])
                actual = "ERROR"
            else:
                actual = self.extract_recommendation(result)
            
            is_correct = actual == expected
            
            # Step 4: Cleanup (optional)
            # self.injector.cleanup_reports(symbol)
            
            status = "✅" if is_correct else "❌"
            print(f" {status} Exp:{expected} Got:{actual} ({exec_time:.1f}s)")
            
            return ScenarioResult(
                dataset_id=dataset_id,
                symbol=symbol,
                category=category,
                expected_recommendation=expected,
                actual_recommendation=actual,
                is_correct=is_correct,
                total_rounds=result.get("rounds_completed", 0),
                conclusion_reason=result.get("conclusion_reason", "unknown"),
                facilitator_report=result.get("facilitator_report", ""),
                execution_time_seconds=exec_time,
                api_response=result,
                errors=errors
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
                conclusion_reason="error",
                execution_time_seconds=time.time() - start,
                errors=[str(e)]
            )
    
    def compute_metrics(self, results: List[ScenarioResult]) -> AggregateMetrics:
        """Compute aggregate metrics from results"""
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
        
        # Conclusion reasons
        for r in valid:
            metrics.conclusion_reasons[r.conclusion_reason] = \
                metrics.conclusion_reasons.get(r.conclusion_reason, 0) + 1
        
        return metrics
    
    def run_evaluation(self, datasets_dir: Path, max_scenarios: int = None):
        """Run full evaluation"""
        print("=" * 70)
        print("🚀 BULL-BEAR EVALUATION (Using ACTUAL System)")
        print("=" * 70)
        
        # Check prerequisites
        if not self.check_prerequisites():
            return [], AggregateMetrics()
        
        # Load datasets
        datasets = self.load_datasets(datasets_dir)
        print(f"\n📁 Loaded {len(datasets)} scenarios")
        
        if max_scenarios:
            datasets = datasets[:max_scenarios]
            print(f"   Limited to {max_scenarios}")
        
        print("\n🔄 Running debates via API...\n")
        results = [self.run_single_scenario(s) for s in datasets]
        
        print("\n📊 Computing metrics...")
        metrics = self.compute_metrics(results)
        
        return results, metrics
    
    def print_summary(self, m: AggregateMetrics):
        """Print metrics summary"""
        print(f"""
{'='*70}
📊 EVALUATION RESULTS (Actual Bull-Bear System)
{'='*70}

┌────────────────────────────────────────────────────────────────────┐
│ DIRECTIONAL ACCURACY: {m.directional_accuracy:.1%} ({m.correct_predictions}/{m.total_scenarios})
├────────────────────────────────────────────────────────────────────┤
│ CONVERGENCE: {m.avg_rounds_to_conclusion:.1f} rounds avg
├────────────────────────────────────────────────────────────────────┤
│ CONCLUSION REASONS: {dict(m.conclusion_reasons)}
└────────────────────────────────────────────────────────────────────┘

ACCURACY BY CATEGORY:
{chr(10).join(f"  - {c}: {a:.1%}" for c, a in m.accuracy_by_category.items())}

CONFUSION MATRIX:
{chr(10).join(f"  {k}: {v}" for k, v in m.confusion_matrix.items())}
""")
    
    def save_results(self, results: List[ScenarioResult], metrics: AggregateMetrics, output_dir: Path):
        """Save results to files"""
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save results
        results_data = [asdict(r) for r in results]
        with open(output_dir / f"results_actual_{ts}.json", 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        # Save metrics
        with open(output_dir / f"metrics_actual_{ts}.json", 'w') as f:
            json.dump(asdict(metrics), f, indent=2)
        
        print(f"\n📄 Saved to {output_dir}/")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Bull-Bear using ACTUAL system (via Docker API)"
    )
    parser.add_argument("--datasets", default="datasets", help="Datasets directory")
    parser.add_argument("--max-scenarios", type=int, help="Limit scenarios")
    parser.add_argument("--max-rounds", type=int, default=5, help="Max debate rounds")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Bull-Bear API URL")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--no-save", action="store_true", help="Skip saving")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show API responses")
    
    args = parser.parse_args()
    
    runner = EvaluationRunner(
        max_rounds=args.max_rounds,
        api_url=args.api_url,
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
