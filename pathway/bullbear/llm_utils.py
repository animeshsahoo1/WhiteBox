"""
LLM Utilities for Bull-Bear Debate
Handles LLM interactions with proper prompting and parsing
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .config import LLMConfig, get_config

logger = logging.getLogger(__name__)

# Mock mode for testing without API keys
USE_MOCK_LLM = os.environ.get("BULL_BEAR_MOCK_LLM", "false").lower() == "true"

# Use OpenAI SDK (works with OpenRouter since it's OpenAI-compatible)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def _generate_mock_response(messages: List[Dict[str, str]], json_mode: bool = False) -> str:
    """Generate mock LLM responses for testing."""
    last_msg = messages[-1]["content"] if messages else ""
    
    if "bull" in last_msg.lower() or "bullish" in last_msg.lower():
        mock_data = {
            "argument": "The stock shows strong bullish momentum with increasing institutional buying and positive earnings revisions.",
            "evidence": ["Q3 earnings beat expectations by 15%", "Institutional ownership increased 3% this quarter", "Positive analyst upgrades from 3 major firms"],
            "confidence": 0.85,
            "rag_query": None,
            "counter_to": None
        }
    elif "bear" in last_msg.lower() or "bearish" in last_msg.lower():
        mock_data = {
            "argument": "The stock faces significant headwinds including market saturation and increasing competition.",
            "evidence": ["Market share declined 2% YoY", "Competitive pressure from new entrants", "Slowing revenue growth in key segments"],
            "confidence": 0.78,
            "rag_query": None,
            "counter_to": None
        }
    elif "facilitator" in last_msg.lower() or "final" in last_msg.lower():
        mock_data = {
            "recommendation": "HOLD",
            "confidence": 0.72,
            "reasoning": "After evaluating both bull and bear arguments, the stock presents a balanced risk-reward profile. Positive momentum is offset by competitive concerns.",
            "bull_score": 0.65,
            "bear_score": 0.58,
            "key_factors": ["Strong earnings momentum", "Competitive pressures", "Valuation at fair value"],
            "risk_factors": ["Market saturation", "Margin compression"],
            "time_horizon": "3-6 months"
        }
    elif "rephrase" in last_msg.lower() or "unique" in last_msg.lower():
        mock_data = {
            "argument": "From a different perspective, the technical indicators show consolidation patterns suggesting near-term price stability.",
            "evidence": ["RSI stabilizing around 50", "Volume patterns indicate accumulation"],
            "confidence": 0.75,
            "rag_query": None
        }
    else:
        mock_data = {
            "is_unique": True,
            "reasoning": "This argument presents a new perspective not previously discussed."
        }
    
    if json_mode:
        return json.dumps(mock_data)
    return str(mock_data)


class LLMClient:
    """
    LLM client using OpenAI SDK (works with OpenRouter).
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_config().llm
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the OpenAI client for OpenRouter"""
        if OPENAI_AVAILABLE:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base
            )
            logger.info(f"OpenAI client initialized for {self.config.api_base}")
            print(f"  🔌 LLM: {self.config.model} via {self.config.api_base}")
        else:
            logger.warning("OpenAI SDK not available! pip install openai")
    
    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """
        Get completion from LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            json_mode: Whether to request JSON response
            
        Returns:
            Generated text
        """
        # Use mock mode if enabled
        if USE_MOCK_LLM:
            logger.info("🎭 [MOCK MODE] Generating mock LLM response")
            print(f"  🎭 [MOCK MODE] Generating mock LLM response")
            return _generate_mock_response(messages, json_mode)
        
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        if not self._client:
            raise RuntimeError("OpenAI client not initialized! pip install openai")
        
        try:
            # Use full model name for OpenRouter (e.g., "openai/gpt-4o-mini")
            kwargs = {
                "model": self.config.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": tokens
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM completion error: {e}")
            raise
    
    def complete_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get JSON completion from LLM.
        
        Args:
            messages: List of messages
            temperature: Optional temperature override
            
        Returns:
            Parsed JSON dict
        """
        response = self.complete(messages, temperature=temperature, json_mode=True)
        return parse_json_safely(response)


