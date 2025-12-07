"""
LLM Utilities for Bull-Bear Debate
Handles LLM interactions with proper prompting and parsing

Optimizations:
- Module-level OpenAI client caching (one per config hash)
- Avoids recreating expensive client connections
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

# ============================================================
# MODULE-LEVEL CLIENT CACHING
# ============================================================
# Cache OpenAI clients by (api_key, api_base) to avoid recreating connections
_cached_clients: Dict[tuple, 'OpenAI'] = {}


def get_cached_openai_client(api_key: str, api_base: str) -> Optional['OpenAI']:
    """
    Get or create a cached OpenAI client.
    
    Avoids recreating expensive HTTP connections for repeated debates.
    """
    if not OPENAI_AVAILABLE:
        return None
    
    cache_key = (api_key, api_base)
    
    if cache_key not in _cached_clients:
        try:
            _cached_clients[cache_key] = OpenAI(
                api_key=api_key,
                base_url=api_base
            )
            logger.info(f"Created new OpenAI client for {api_base}")
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            return None
    
    return _cached_clients[cache_key]


def clear_llm_client_cache():
    """
    Clear all cached OpenAI clients.
    
    Useful for cleanup or when API keys change.
    """
    global _cached_clients
    count = len(_cached_clients)
    _cached_clients = {}
    logger.info(f"Cleared {count} cached OpenAI clients")


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
    
    Uses module-level client caching to avoid recreating connections.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_config().llm
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the OpenAI client for OpenRouter (uses cache)"""
        if OPENAI_AVAILABLE:
            # Use cached client instead of creating new one
            self._client = get_cached_openai_client(
                self.config.api_key,
                self.config.api_base
            )
            if self._client:
                logger.info(f"Using cached OpenAI client for {self.config.api_base}")
                print(f"  🔌 LLM: {self.config.model} via {self.config.api_base}")
            else:
                logger.warning("Failed to get OpenAI client from cache")
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


BULL_POINT_PROMPT = """You are a BULLISH investment analyst presenting a STRONG CASE TO BUY {symbol}.

## YOUR OBJECTIVE
Make the most compelling BULLISH argument using the Toulmin argumentation model.
DO NOT BE TIMID - if the data supports buying, advocate strongly for BUY!

## TOULMIN MODEL - YOU MUST INCLUDE ALL 5 COMPONENTS:

1. **CLAIM** (Your main assertion)
   - Clear, specific, actionable: "Investors should BUY {symbol} because..."
   - Include a price target or upside potential when possible

2. **EVIDENCE** (Concrete data supporting your claim)
   - Use SPECIFIC NUMBERS: percentages, dollar amounts, ratios, growth rates
   - Cite sources from the reports provided
   - Minimum 3 evidence points

3. **WARRANT** (Logical connection between evidence and claim)
   - Explain WHY this evidence supports buying
   - Use logical reasoning: "This indicates... because..."

4. **QUALIFIER** (Confidence level and conditions)
   - State your confidence: "I am X% confident..."
   - Acknowledge conditions: "This thesis holds if..."

5. **REBUTTAL** (Counter the BEAR's argument)
   - Directly address the opposing view
   - "While bears argue X, this is mitigated by Y because..."

## INTELLIGENCE
{context}

{deltas}

DEBATE HISTORY:
{debate_history}

BEAR'S ARGUMENT TO COUNTER:
{opponent_point}

KNOWLEDGE BASE:
{rag_info}

## OUTPUT (strict JSON):
{{
    "claim": "Clear BUY recommendation with specific thesis and target",
    "evidence": ["Evidence 1 with specific numbers", "Evidence 2 with metrics", "Evidence 3 with data"],
    "warrant": "Logical explanation of why this evidence supports buying",
    "qualifier": "Confidence level (0.6-0.95) and conditions for thesis to hold",
    "rebuttal": "Direct counter to bear's main argument with reasoning",
    "confidence": 0.7-0.95,
    "point_type": "counter | new",
    "supporting_evidence": ["Same as evidence array for compatibility"]
}}

REMEMBER: Be DECISIVE. If data supports buying, say BUY with conviction! Don't hedge unnecessarily."""


