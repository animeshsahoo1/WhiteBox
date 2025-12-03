"""
Simple Rule-Based Guardrails Service
Fast, reliable, no LLM interference with main workflow.
"""
import re
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .config import (
    PII_PATTERNS,
    JAILBREAK_KEYWORDS,
    OFF_TOPIC_KEYWORDS,
    FINANCIAL_KEYWORDS,
    INVESTMENT_DISCLAIMER,
)

NEMO_AVAILABLE = False  # Disabled to avoid interference


@dataclass
class GuardResult:
    """Result from guardrail check"""
    allowed: bool
    message: str
    reason: str
    pii_detected: List[str] = None
    modified: bool = False
    llm_used: bool = False
    nemo_used: bool = False


class GuardrailsService:
    """
    Simple Rule-Based Guardrails - No LLM calls, no interference.
    
    Checks:
    - PII detection and masking (regex)
    - Jailbreak detection (keywords)
    - Off-topic detection (keywords)
    - Output disclaimer addition
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.enabled = os.getenv("GUARDRAILS_ENABLED", "true").lower() == "true"
        print(f"🛡️ Guardrails initialized (rule-based mode, enabled={self.enabled})")
    
    def _check_pii(self, text: str) -> Tuple[bool, List[str], str]:
        """Check for PII and mask it."""
        pii_found = []
        masked_text = text
        
        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                pii_found.append(pii_type)
                masked_text = re.sub(
                    pattern,
                    f"[{pii_type.upper()}_REDACTED]",
                    masked_text,
                    flags=re.IGNORECASE
                )
        
        return len(pii_found) > 0, pii_found, masked_text
    
    def _check_jailbreak(self, text: str) -> bool:
        """Check for jailbreak attempts."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in JAILBREAK_KEYWORDS)
    
    def _check_off_topic(self, text: str) -> bool:
        """Check if query is off-topic (not financial)."""
        text_lower = text.lower()
        # If has financial keyword, it's on-topic
        if any(kw in text_lower for kw in FINANCIAL_KEYWORDS):
            return False
        # Check for explicit off-topic keywords
        return any(kw in text_lower for kw in OFF_TOPIC_KEYWORDS)
    
    def check_input(self, user_input: str) -> GuardResult:
        """Check user input - fast rule-based checks only."""
        if not self.enabled:
            return GuardResult(allowed=True, message=user_input, reason="disabled")
        
        # 1. Check PII
        has_pii, pii_types, masked_input = self._check_pii(user_input)
        
        # 2. Check jailbreak
        if self._check_jailbreak(user_input):
            return GuardResult(
                allowed=False,
                message="I cannot comply with that request. I'm here to help with financial analysis.",
                reason="jailbreak_blocked",
                pii_detected=pii_types if has_pii else None
            )
        
        # 3. Check off-topic
        if self._check_off_topic(user_input):
            return GuardResult(
                allowed=False,
                message="I'm a financial analysis assistant. I can help with stock market analysis and trading insights.",
                reason="off_topic_blocked",
                pii_detected=pii_types if has_pii else None
            )
        
        # 4. Return (with masked PII if found)
        if has_pii:
            return GuardResult(
                allowed=True,
                message=masked_input,
                reason="pii_masked",
                pii_detected=pii_types,
                modified=True
            )
        
        return GuardResult(allowed=True, message=user_input, reason="allowed")
    
    def check_output(self, bot_response: str, add_disclaimer: bool = True) -> GuardResult:
        """Check and modify bot output."""
        if not self.enabled:
            return GuardResult(allowed=True, message=bot_response, reason="disabled")
        
        # 1. Mask PII in output
        has_pii, pii_types, masked_response = self._check_pii(bot_response)
        final_response = masked_response
        modified = has_pii
        
        # 2. Add disclaimer for investment content
        if add_disclaimer:
            investment_kws = ["buy", "sell", "invest", "trade", "recommend", "bullish", "bearish", "target"]
            needs_disclaimer = any(kw in bot_response.lower() for kw in investment_kws)
            if needs_disclaimer and INVESTMENT_DISCLAIMER not in bot_response:
                final_response = masked_response + INVESTMENT_DISCLAIMER
                modified = True
        
        return GuardResult(
            allowed=True,
            message=final_response,
            reason="pii_masked" if has_pii else ("disclaimer_added" if modified else "allowed"),
            pii_detected=pii_types if has_pii else None,
            modified=modified
        )


# Global instance
_service: Optional[GuardrailsService] = None


def get_guardrails_service() -> GuardrailsService:
    global _service
    if _service is None:
        _service = GuardrailsService()
    return _service


def guard_input(user_input: str) -> GuardResult:
    """Guard user input."""
    return get_guardrails_service().check_input(user_input)


def guard_output(bot_response: str, add_disclaimer: bool = True) -> GuardResult:
    """Guard bot output."""
    return get_guardrails_service().check_output(bot_response, add_disclaimer)


# Backward compatibility
NeMoGuardrailsService = GuardrailsService