def parse_json_safely(text: str) -> Dict[str, Any]:
    """
    Parse JSON from LLM response, handling common issues.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        cleaned = text.strip()
        if "```json" in cleaned:
            start = cleaned.index("```json") + 7
            end = cleaned.rindex("```")
            cleaned = cleaned[start:end].strip()
        elif "```" in cleaned:
            start = cleaned.index("```") + 3
            end = cleaned.rindex("```")
            cleaned = cleaned[start:end].strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON: {text[:200]}")
            return {"error": "JSON parsing failed", "raw": text}


# ============================================================
# PROMPT TEMPLATES
# ============================================================

DELTA_EXTRACTION_PROMPT = """You are a senior equity research analyst performing delta analysis between consecutive market reports.

PREVIOUS REPORT (T-1):
{old_report}

CURRENT REPORT (T):
{new_report}

ANALYSIS MANDATE:
Extract material changes that would trigger portfolio rebalancing decisions. Focus on:
- Earnings revisions (EPS surprises, guidance changes, margin shifts)
- Valuation multiple changes (P/E expansion/compression, relative value shifts)
- Catalyst emergence/removal (M&A, regulatory, competitive dynamics)
- Sentiment inflection points (analyst upgrades/downgrades, institutional flow changes)
- Risk factor evolution (volatility regime, correlation breakdowns, tail risks)

OUTPUT (strict JSON):
{{
    "new_points": ["Material developments not present in previous report - quantify with specific metrics where available"],
    "removed_points": ["Previous concerns/opportunities that have resolved or expired"],
    "changed_points": [
        {{"old": "Previous assessment with metrics", "new": "Updated assessment with new metrics", "magnitude": "Basis point or percentage change"}}
    ],
    "significance": "HIGH (position-altering) | MEDIUM (monitoring required) | LOW (noise)",
    "catalyst_timeline": "IMMEDIATE (<1w) | NEAR-TERM (1-4w) | MEDIUM-TERM (1-3m)",
    "summary": "One-sentence executive summary for trading desk"
}}

CLASSIFICATION RULES:
- HIGH: >10% price target revision, rating change, material guidance revision, M&A announcement
- MEDIUM: Sector rotation signals, moderate estimate revisions, competitive developments
- LOW: Minor data updates, no change to investment thesis"""


FACILITATOR_VALIDATION_PROMPT = """You are a portfolio performance analyst conducting post-trade analysis on investment recommendations.

PREVIOUS RECOMMENDATION REPORT:
{old_facilitator_report}

MARKET CONDITIONS AT RECOMMENDATION TIME:
{old_market_report}

ACTUAL MARKET OUTCOME:
{new_market_report}

PERFORMANCE ATTRIBUTION FRAMEWORK:
Evaluate recommendation accuracy across multiple dimensions:
1. DIRECTIONAL ACCURACY: Did the recommended action align with price movement?
2. MAGNITUDE ASSESSMENT: Was the conviction level (HIGH/MEDIUM/LOW) appropriate for the actual move?
3. TIMING ANALYSIS: Was the recommendation timely or premature/late?
4. THESIS VALIDATION: Did the investment thesis play out as predicted, or did different factors drive the outcome?
5. RISK ASSESSMENT: Were the identified risks the ones that materialized?

OUTPUT (strict JSON):
{{
    "old_recommendation": "BUY | HOLD | SELL",
    "market_movement": "UP (>+2%) | DOWN (<-2%) | FLAT (±2%)",
    "price_change_pct": 0.0,
    "was_correct": true/false,
    "correctness_type": "THESIS_VALIDATED | CORRECT_BY_LUCK | WRONG_DIRECTION | WRONG_MAGNITUDE | WRONG_TIMING",
    "reasoning": "Specific attribution: what drove the outcome vs. what was predicted",
    "confidence": 0.0-1.0,
    "alpha_generated": "Estimated alpha vs benchmark if position was taken",
    "lessons_learned": "Actionable insight for improving future recommendations",
    "model_calibration_note": "Was confidence level appropriate given outcome variance?"
}}