BEAR_POINT_PROMPT = """You are a BEARISH investment analyst presenting a STRONG CASE TO SELL/AVOID {symbol}.

## YOUR OBJECTIVE
Make the most compelling BEARISH argument using the Toulmin argumentation model.
DO NOT BE TIMID - if the data shows risks, advocate strongly for SELL or AVOID!

## TOULMIN MODEL - YOU MUST INCLUDE ALL 5 COMPONENTS:

1. **CLAIM** (Your main assertion)
   - Clear, specific, actionable: "Investors should SELL/AVOID {symbol} because..."
   - Include a downside target or risk quantification when possible

2. **EVIDENCE** (Concrete data supporting your claim)
   - Use SPECIFIC NUMBERS: percentages, losses, ratios, negative trends
   - Cite sources from the reports provided
   - Minimum 3 evidence points

3. **WARRANT** (Logical connection between evidence and claim)
   - Explain WHY this evidence indicates risk
   - Use logical reasoning: "This signals danger because..."

4. **QUALIFIER** (Confidence level and conditions)
   - State your confidence: "I am X% confident in my bearish thesis..."
   - Acknowledge conditions: "The downside materializes if..."

5. **REBUTTAL** (Counter the BULL's argument)
   - Directly address the bullish view
   - "While bulls argue X, this ignores Y because..."

## INTELLIGENCE
{context}

{deltas}

DEBATE HISTORY:
{debate_history}

BULL'S ARGUMENT TO COUNTER:
{opponent_point}

KNOWLEDGE BASE:
{rag_info}

## OUTPUT (strict JSON):
{{
    "claim": "Clear SELL/AVOID recommendation with specific risk thesis",
    "evidence": ["Risk evidence 1 with numbers", "Risk evidence 2 with metrics", "Risk evidence 3 with data"],
    "warrant": "Logical explanation of why this evidence indicates sell",
    "qualifier": "Confidence level (0.6-0.95) and conditions for risk to materialize",
    "rebuttal": "Direct counter to bull's main argument with reasoning",
    "confidence": 0.7-0.95,
    "point_type": "counter | new",
    "supporting_evidence": ["Same as evidence array for compatibility"]
}}

REMEMBER: Be DECISIVE. If risks are real, say SELL with conviction! Don't downplay genuine concerns."""


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


FACILITATOR_CONCLUSION_PROMPT = """You are the Chief Investment Officer making the FINAL investment decision for {symbol}.

## DEBATE FORMAT
This debate used ASIAN PARLIAMENTARY format: Bull spoke LAST with the closing argument.
Evaluate based on PRIMARY EVIDENCE quality, not speaking order.

## YOUR MANDATE
Evaluate the debate using TOULMIN ARGUMENTATION QUALITY and make a DECISIVE recommendation.

## PREVIOUS CONTEXT
{old_report}

Previous Accuracy: {was_correct}
{correctness_reasoning}

## DEBATE TRANSCRIPT
{debate_points}

## INTELLIGENCE UPDATES
- News: {news_delta}
- Sentiment: {sentiment_delta}
- Market: {market_delta}
- Fundamental: {fundamental_delta}

═══════════════════════════════════════════════════════════════
TOULMIN QUALITY SCORING (Score each 1-5)
═══════════════════════════════════════════════════════════════

For EACH side (Bull and Bear), evaluate:

1. **Claim Clarity** (1-5): Is the recommendation specific and actionable?
2. **Evidence Quality** (1-5): Are there 3+ concrete, quantified data points?
3. **Warrant Strength** (1-5): Does the logic connect evidence to claim?
4. **Qualifier Honesty** (1-5): Is confidence level realistic given the evidence?
5. **Rebuttal Effectiveness** (1-5): Did they counter the opposing view?

## DECISION RULES

Calculate: BULL_TOTAL = sum of Bull's 5 scores (max 25)
Calculate: BEAR_TOTAL = sum of Bear's 5 scores (max 25)

**Also check confidence levels from arguments:**
- If Bull confidence > 0.75 AND Bear confidence < 0.60 → Lean **BUY**
- If Bear confidence > 0.75 AND Bull confidence < 0.60 → Lean **SELL**

**Score-based decision:**
- If BULL_TOTAL > BEAR_TOTAL + 2: Recommend **BUY**
- If BEAR_TOTAL > BULL_TOTAL + 2: Recommend **SELL**  
- If within 2 points AND both have similar confidence: Recommend **HOLD**

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

# Investment Memo: {symbol}
## Date: {timestamp} UTC

### Toulmin Quality Scores

| Criterion | BULL | BEAR |
|-----------|------|------|
| Claim Clarity | X/5 | X/5 |
| Evidence Quality | X/5 | X/5 |
| Warrant Strength | X/5 | X/5 |
| Qualifier Honesty | X/5 | X/5 |
| Rebuttal Effectiveness | X/5 | X/5 |
| **TOTAL** | XX/25 | XX/25 |

### Winner: [BULL/BEAR] by [X] points

### Recommendation: [BUY | SELL | HOLD]
### Conviction: [HIGH | MEDIUM | LOW]

**Rationale:** [2-3 sentences explaining why the winning side's argument was stronger]

**Key Evidence That Decided:** [The single most compelling data point]

### Risk Triggers
- Exit if: [specific condition]
- Target: [upside target]

---
**REMEMBER: Be DECISIVE! If one side won clearly, recommend BUY or SELL, not HOLD!**
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
- Must use DIFFERENT evidence than the similar point1
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
