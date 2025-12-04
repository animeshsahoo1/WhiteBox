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

DELTA_EXTRACTION_PROMPT = """You are a financial analyst comparing two reports to identify changes.

OLD REPORT:
{old_report}

NEW REPORT:
{new_report}

Analyze the differences and output a JSON object with:
{{
    "new_points": ["list of new key points/insights not in old report"],
    "removed_points": ["list of points that were in old but not in new"],
    "changed_points": [
        {{"old": "old statement", "new": "new statement"}}
    ],
    "significance": "HIGH/MEDIUM/LOW",
    "summary": "Brief summary of changes"
}}

Focus on significant changes that would affect investment decisions."""


FACILITATOR_VALIDATION_PROMPT = """You are validating a previous investment recommendation.

PREVIOUS FACILITATOR REPORT:
{old_facilitator_report}

PREVIOUS MARKET CONDITIONS:
{old_market_report}

CURRENT MARKET CONDITIONS:
{new_market_report}

Analyze whether the previous recommendation was correct based on what actually happened.

Output JSON:
{{
    "old_recommendation": "BUY/HOLD/SELL",
    "market_movement": "UP/DOWN/FLAT",
    "was_correct": true/false,
    "reasoning": "explanation of why the recommendation was correct or incorrect",
    "confidence": 0.0-1.0,
    "lessons_learned": "what can be learned from this"
}}"""


BULL_POINT_PROMPT = """You are the BULL (optimistic) analyst in an investment debate about {symbol}.

CONTEXT:
{context}

REPORT CHANGES:
{deltas}

PREVIOUS FACILITATOR WAS {correct_status}: {correctness_reasoning}

MEMORY CONTEXT:
{memory_context}

DEBATE HISTORY:
{debate_history}

BEAR'S LAST POINT (if any):
{opponent_point}

EVIDENCE FROM KNOWLEDGE BASE:
{rag_info}

You must present a BULLISH argument. Use the evidence from the knowledge base to strengthen your point!
Either:
1. Counter the Bear's last point with bullish perspective, using KB evidence
2. Present a new bullish point supported by KB evidence and report changes

IMPORTANT: Incorporate the knowledge base evidence into your argument when relevant.

Output JSON:
{{
    "thought": "your reasoning process, how you're using the KB evidence",
    "point_type": "counter" or "new",
    "point": "your bullish argument incorporating KB evidence",
    "supporting_evidence": ["list of evidence from KB and reports"],
    "confidence": 0.0-1.0
}}

Be specific, cite data from KB and reports, and maintain a bullish stance."""


BEAR_POINT_PROMPT = """You are the BEAR (cautious/pessimistic) analyst in an investment debate about {symbol}.

CONTEXT:
{context}

REPORT CHANGES:
{deltas}

PREVIOUS FACILITATOR WAS {correct_status}: {correctness_reasoning}

MEMORY CONTEXT:
{memory_context}

DEBATE HISTORY:
{debate_history}

BULL'S LAST POINT (if any):
{opponent_point}

EVIDENCE FROM KNOWLEDGE BASE:
{rag_info}

You must present a BEARISH argument. Use the evidence from the knowledge base to strengthen your point!
Either:
1. Counter the Bull's last point with bearish perspective, using KB evidence
2. Present a new bearish point supported by KB evidence and report changes

IMPORTANT: Incorporate the knowledge base evidence into your argument when relevant.

Output JSON:
{{
    "thought": "your reasoning process, how you're using the KB evidence",
    "point_type": "counter" or "new",
    "point": "your bearish argument incorporating KB evidence",
    "supporting_evidence": ["list of evidence from KB and reports"],
    "confidence": 0.0-1.0
}}

Be specific, cite data from KB and reports, and maintain a bearish stance."""


UNIQUENESS_CHECK_PROMPT = """Check if the following point is sufficiently different from previous points.

NEW POINT:
{new_point}

PREVIOUS POINTS BY SAME PARTY:
{previous_points}

Output JSON:
{{
    "is_unique": true/false,
    "similar_to": "ID of similar point if not unique, null otherwise",
    "similarity_reason": "explanation if not unique"
}}"""


FACILITATOR_CONCLUSION_PROMPT = """You are the Senior Investment Facilitator for {symbol}.

OLD FACILITATOR REPORT:
{old_report}

NEW DEBATE POINTS:
{debate_points}

REPORT DELTAS:
- News: {news_delta}
- Sentiment: {sentiment_delta}
- Market: {market_delta}
- Fundamental: {fundamental_delta}

WAS PREVIOUS CONCLUSION CORRECT: {was_correct}
REASONING: {correctness_reasoning}

Generate a comprehensive facilitator report in markdown format:

# Investment Analysis Report: {symbol}
## Generated: {timestamp}

### Executive Summary
[Balanced summary of current situation]

### Bull Arguments (Top Points)
[List the strongest bullish arguments from the debate]

### Bear Arguments (Top Points)
[List the strongest bearish arguments from the debate]

### Areas of Agreement
[Points where both sides agree]

### Key Disagreements
[Major points of contention]

### Changes Since Last Analysis
[Significant changes in the reports]

### Facilitator's Assessment
[Your balanced assessment]

### Recommendation: [BUY/HOLD/SELL]
Confidence: [HIGH/MEDIUM/LOW]

### Risk Considerations
[Key risks to monitor]

### Action Items
[Specific recommendations]

---
Last Analysis: {timestamp} UTC
"""


RAG_QUERY_GENERATION_PROMPT = """You are a {party} analyst preparing to make a point in an investment debate about {symbol}.

OPPONENT'S LAST POINT:
{opponent_point}

YOUR STANCE: {stance_description}

DEBATE CONTEXT:
{context}

Generate a search query to find evidence from the knowledge base that will help you:
1. Find data to COUNTER the opponent's argument (if they made a point)
2. Find supporting evidence for YOUR {party} perspective
3. Discover facts, statistics, or analysis that strengthens your position

Output JSON:
{{
    "query": "your search query for the knowledge base",
    "search_intent": "what you're looking for",
    "expected_evidence_type": "statistics/news/analysis/historical data/etc"
}}

Make the query specific and targeted to find useful counter-evidence or supporting data."""


REPHRASE_POINT_PROMPT = """Your previous point was too similar to an existing point.

PREVIOUS POINT THAT WAS SIMILAR:
{similar_point}

YOUR REJECTED POINT:
{rejected_point}

AVAILABLE NEW INFORMATION:
{available_info}

Generate a NEW, UNIQUE {party} point that:
1. Is substantially different from the similar point
2. Uses different evidence or perspective
3. Still maintains your {party} stance

Output JSON:
{{
    "point": "your new unique argument",
    "supporting_evidence": ["list of evidence"],
    "confidence": 0.0-1.0
}}"""