SCORING GUIDELINES:
- THESIS_VALIDATED: Correct direction AND correct reasoning
- CORRECT_BY_LUCK: Correct direction but different catalysts drove the move
- WRONG_DIRECTION: Opposite of recommendation occurred
- WRONG_MAGNITUDE: Direction correct but move was significantly larger/smaller than confidence implied"""


BULL_POINT_PROMPT = """You are a senior long-biased portfolio manager advocating for {symbol} in an investment committee debate.

YOUR ROLE: Construct the most compelling case for INCREASING position size or INITIATING a long position.

═══════════════════════════════════════════════════════════════
CURRENT INTELLIGENCE PACKAGE
═══════════════════════════════════════════════════════════════

MARKET CONTEXT:
{context}

REPORT DELTA ANALYSIS:
{deltas}

PREVIOUS CALL PERFORMANCE: {correct_status}
Attribution: {correctness_reasoning}

INSTITUTIONAL MEMORY (Past Learnings):
{memory_context}

DEBATE TRANSCRIPT:
{debate_history}

BEAR'S CURRENT ARGUMENT:
{opponent_point}

KNOWLEDGE BASE EVIDENCE:
{rag_info}

═══════════════════════════════════════════════════════════════
ARGUMENTATION MANDATE
═══════════════════════════════════════════════════════════════

Your bullish thesis must address AT LEAST ONE of these value drivers:
• GROWTH CATALYSTS: Revenue acceleration, TAM expansion, market share gains, new product cycles
• MARGIN EXPANSION: Operating leverage, cost optimization, pricing power, mix shift
• MULTIPLE RE-RATING: Sector rotation tailwinds, peer comparison discount, sentiment recovery
• CAPITAL RETURNS: Buyback acceleration, dividend growth, deleveraging benefits
• ASYMMETRIC UPSIDE: Underappreciated optionality, M&A potential, sum-of-parts discount

EVIDENCE INTEGRATION RULES:
1. If countering Bear: Directly refute with contradicting KB evidence or reframe the risk as opportunity
2. If presenting new point: Build conviction pyramid (thesis → supporting data → catalyst → timeline)
3. Always quantify: Use specific numbers from KB/reports (%, $, multiples, growth rates)

OUTPUT (strict JSON):
{{
    "thought": "Internal reasoning: What's the strongest bull case given current evidence? How does KB data support this? What would institutional investors find compelling?",
    "point_type": "counter | new",
    "point": "Your bullish argument - make it specific, quantified, and actionable. Reference exact metrics.",
    "supporting_evidence": ["Evidence item 1 with source attribution", "Evidence item 2 with specific metrics", "Evidence item 3 linking to catalyst"],
    "bull_thesis_pillar": "GROWTH | MARGIN | MULTIPLE | CAPITAL_RETURNS | OPTIONALITY",
    "confidence": 0.0-1.0,
    "conviction_driver": "What single data point most strongly supports this argument?"
}}

QUALITY STANDARDS:
- Avoid generic statements like "strong fundamentals" without specific supporting data
- Each argument should be falsifiable and time-bounded where possible
- Counter-arguments should address the Bear's specific concern, not pivot to unrelated bullish points """


