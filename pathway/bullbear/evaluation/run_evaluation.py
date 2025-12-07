#!/usr/bin/env python3
"""
Bull-Bear Standalone Evaluation Pipeline
=========================================

This is a STANDALONE evaluation script that runs the Bull-Bear debate
without requiring the full pathway stack. It uses the core debate logic
directly with dataset-provided reports.

Usage:
    source .venv/bin/activate
    python run_evaluation.py --datasets datasets/
    python run_evaluation.py --max-scenarios 5 --max-rounds 3
"""

import os
import sys
import json
import argparse
import time
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# Setup paths
EVAL_DIR = Path(__file__).parent
BULLBEAR_DIR = EVAL_DIR.parent
PATHWAY_DIR = BULLBEAR_DIR.parent

sys.path.insert(0, str(PATHWAY_DIR))
sys.path.insert(0, str(BULLBEAR_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(EVAL_DIR / ".env")
except ImportError:
    pass

# Import OpenAI for LLM calls
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ openai not available - install with: uv pip install openai")


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
class DebatePointMetrics:
    """Metrics for a single debate point"""
    party: str
    content: str
    confidence: float
    evidence_count: int
    reports_cited: List[str]
    toulmin: ToulminScore
    is_counter: bool = False
    word_count: int = 0


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
    total_points: int
    bull_points: int
    bear_points: int
    rounds_to_conclusion: int
    conclusion_reason: str
    point_metrics: List[DebatePointMetrics] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all scenarios"""
    total_scenarios: int = 0
    correct_predictions: int = 0
    directional_accuracy: float = 0.0
    accuracy_by_category: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    avg_toulmin_score: float = 0.0
    avg_bull_toulmin: float = 0.0
    avg_bear_toulmin: float = 0.0
    avg_rounds_to_conclusion: float = 0.0
    conclusion_reasons: Dict[str, int] = field(default_factory=dict)
    avg_confidence_gap: float = 0.0
    bull_wins: int = 0
    bear_wins: int = 0
    draws: int = 0
    bull_elo: float = 1500.0
    bear_elo: float = 1500.0
    avg_evidence_per_point: float = 0.0
    avg_bull_evidence: float = 0.0
    avg_bear_evidence: float = 0.0
    report_citation_counts: Dict[str, int] = field(default_factory=dict)
    avg_reports_cited_per_point: float = 0.0


# ============================================================
# ANALYZERS
# ============================================================

class ToulminAnalyzer:
    """Analyzes argument quality using Toulmin Model"""
    
    CLAIM_PATTERNS = [
        r'\b(should|recommend|suggest|believe|argue|position)\b',
        r'\b(bullish|bearish|buy|sell|hold)\b',
        r'\b(will|expect|predict|forecast)\b',
    ]
    
    EVIDENCE_PATTERNS = [
        r'\b(\d+%|\$[\d,]+|[0-9]+x)\b',
        r'\b(according to|based on|data shows|reports indicate)\b',
        r'\b(earnings|revenue|growth|margin|ratio)\b',
    ]
    
    WARRANT_PATTERNS = [
        r'\b(because|therefore|thus|hence|consequently)\b',
        r'\b(this means|this suggests|this indicates)\b',
        r'\b(as a result|due to|given that)\b',
    ]
    
    BACKING_PATTERNS = [
        r'\b(historically|traditionally|typically)\b',
        r'\b(in the past|previously|before)\b',
    ]
    
    QUALIFIER_PATTERNS = [
        r'\b(probably|likely|possibly|perhaps)\b',
        r'\b(confidence|certainty|uncertain)\b',
        r'\b(may|might|could)\b',
    ]
    
    REBUTTAL_PATTERNS = [
        r'\b(however|although|despite|nevertheless)\b',
        r'\b(counter|against|oppose|refute)\b',
        r'\b(risk|concern|caveat|limitation)\b',
    ]
    
    def analyze(self, content: str, evidence: List[str] = None) -> ToulminScore:
        content_lower = content.lower()
        evidence_text = " ".join(evidence or []).lower()
        full_text = content_lower + " " + evidence_text
        
        def has_pattern(patterns, text):
            return any(re.search(p, text, re.I) for p in patterns)
        
        return ToulminScore(
            claim_present=has_pattern(self.CLAIM_PATTERNS, content_lower),
            evidence_present=has_pattern(self.EVIDENCE_PATTERNS, full_text) or len(evidence or []) > 0,
            warrant_present=has_pattern(self.WARRANT_PATTERNS, content_lower),
            backing_present=has_pattern(self.BACKING_PATTERNS, full_text),
            qualifier_present=has_pattern(self.QUALIFIER_PATTERNS, content_lower),
            rebuttal_addressed=has_pattern(self.REBUTTAL_PATTERNS, content_lower),
        )


class ReportCoverageAnalyzer:
    """Analyzes which reports are cited"""
    
    REPORT_KEYWORDS = {
        "news": ["news", "headline", "announced", "reported", "press"],
        "sentiment": ["sentiment", "social", "twitter", "reddit", "bullish", "bearish"],
        "market": ["technical", "rsi", "macd", "moving average", "support", "resistance", "price"],
        "fundamental": ["p/e", "earnings", "revenue", "valuation", "fundamental", "ratio"]
    }
    
    def analyze(self, content: str, evidence: List[str] = None) -> List[str]:
        full_text = (content + " " + " ".join(evidence or [])).lower()
        cited = []
        for report_type, keywords in self.REPORT_KEYWORDS.items():
            if any(kw in full_text for kw in keywords):
                cited.append(report_type)
        return cited


class EloCalculator:
    """Calculate Elo ratings for Bull vs Bear"""
    
    def __init__(self, k_factor: float = 32):
        self.k_factor = k_factor
    
    def update_ratings(self, bull_elo: float, bear_elo: float, winner: str) -> Tuple[float, float]:
        expected_bull = 1 / (1 + 10 ** ((bear_elo - bull_elo) / 400))
        expected_bear = 1 - expected_bull
        
        actual = {"bull": (1.0, 0.0), "bear": (0.0, 1.0), "draw": (0.5, 0.5)}
        actual_bull, actual_bear = actual.get(winner, (0.5, 0.5))
        
        new_bull = bull_elo + self.k_factor * (actual_bull - expected_bull)
        new_bear = bear_elo + self.k_factor * (actual_bear - expected_bear)
        return new_bull, new_bear
    
    def determine_winner(self, recommendation: str, expected: str) -> str:
        if recommendation == expected:
            return "bull" if recommendation == "BUY" else ("bear" if recommendation == "SELL" else "draw")
        else:
            return "bull" if expected == "BUY" else ("bear" if expected == "SELL" else "draw")


# ============================================================
# STANDALONE DEBATE RUNNER
# ============================================================

class StandaloneDebateRunner:
    """Runs debates using direct LLM calls without pathway dependencies"""
    
    # Prompts enforce Toulmin Model argumentation structure
    BULL_PROMPT = """You are an OPTIMISTIC investment analyst presenting a BULLISH argument for {symbol}.

## YOUR TASK
Build the strongest possible BULLISH case using the Toulmin argumentation model.

## TOULMIN MODEL REQUIREMENTS
Your argument MUST include ALL of these components:

1. **CLAIM**: A clear, specific assertion that this stock should be BOUGHT
   - Be definitive: "Investors should buy {symbol} because..."
   - Include a price target or expected return if possible

2. **EVIDENCE**: Concrete, quantified data points that support your claim
   - Use specific numbers: percentages, dollar amounts, ratios
   - Reference data from the reports provided
   - Minimum 2-3 strong evidence points

3. **WARRANT**: Logical reasoning that connects your evidence to your claim
   - Explain WHY your evidence supports buying
   - Use phrases like "This matters because...", "This indicates..."

4. **QUALIFIER**: Acknowledge your confidence level honestly
   - State conditions: "This is likely if...", "With high probability..."
   - Quantify: "I am 80% confident because..."

5. **REBUTTAL**: Briefly acknowledge and counter the main bear argument
   - "While bears might argue X, this is mitigated by Y..."
   - Shows you've considered the other side

## REPORTS
{reports}

## DEBATE HISTORY
{history}

{counter_instruction}

## OUTPUT FORMAT
Generate a structured bullish argument. Output JSON:
{{
    "claim": "Your specific, definitive claim for buying this stock",
    "evidence": ["Quantified evidence point 1", "Quantified evidence point 2", "Quantified evidence point 3"],
    "warrant": "Logical explanation of why evidence supports the claim",
    "qualifier": "Confidence level and conditions (e.g., 'High confidence assuming market stability')",
    "rebuttal": "Acknowledgment and counter to main bear concern",
    "confidence": 0.0-1.0
}}"""

    BEAR_PROMPT = """You are a CAUTIOUS investment analyst presenting a BEARISH argument for {symbol}.

## YOUR TASK
Build the strongest possible BEARISH case using the Toulmin argumentation model.

## TOULMIN MODEL REQUIREMENTS
Your argument MUST include ALL of these components:

1. **CLAIM**: A clear, specific assertion that this stock should be SOLD or avoided
   - Be definitive: "Investors should sell/avoid {symbol} because..."
   - Include downside risk or price target if possible

2. **EVIDENCE**: Concrete, quantified data points that support your claim
   - Use specific numbers: percentages, dollar amounts, ratios
   - Reference data from the reports provided
   - Minimum 2-3 strong evidence points

3. **WARRANT**: Logical reasoning that connects your evidence to your claim
   - Explain WHY your evidence supports caution/selling
   - Use phrases like "This is concerning because...", "This signals..."

4. **QUALIFIER**: Acknowledge your confidence level honestly
   - State conditions: "This risk materializes if...", "Probability of decline..."
   - Quantify: "I am 75% confident the downside exceeds upside..."

5. **REBUTTAL**: Briefly acknowledge and counter the main bull argument
   - "While bulls point to X, this doesn't offset Y because..."
   - Shows you've considered the other side

## REPORTS
{reports}

## DEBATE HISTORY
{history}

{counter_instruction}

## OUTPUT FORMAT
Generate a structured bearish argument. Output JSON:
{{
    "claim": "Your specific, definitive claim against this stock",
    "evidence": ["Quantified evidence point 1", "Quantified evidence point 2", "Quantified evidence point 3"],
    "warrant": "Logical explanation of why evidence supports caution/selling",
    "qualifier": "Confidence level and conditions (e.g., 'Moderate confidence given earnings uncertainty')",
    "rebuttal": "Acknowledgment and counter to main bull argument",
    "confidence": 0.0-1.0
}}"""

    FACILITATOR_PROMPT = """You are a senior investment committee FACILITATOR making the final recommendation for {symbol}.

## YOUR ROLE
You have heard arguments from both Bull (optimistic) and Bear (cautious) analysts.
Your job is to:
1. Evaluate the QUALITY of each argument (not just agree with the majority)
2. Determine which side made a more CONVINCING case
3. Render a DECISIVE verdict

## DEBATE TRANSCRIPT
{debate_points}

## EVALUATION CRITERIA

Score each side on (1-5 scale):
1. **Claim Clarity**: How clear and specific was their recommendation?
2. **Evidence Quality**: How quantified and verifiable were their data points?
3. **Warrant Strength**: How logical was the connection between evidence and claim?
4. **Qualifier Honesty**: Did they appropriately acknowledge uncertainty?
5. **Rebuttal Effectiveness**: Did they address the opposing view convincingly?

## DECISION RULES
- If BULL total score > BEAR total score + 2: Recommend BUY
- If BEAR total score > BULL total score + 2: Recommend SELL
- If scores are within 2 points: Recommend HOLD

## OUTPUT FORMAT
{{
    "bull_scores": {{
        "claim_clarity": 1-5,
        "evidence_quality": 1-5,
        "warrant_strength": 1-5,
        "qualifier_honesty": 1-5,
        "rebuttal_effectiveness": 1-5,
        "total": sum
    }},
    "bear_scores": {{
        "claim_clarity": 1-5,
        "evidence_quality": 1-5,
        "warrant_strength": 1-5,
        "qualifier_honesty": 1-5,
        "rebuttal_effectiveness": 1-5,
        "total": sum
    }},
    "recommendation": "BUY" or "SELL" or "HOLD",
    "winning_side": "bull" or "bear" or "neither",
    "reasoning": "2-3 sentences explaining which arguments were most compelling and why",
    "confidence": 0.0-1.0
}}"""

    # Prompt for LLM-based Toulmin scoring
    TOULMIN_SCORER_PROMPT = """You are an argumentation quality analyst scoring a debate point using the Toulmin Model.

## ARGUMENT TO SCORE
Party: {party}
Content: {content}
Evidence provided: {evidence}

## SCORING CRITERIA (0.0 to 1.0 each)

1. **claim_score**: How clear and specific is the claim/recommendation?
   - 0.0: No clear claim
   - 0.5: Vague or implicit claim
   - 1.0: Crystal clear, specific, actionable claim

2. **evidence_score**: How well-supported with quantified data?
   - 0.0: No data or evidence
   - 0.5: Some data but vague or unquantified
   - 1.0: Multiple specific, quantified data points

3. **warrant_score**: How logical is the reasoning?
   - 0.0: No explanation of why evidence supports claim
   - 0.5: Some reasoning but gaps in logic
   - 1.0: Clear, logical connection between evidence and claim

4. **backing_score**: Is there historical/authoritative support?
   - 0.0: No historical context or authority cited
   - 0.5: Some reference to past or authority
   - 1.0: Strong historical patterns or credible sources cited

5. **qualifier_score**: Is uncertainty appropriately acknowledged?
   - 0.0: Overconfident with no caveats
   - 0.5: Some acknowledgment of uncertainty
   - 1.0: Honest, calibrated confidence with conditions stated

6. **rebuttal_score**: Does it address counterarguments?
   - 0.0: Ignores opposing view entirely
   - 0.5: Mentions but doesn't convincingly counter
   - 1.0: Acknowledges and effectively counters opposing view

## OUTPUT JSON ONLY
{{
    "claim_score": 0.0-1.0,
    "evidence_score": 0.0-1.0,
    "warrant_score": 0.0-1.0,
    "backing_score": 0.0-1.0,
    "qualifier_score": 0.0-1.0,
    "rebuttal_score": 0.0-1.0,
    "overall_score": weighted average,
    "brief_reasoning": "One sentence summary"
}}"""

    def __init__(self, max_rounds: int = 3, model: str = "google/gemini-2.5-flash-lite", verbose: bool = False):
        self.max_rounds = max_rounds
        self.model = model
        self.verbose = verbose
        self.client = None
        
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
    
    def _print_box(self, title: str, content: str, color: str = ""):
        """Print content in a styled box"""
        colors = {
            "blue": "\033[94m",
            "green": "\033[92m", 
            "yellow": "\033[93m",
            "red": "\033[91m",
            "cyan": "\033[96m",
            "magenta": "\033[95m",
            "reset": "\033[0m",
            "bold": "\033[1m",
            "dim": "\033[2m"
        }
        c = colors.get(color, "")
        reset = colors["reset"]
        bold = colors["bold"]
        dim = colors["dim"]
        
        width = 80
        print(f"\n{c}{'─'*width}{reset}")
        print(f"{c}{bold}│ {title}{reset}")
        print(f"{c}{'─'*width}{reset}")
        
        # Truncate long content
        lines = content.split('\n')
        for i, line in enumerate(lines[:30]):  # Max 30 lines
            if len(line) > width - 4:
                line = line[:width-7] + "..."
            print(f"{dim}│{reset} {line}")
        
        if len(lines) > 30:
            print(f"{dim}│ ... ({len(lines) - 30} more lines){reset}")
        
        print(f"{c}{'─'*width}{reset}\n")
    
    def _call_llm(self, prompt: str, system: str = "You are a financial analyst.", role_name: str = "LLM") -> Dict:
        """Make LLM call and parse JSON response"""
        if not self.client:
            return {"point": "Mock argument", "supporting_evidence": [], "confidence": 0.5}
        
        # Show prompt if verbose
        if self.verbose:
            role_colors = {"BULL": "green", "BEAR": "red", "FACILITATOR": "cyan"}
            color = role_colors.get(role_name.upper(), "blue")
            self._print_box(f"📤 PROMPT → {role_name}", prompt[:2000], color)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            content = response.choices[0].message.content
            
            # Show response if verbose
            if self.verbose:
                self._print_box(f"📥 RESPONSE ← {role_name}", content, color)
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            parsed = json.loads(content.strip())
            
            # Show parsed result if verbose
            if self.verbose:
                summary = f"Point: {parsed.get('point', parsed.get('recommendation', 'N/A'))[:100]}..."
                if 'confidence' in parsed:
                    summary += f"\nConfidence: {parsed['confidence']}"
                if 'recommendation' in parsed:
                    summary += f"\nRecommendation: {parsed['recommendation']}"
                self._print_box(f"✅ PARSED ({role_name})", summary, "yellow")
            
            return parsed
        except Exception as e:
            if self.verbose:
                self._print_box(f"❌ ERROR ({role_name})", str(e), "red")
            print(f"      LLM error: {e}")
            return {"point": f"Error: {e}", "supporting_evidence": [], "confidence": 0.5}
    
    def run_debate(self, scenario: Dict) -> Dict:
        """Run a complete debate on a scenario"""
        
        symbol = scenario.get("symbol", "TEST")
        inputs = scenario.get("inputs", {})
        
        # Format reports
        reports = f"""
NEWS REPORT:
{inputs.get('news_report', 'No news available')[:1500]}

SENTIMENT REPORT:
{inputs.get('sentiment_report', 'No sentiment available')[:1500]}

MARKET REPORT:
{inputs.get('market_report', 'No market data available')[:1500]}

FUNDAMENTAL REPORT:
{inputs.get('fundamental_report', 'No fundamentals available')[:1500]}
"""
        
        debate_points = []
        history = "No previous points yet."
        
        # Run debate rounds
        for round_num in range(self.max_rounds):
            # Bull's turn
            last_bear_claim = debate_points[-1].get('claim', debate_points[-1].get('content', '')) if debate_points else ""
            counter = f"Counter the Bear's argument: {last_bear_claim}" if debate_points else ""
            bull_prompt = self.BULL_PROMPT.format(
                symbol=symbol,
                reports=reports,
                history=history,
                counter_instruction=counter
            )
            
            bull_response = self._call_llm(bull_prompt, role_name="BULL")
            
            # Handle both old format (point) and new Toulmin format (claim)
            bull_claim = bull_response.get("claim", bull_response.get("point", ""))
            bull_evidence = bull_response.get("evidence", bull_response.get("supporting_evidence", []))
            
            bull_point = {
                "id": str(uuid.uuid4())[:8],
                "party": "bull",
                "content": bull_claim,
                "claim": bull_claim,
                "evidence": bull_evidence,
                "supporting_evidence": bull_evidence,  # Keep for backward compat
                "warrant": bull_response.get("warrant", ""),
                "qualifier": bull_response.get("qualifier", ""),
                "rebuttal": bull_response.get("rebuttal", ""),
                "confidence": bull_response.get("confidence", 0.5),
                "counter_to": debate_points[-1]["id"] if debate_points else None
            }
            debate_points.append(bull_point)
            
            # Bear's turn
            counter = f"Counter the Bull's argument: {bull_claim}"
            bear_prompt = self.BEAR_PROMPT.format(
                symbol=symbol,
                reports=reports,
                history=self._format_history(debate_points),
                counter_instruction=counter
            )
            
            bear_response = self._call_llm(bear_prompt, role_name="BEAR")
            
            # Handle both formats
            bear_claim = bear_response.get("claim", bear_response.get("point", ""))
            bear_evidence = bear_response.get("evidence", bear_response.get("supporting_evidence", []))
            
            bear_point = {
                "id": str(uuid.uuid4())[:8],
                "party": "bear",
                "content": bear_claim,
                "claim": bear_claim,
                "evidence": bear_evidence,
                "supporting_evidence": bear_evidence,
                "warrant": bear_response.get("warrant", ""),
                "qualifier": bear_response.get("qualifier", ""),
                "rebuttal": bear_response.get("rebuttal", ""),
                "confidence": bear_response.get("confidence", 0.5),
                "counter_to": bull_point["id"]
            }
            debate_points.append(bear_point)
            
            history = self._format_history(debate_points)
            
            # Check for early convergence (both low confidence)
            if bull_point["confidence"] < 0.3 and bear_point["confidence"] < 0.3:
                break
        
        # Facilitator generates final recommendation
        facilitator_prompt = self.FACILITATOR_PROMPT.format(
            symbol=symbol,
            debate_points=self._format_history_detailed(debate_points)
        )
        
        facilitator_response = self._call_llm(facilitator_prompt, role_name="FACILITATOR")
        recommendation = facilitator_response.get("recommendation", "HOLD").upper()
        
        # Extract facilitator scores if available
        bull_scores = facilitator_response.get("bull_scores", {})
        bear_scores = facilitator_response.get("bear_scores", {})
        
        return {
            "debate_points": debate_points,
            "recommendation": recommendation,
            "round_number": len(debate_points) // 2,
            "conclusion_reason": "max_rounds" if len(debate_points) >= self.max_rounds * 2 else "convergence",
            "facilitator_response": facilitator_response,
            "bull_total_score": bull_scores.get("total", 0),
            "bear_total_score": bear_scores.get("total", 0),
            "winning_side": facilitator_response.get("winning_side", "neither")
        }
    
    def _format_history(self, points: List[Dict]) -> str:
        """Brief history for prompts"""
        if not points:
            return "No debate history yet."
        
        lines = []
        for p in points[-4:]:  # Last 4 points
            party = p["party"].upper()
            claim = p.get("claim", p.get("content", ""))[:150]
            conf = p.get("confidence", 0.5)
            lines.append(f"[{party}] (conf: {conf:.0%}): {claim}")
        
        return "\n".join(lines)
    
    def _format_history_detailed(self, points: List[Dict]) -> str:
        """Detailed history for facilitator showing Toulmin components"""
        if not points:
            return "No debate points."
        
        lines = []
        for i, p in enumerate(points, 1):
            party = p["party"].upper()
            lines.append(f"\n### Argument {i} ({party})")
            lines.append(f"**Claim**: {p.get('claim', p.get('content', 'N/A'))}")
            
            evidence = p.get('evidence', p.get('supporting_evidence', []))
            if evidence:
                lines.append(f"**Evidence**: {'; '.join(str(e)[:100] for e in evidence[:3])}")
            
            if p.get('warrant'):
                lines.append(f"**Warrant**: {p['warrant'][:200]}")
            
            if p.get('qualifier'):
                lines.append(f"**Qualifier**: {p['qualifier'][:100]}")
            
            if p.get('rebuttal'):
                lines.append(f"**Rebuttal**: {p['rebuttal'][:150]}")
            
            lines.append(f"**Confidence**: {p.get('confidence', 0.5):.0%}")
        
        return "\n".join(lines)
    
    def score_toulmin_llm(self, point: Dict) -> Dict:
        """Use LLM to score a debate point on Toulmin criteria"""
        if not self.client:
            return {"overall_score": 0.5}
        
        # Combine all content for scoring
        content = f"""
Claim: {point.get('claim', point.get('content', ''))}
Warrant: {point.get('warrant', 'Not provided')}
Qualifier: {point.get('qualifier', 'Not provided')}
Rebuttal: {point.get('rebuttal', 'Not provided')}
"""
        evidence = point.get('evidence', point.get('supporting_evidence', []))
        
        prompt = self.TOULMIN_SCORER_PROMPT.format(
            party=point.get('party', 'unknown').upper(),
            content=content,
            evidence=json.dumps(evidence) if evidence else "None provided"
        )
        
        try:
            result = self._call_llm(prompt, role_name="SCORER")
            
            # Calculate overall score (weighted average)
            weights = {
                "claim_score": 0.25,
                "evidence_score": 0.25,
                "warrant_score": 0.20,
                "backing_score": 0.10,
                "qualifier_score": 0.10,
                "rebuttal_score": 0.10
            }
            
            overall = sum(
                result.get(k, 0.5) * w 
                for k, w in weights.items()
            )
            result["overall_score"] = overall
            return result
            
        except Exception as e:
            return {"overall_score": 0.5, "error": str(e)}


# ============================================================
# EVALUATION RUNNER
# ============================================================

class EvaluationRunner:
    """Runs evaluation pipeline"""
    
    def __init__(self, max_rounds: int = 3, model: str = None, verbose: bool = False, use_llm_scoring: bool = False):
        self.verbose = verbose
        self.use_llm_scoring = use_llm_scoring
        self.debate_runner = StandaloneDebateRunner(
            max_rounds=max_rounds,
            model=model or "google/gemini-2.5-flash-lite",
            verbose=verbose
        )
        self.toulmin = ToulminAnalyzer()
        self.coverage = ReportCoverageAnalyzer()
        self.elo = EloCalculator()
    
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
        symbol = scenario.get("symbol", "TEST")
        category = scenario.get("category", "unknown")
        expected = scenario.get("ground_truth", {}).get("expected_recommendation", "HOLD").upper()
        
        print(f"  📊 {dataset_id} ({symbol})", end="", flush=True)
        
        start = time.time()
        errors = []
        
        try:
            result = self.debate_runner.run_debate(scenario)
            exec_time = time.time() - start
            
            actual = result["recommendation"].upper()
            is_correct = actual == expected
            
            # Analyze points
            point_metrics = []
            for p in result["debate_points"]:
                evidence = p.get("evidence", p.get("supporting_evidence", []))
                content = p.get("claim", p.get("content", ""))
                
                # Use LLM scoring if enabled, otherwise regex
                if self.use_llm_scoring:
                    llm_scores = self.debate_runner.score_toulmin_llm(p)
                    toulmin = ToulminScore(
                        claim_present=llm_scores.get("claim_score", 0) > 0.3,
                        evidence_present=llm_scores.get("evidence_score", 0) > 0.3,
                        warrant_present=llm_scores.get("warrant_score", 0) > 0.3,
                        backing_present=llm_scores.get("backing_score", 0) > 0.3,
                        qualifier_present=llm_scores.get("qualifier_score", 0) > 0.3,
                        rebuttal_addressed=llm_scores.get("rebuttal_score", 0) > 0.3,
                    )
                    # Override score with LLM-calculated score
                    toulmin._llm_score = llm_scores.get("overall_score", 0.5)
                else:
                    toulmin = self.toulmin.analyze(content, evidence)
                
                point_metrics.append(DebatePointMetrics(
                    party=p["party"],
                    content=content,
                    confidence=p.get("confidence", 0.5),
                    evidence_count=len(evidence),
                    reports_cited=self.coverage.analyze(content, evidence),
                    toulmin=toulmin,
                    is_counter=p.get("counter_to") is not None,
                    word_count=len(content.split())
                ))
            
            status = "✅" if is_correct else "❌"
            print(f" {status} Exp:{expected} Got:{actual} ({exec_time:.1f}s)")
            
            return ScenarioResult(
                dataset_id=dataset_id,
                symbol=symbol,
                category=category,
                expected_recommendation=expected,
                actual_recommendation=actual,
                is_correct=is_correct,
                total_rounds=result["round_number"],
                total_points=len(result["debate_points"]),
                bull_points=len([p for p in result["debate_points"] if p["party"] == "bull"]),
                bear_points=len([p for p in result["debate_points"] if p["party"] == "bear"]),
                rounds_to_conclusion=result["round_number"],
                conclusion_reason=result["conclusion_reason"],
                point_metrics=point_metrics,
                execution_time_seconds=exec_time,
                errors=errors
            )
            
        except Exception as e:
            print(f" ❌ Error: {e}")
            return ScenarioResult(
                dataset_id=dataset_id, symbol=symbol, category=category,
                expected_recommendation=expected, actual_recommendation="ERROR",
                is_correct=False, total_rounds=0, total_points=0,
                bull_points=0, bear_points=0, rounds_to_conclusion=0,
                conclusion_reason="error", execution_time_seconds=time.time()-start,
                errors=[str(e)]
            )
    
    def compute_aggregate_metrics(self, results: List[ScenarioResult]) -> AggregateMetrics:
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
        
        # Toulmin scores
        all_t, bull_t, bear_t = [], [], []
        for r in valid:
            for pm in r.point_metrics:
                s = pm.toulmin.score
                all_t.append(s)
                (bull_t if pm.party == "bull" else bear_t).append(s)
        
        metrics.avg_toulmin_score = sum(all_t)/len(all_t) if all_t else 0
        metrics.avg_bull_toulmin = sum(bull_t)/len(bull_t) if bull_t else 0
        metrics.avg_bear_toulmin = sum(bear_t)/len(bear_t) if bear_t else 0
        
        # Convergence
        rounds = [r.rounds_to_conclusion for r in valid]
        metrics.avg_rounds_to_conclusion = sum(rounds)/len(rounds) if rounds else 0
        for r in valid:
            metrics.conclusion_reasons[r.conclusion_reason] = metrics.conclusion_reasons.get(r.conclusion_reason, 0) + 1
        
        # Confidence gap
        gaps = []
        for r in valid:
            bc = [pm.confidence for pm in r.point_metrics if pm.party == "bull"]
            ec = [pm.confidence for pm in r.point_metrics if pm.party == "bear"]
            if bc and ec:
                gaps.append(abs(sum(bc)/len(bc) - sum(ec)/len(ec)))
        metrics.avg_confidence_gap = sum(gaps)/len(gaps) if gaps else 0
        
        # Elo
        bull_elo, bear_elo = 1500.0, 1500.0
        for r in valid:
            winner = self.elo.determine_winner(r.actual_recommendation, r.expected_recommendation)
            if winner == "bull": metrics.bull_wins += 1
            elif winner == "bear": metrics.bear_wins += 1
            else: metrics.draws += 1
            bull_elo, bear_elo = self.elo.update_ratings(bull_elo, bear_elo, winner)
        metrics.bull_elo, metrics.bear_elo = bull_elo, bear_elo
        
        # Evidence density
        all_e, bull_e, bear_e = [], [], []
        for r in valid:
            for pm in r.point_metrics:
                all_e.append(pm.evidence_count)
                (bull_e if pm.party == "bull" else bear_e).append(pm.evidence_count)
        metrics.avg_evidence_per_point = sum(all_e)/len(all_e) if all_e else 0
        metrics.avg_bull_evidence = sum(bull_e)/len(bull_e) if bull_e else 0
        metrics.avg_bear_evidence = sum(bear_e)/len(bear_e) if bear_e else 0
        
        # Report coverage
        counts = defaultdict(int)
        total = 0
        for r in valid:
            for pm in r.point_metrics:
                for rpt in pm.reports_cited:
                    counts[rpt] += 1
                    total += 1
        metrics.report_citation_counts = dict(counts)
        total_pts = sum(len(r.point_metrics) for r in valid)
        metrics.avg_reports_cited_per_point = total/total_pts if total_pts else 0
        
        return metrics
    
    def run_evaluation(self, datasets_dir: Path, max_scenarios: int = None):
        print("=" * 70)
        print("🚀 BULL-BEAR STANDALONE EVALUATION")
        print("=" * 70)
        
        datasets = self.load_datasets(datasets_dir)
        print(f"\n📁 Loaded {len(datasets)} scenarios")
        
        if max_scenarios:
            datasets = datasets[:max_scenarios]
            print(f"   Limited to {max_scenarios}")
        
        print("\n🔄 Running debates...\n")
        results = [self.run_single_scenario(s) for s in datasets]
        
        print("\n📊 Computing metrics...")
        metrics = self.compute_aggregate_metrics(results)
        
        return results, metrics
    
    def save_results(self, results: List[ScenarioResult], metrics: AggregateMetrics, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save results
        results_data = []
        for r in results:
            d = asdict(r)
            for pm in d.get("point_metrics", []):
                if "toulmin" in pm and hasattr(pm["toulmin"], '__dataclass_fields__'):
                    pm["toulmin"] = asdict(pm["toulmin"])
            results_data.append(d)
        
        with open(output_dir / f"results_{ts}.json", 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        with open(output_dir / f"metrics_{ts}.json", 'w') as f:
            json.dump(asdict(metrics), f, indent=2)
        
        # Markdown report
        report = self.generate_report(results, metrics)
        with open(output_dir / f"report_{ts}.md", 'w') as f:
            f.write(report)
        
        print(f"\n📄 Saved to {output_dir}/")
    
    def generate_report(self, results: List[ScenarioResult], m: AggregateMetrics) -> str:
        return f"""# Bull-Bear Evaluation Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

| Metric | Value |
|--------|-------|
| Scenarios | {m.total_scenarios} |
| Correct | {m.correct_predictions} |
| **Directional Accuracy** | **{m.directional_accuracy:.1%}** |

---

## 1. Directional Accuracy 🎯

**{m.directional_accuracy:.1%}** ({m.correct_predictions}/{m.total_scenarios})

### By Category
{chr(10).join(f"- {c}: {a:.1%}" for c, a in m.accuracy_by_category.items())}

---

## 2. Argumentation Quality (Toulmin) 📝

| Party | Score |
|-------|-------|
| Overall | {m.avg_toulmin_score:.2f} |
| Bull | {m.avg_bull_toulmin:.2f} |
| Bear | {m.avg_bear_toulmin:.2f} |

---

## 3. Convergence Rate ⏱️

Avg rounds: **{m.avg_rounds_to_conclusion:.1f}**

---

## 4. Consensus Score 🤝

Confidence gap: **{m.avg_confidence_gap:.2f}**

---

## 5. Elo Rating ♟️

| Party | Wins | Elo |
|-------|------|-----|
| Bull 🐂 | {m.bull_wins} | {m.bull_elo:.0f} |
| Bear 🐻 | {m.bear_wins} | {m.bear_elo:.0f} |
| Draws | {m.draws} | - |

---

## 6. Evidence Density 📚

| Party | Avg Items |
|-------|----------|
| Bull | {m.avg_bull_evidence:.1f} |
| Bear | {m.avg_bear_evidence:.1f} |

---

## 7. Report Coverage 📰

{chr(10).join(f"- {r}: {c}" for r, c in m.report_citation_counts.items())}

---

## Results Table

| ID | Symbol | Expected | Actual | ✓ | Rounds |
|----|--------|----------|--------|---|--------|
{chr(10).join(f"| {r.dataset_id} | {r.symbol} | {r.expected_recommendation} | {r.actual_recommendation} | {'✅' if r.is_correct else '❌'} | {r.total_rounds} |" for r in results)}
"""

    def print_summary(self, m: AggregateMetrics):
        print(f"""
{'='*70}
📊 EVALUATION RESULTS
{'='*70}

┌────────────────────────────────────────────────────────────────────┐
│ 1. DIRECTIONAL ACCURACY: {m.directional_accuracy:.1%} ({m.correct_predictions}/{m.total_scenarios})
├────────────────────────────────────────────────────────────────────┤
│ 2. TOULMIN QUALITY: {m.avg_toulmin_score:.2f} (Bull: {m.avg_bull_toulmin:.2f}, Bear: {m.avg_bear_toulmin:.2f})
├────────────────────────────────────────────────────────────────────┤
│ 3. CONVERGENCE: {m.avg_rounds_to_conclusion:.1f} rounds avg
├────────────────────────────────────────────────────────────────────┤
│ 4. CONSENSUS (conf gap): {m.avg_confidence_gap:.2f}
├────────────────────────────────────────────────────────────────────┤
│ 5. ELO: Bull {m.bull_elo:.0f} ({m.bull_wins}W) | Bear {m.bear_elo:.0f} ({m.bear_wins}W)
├────────────────────────────────────────────────────────────────────┤
│ 6. EVIDENCE: {m.avg_evidence_per_point:.1f}/point (Bull: {m.avg_bull_evidence:.1f}, Bear: {m.avg_bear_evidence:.1f})
├────────────────────────────────────────────────────────────────────┤
│ 7. REPORT COVERAGE: {m.avg_reports_cited_per_point:.1f} reports/point
└────────────────────────────────────────────────────────────────────┘
""")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Evaluate Bull-Bear (Standalone)")
    parser.add_argument("--datasets", default="datasets", help="Datasets directory")
    parser.add_argument("--max-scenarios", type=int, help="Limit scenarios")
    parser.add_argument("--max-rounds", type=int, default=3, help="Max debate rounds")
    parser.add_argument("--model", default="google/gemini-2.5-flash-lite", help="LLM model")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--no-save", action="store_true", help="Skip saving")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show prompts and responses")
    parser.add_argument("--llm-scoring", action="store_true", help="Use LLM for Toulmin scoring (slower but more accurate)")
    
    args = parser.parse_args()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY not set - using mock responses")
        print("   Set it: export OPENAI_API_KEY=your_openrouter_key")
    
    if args.verbose:
        print("🔍 VERBOSE MODE: Showing all prompts and responses\n")
    
    if args.llm_scoring:
        print("🧠 LLM SCORING: Using LLM for Toulmin quality analysis\n")
    
    runner = EvaluationRunner(
        max_rounds=args.max_rounds, 
        model=args.model, 
        verbose=args.verbose,
        use_llm_scoring=args.llm_scoring
    )
    datasets_dir = EVAL_DIR / args.datasets
    
    if not datasets_dir.exists():
        print(f"❌ Not found: {datasets_dir}")
        sys.exit(1)
    
    results, metrics = runner.run_evaluation(datasets_dir, args.max_scenarios)
    runner.print_summary(metrics)
    
    if not args.no_save:
        runner.save_results(results, metrics, EVAL_DIR / args.output)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