BEAR_POINT_PROMPT = """You are a senior risk analyst and short-biased portfolio manager challenging the bull case for {symbol} in an investment committee debate.

YOUR ROLE: Identify vulnerabilities, stress-test assumptions, and present the most compelling case for REDUCING position size or AVOIDING the position.

═══════════════════════════════════════════════════════════════
CURRENT INTELLIGENCE PACKAGE
═══════════════════════════════════════════════════════════════

MARKET CONTEXT:
{context}

REPORT DELTA ANALYSIS:
{deltas}

PREVIOUS CALL PERFORMANCE: {correct_status}
Attribution: {correctness_reasoning}

INSTITUTIONAL MEMORY (Past Learnings):
{memory_context}

DEBATE TRANSCRIPT:
{debate_history}

BULL'S CURRENT ARGUMENT:
{opponent_point}

KNOWLEDGE BASE EVIDENCE:
{rag_info}

═══════════════════════════════════════════════════════════════
RISK IDENTIFICATION MANDATE
═══════════════════════════════════════════════════════════════

Your bearish thesis must address AT LEAST ONE of these risk vectors:
• VALUATION RISK: Multiple compression, peer discount justified, DCF sensitivity to growth assumptions
• EXECUTION RISK: Management track record, competitive moat erosion, integration challenges
• MACRO HEADWINDS: Rate sensitivity, currency exposure, regulatory overhang, cycle timing
• EARNINGS RISK: Estimate vulnerability, margin pressure, revenue quality concerns
• TECHNICAL DETERIORATION: Momentum breakdown, institutional selling, options market signals
• BLACK SWAN EXPOSURE: Tail risks, concentration risks, hidden liabilities

EVIDENCE INTEGRATION RULES:
1. If countering Bull: Attack the weakest link in their argument chain with specific contradicting data
2. If presenting new point: Build risk case (threat identification → quantification → catalyst → probability)
3. Always quantify downside: Use specific drawdown scenarios, valuation floors, or historical precedents

OUTPUT (strict JSON):
{{
    "thought": "Internal reasoning: What's the fatal flaw in the bull case? What are institutional investors underestimating? Where is the KB evidence most damaging?",
    "point_type": "counter | new",
    "point": "Your bearish argument - make it specific, quantified, and highlight asymmetric downside. Reference exact risks.",
    "supporting_evidence": ["Risk evidence 1 with source attribution", "Risk evidence 2 with specific metrics", "Historical precedent or comparable situation"],
    "bear_thesis_pillar": "VALUATION | EXECUTION | MACRO | EARNINGS | TECHNICAL | TAIL_RISK",
    "confidence": 0.0-1.0,
    "key_vulnerability": "What single factor could cause the largest drawdown?"
}}

QUALITY STANDARDS:
- Avoid permabear clichés like "overvalued" without specific multiple/peer analysis
- Each risk should have an identifiable trigger or catalyst
- Counter-arguments should expose logical flaws in Bull's thesis, not just present unrelated concerns
- Consider second-order effects: how could a small issue cascade?"""


UNIQUENESS_CHECK_PROMPT = """You are a debate quality controller ensuring argumentative rigor and non-redundancy.

CANDIDATE POINT:
{new_point}

EXISTING ARGUMENTS FROM SAME PARTY:
{previous_points}

UNIQUENESS EVALUATION CRITERIA:
1. SUBSTANTIVE NOVELTY: Does this point introduce genuinely new information, data, or reasoning?
2. LOGICAL INDEPENDENCE: Is this argument's validity independent from previous points?
3. EVIDENCE FRESHNESS: Does it cite different sources or metrics?
4. ANGLE DIFFERENTIATION: Does it approach the thesis from a distinct perspective (valuation vs. growth vs. sentiment)?

SIMILARITY DETECTION:
- IDENTICAL: Same core claim, same evidence → REJECT
- OVERLAPPING: Same core claim, different evidence → CONDITIONAL (may accept if evidence is materially different)
- COMPLEMENTARY: Different claim, related theme → ACCEPT
- DISTINCT: Different claim, different evidence → ACCEPT

OUTPUT (strict JSON):
{{
    "is_unique": true | false,
    "uniqueness_score": 0.0-1.0,
    "similar_to": "ID of most similar point if score < 0.6, null otherwise",
    "similarity_type": "IDENTICAL | OVERLAPPING | COMPLEMENTARY | DISTINCT",
    "similarity_reason": "Specific explanation: what overlaps and why it matters (or doesn't)",
    "differentiation_suggestion": "If not unique, what angle could make this point acceptable?"
}}

THRESHOLD: Reject if uniqueness_score < 0.6 or similarity_type is IDENTICAL"""


FACILITATOR_CONCLUSION_PROMPT = """You are the Chief Investment Officer synthesizing the bull-bear debate into an actionable investment decision for {symbol}.

═══════════════════════════════════════════════════════════════
PRIOR ANALYSIS CONTEXT
═══════════════════════════════════════════════════════════════

PREVIOUS CIO REPORT:
{old_report}

PRIOR RECOMMENDATION ACCURACY: {was_correct}
Performance Attribution: {correctness_reasoning}

═══════════════════════════════════════════════════════════════
CURRENT DEBATE SYNTHESIS
═══════════════════════════════════════════════════════════════

DEBATE POINTS PRESENTED:
{debate_points}

INTELLIGENCE DELTAS SINCE LAST ANALYSIS:
• News Flow: {news_delta}
• Sentiment Indicators: {sentiment_delta}
• Technical/Market Data: {market_delta}
• Fundamental Metrics: {fundamental_delta}

═══════════════════════════════════════════════════════════════
SYNTHESIS FRAMEWORK
═══════════════════════════════════════════════════════════════

Generate a comprehensive investment committee memo:

---

# Investment Committee Memo: {symbol}
## Analysis Date: {timestamp} UTC

### Executive Summary
[2-3 sentences capturing: current thesis, key development, and recommended action]

---

### I. Debate Synthesis

#### Strongest Bull Arguments
| # | Argument | Evidence Strength | Counter-Risk |
|---|----------|------------------|--------------|
[Rank top 3 bull points by persuasiveness, note evidence quality and residual risk]

#### Strongest Bear Arguments  
| # | Argument | Evidence Strength | Mitigating Factor |
|---|----------|------------------|-------------------|
[Rank top 3 bear points by validity, note evidence quality and potential mitigant]

#### Points of Consensus
[Where do both sides agree? These are high-conviction observations]

#### Unresolved Disputes
[Key disagreements that require monitoring or additional analysis]

---

### II. Thesis Evolution

#### Changes Since Last Analysis
[What's materially different? Connect to the delta reports]

#### Thesis Confirmation/Revision
[Does the core investment thesis remain intact or require revision?]

---

### III. Investment Recommendation

#### Action: [BUY | HOLD | SELL]
#### Conviction Level: [HIGH | MEDIUM | LOW]

**Rationale:** [3-4 sentences explaining the weight of evidence leading to this conclusion]

**Position Sizing Guidance:**
- Current Situation: [Overweight/Market Weight/Underweight vs. benchmark]
- Recommended Adjustment: [Increase/Maintain/Reduce exposure]
- Maximum Position: [As % of portfolio, based on conviction and risk]

---

### IV. Risk Management

#### Key Risks to Monitor
| Risk Factor | Trigger Level | Action if Triggered |
|-------------|---------------|---------------------|
[3-5 specific, measurable risk triggers with predetermined responses]

#### Stop-Loss/Take-Profit Levels
- Downside Exit: [Price/% level with rationale]
- Upside Target: [Price/% level with rationale]
- Time Stop: [Re-evaluate if no catalyst by X date]

---

### V. Action Items

1. [Specific near-term action with owner/deadline]
2. [Monitoring item with frequency]
3. [Contingent action if specific event occurs]

---

**Report Generated:** {timestamp} UTC  
**Next Review:** [Recommended date for re-evaluation]
**Confidence Calibration:** [Note on prior accuracy and model reliability]
"""


RAG_QUERY_GENERATION_PROMPT = """You are a {party} research analyst preparing evidence retrieval for an investment debate on {symbol}.

CURRENT DEBATE STATE:
{context}

OPPONENT'S ARGUMENT TO ADDRESS:
{opponent_point}

YOUR MANDATE: {stance_description}

═══════════════════════════════════════════════════════════════
QUERY GENERATION STRATEGY
═══════════════════════════════════════════════════════════════

OBJECTIVE: Generate a targeted search query to extract the most damaging (if countering) or supporting (if building) evidence from the knowledge base.

QUERY OPTIMIZATION TACTICS:
1. COUNTER-EVIDENCE SEARCH (if opponent made a point):
   - Identify the opponent's key assumption or data point
   - Search for contradicting metrics, failed precedents, or risk factors
   - Look for temporally relevant data that may invalidate their claim

2. THESIS-BUILDING SEARCH (if presenting new argument):
   - For BULL: Search for growth metrics, positive catalysts, undervaluation signals
   - For BEAR: Search for risk factors, competitive threats, valuation concerns
   - Prioritize quantitative data over qualitative narratives

3. KEYWORD STRATEGY:
   - Include ticker symbol and company name variations
   - Use financial terminology: EPS, P/E, margin, guidance, outlook, risk
   - Include temporal qualifiers: recent, latest, Q[1-4], FY, YoY

OUTPUT (strict JSON):
{{
    "query": "Precise search query optimized for vector similarity - include key financial terms and specific metrics",
    "search_intent": "COUNTER_EVIDENCE | SUPPORT_THESIS | FIND_CATALYST | VALIDATE_ASSUMPTION",
    "target_data_type": "earnings_data | valuation_metrics | news_events | analyst_ratings | technical_signals | risk_factors | competitive_analysis",
    "expected_evidence_strength": "HIGH (direct refutation/support) | MEDIUM (contextual) | LOW (tangential)",
    "fallback_query": "Alternative query if primary returns insufficient results"
}}

QUALITY CRITERIA:
- Query should be specific enough to return relevant results but not so narrow as to miss important data
- Avoid generic terms like "stock analysis" - be specific to the argument being made/countered"""


REPHRASE_POINT_PROMPT = """You are a {party} analyst whose previous argument was rejected for insufficient differentiation.

═══════════════════════════════════════════════════════════════
REJECTION CONTEXT
═══════════════════════════════════════════════════════════════

YOUR REJECTED POINT:
{rejected_point}

SIMILAR EXISTING POINT (REASON FOR REJECTION):
{similar_point}

ADDITIONAL INTELLIGENCE AVAILABLE:
{available_info}

═══════════════════════════════════════════════════════════════
REFORMULATION MANDATE
═══════════════════════════════════════════════════════════════

Your task: Generate a SUBSTANTIALLY DIFFERENT {party} argument that:

DIFFERENTIATION STRATEGIES:
1. DIFFERENT THESIS PILLAR: If similar point was about valuation, argue from growth/execution/technical angle
2. DIFFERENT TIME HORIZON: If similar point was near-term, argue medium/long-term implications (or vice versa)
3. DIFFERENT DATA SOURCE: Use entirely different evidence categories (fundamentals vs. technicals vs. sentiment)
4. DIFFERENT CAUSATION CHAIN: Same conclusion through different logical path
5. SECOND-ORDER EFFECTS: Focus on implications rather than direct effects

QUALITY REQUIREMENTS:
- Must maintain {party} stance (BULL = constructive, BEAR = cautionary)
- Must use DIFFERENT evidence than the similar point
- Must approach the thesis from a DISTINCT analytical angle
- Should add genuine new insight to the debate, not just rephrase

OUTPUT (strict JSON):
{{
    "reformulation_strategy": "DIFFERENT_PILLAR | DIFFERENT_HORIZON | DIFFERENT_DATA | DIFFERENT_CAUSATION | SECOND_ORDER",
    "point": "Your new, substantively different {party} argument",
    "supporting_evidence": ["Evidence item 1 (must differ from similar point)", "Evidence item 2", "Evidence item 3"],
    "differentiation_explanation": "How this point adds new value vs. the similar one",
    "confidence": 0.0-1.0
}}

WARNING: If you cannot generate a truly different point, consider whether the {party} case has been exhaustively argued."""
