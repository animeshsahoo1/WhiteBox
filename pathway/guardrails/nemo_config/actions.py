"""
Custom Actions for NeMo Guardrails
These actions are called by Colang flows for guardrail checks
"""

import re
from typing import Optional
from nemoguardrails.actions import action

# PII patterns for detection
PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone": r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
    "ssn": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
}

# Jailbreak keywords
JAILBREAK_KEYWORDS = [
    "ignore your instructions",
    "forget your rules", 
    "pretend you are",
    "act as if you have no restrictions",
    "bypass your filters",
    "dan mode",
    "jailbreak",
    "ignore previous",
    "disregard your programming",
    "override your",
    "you are now",
    "new persona",
    "roleplay as",
    "no ethical guidelines",
    "ignore safety"
]

# Off-topic keywords (non-financial)
OFF_TOPIC_KEYWORDS = [
    "recipe", "cooking", "weather", "sports score",
    "movie recommendation", "song lyrics", "poem",
    "joke", "riddle", "game", "homework help",
    "relationship advice", "medical advice"
]

# Financial keywords (whitelist)
FINANCIAL_KEYWORDS = [
    "stock", "share", "price", "market", "trading",
    "investment", "portfolio", "dividend", "earnings",
    "revenue", "profit", "loss", "analysis", "forecast",
    "bull", "bear", "ticker", "nasdaq", "nyse", "s&p",
    "dow", "etf", "mutual fund", "bond", "forex",
    "crypto", "bitcoin", "financial", "economy"
]


@action(name="CheckJailbreakAction")
async def check_jailbreak(user_input: str) -> bool:
    """Check if user input contains jailbreak attempts"""
    user_input_lower = user_input.lower()
    
    for keyword in JAILBREAK_KEYWORDS:
        if keyword.lower() in user_input_lower:
            return True
    
    return False


@action(name="CheckOffTopicAction") 
async def check_off_topic(user_input: str) -> bool:
    """Check if user input is off-topic (non-financial)"""
    user_input_lower = user_input.lower()
    
    # Check if any financial keyword is present
    has_financial_keyword = any(
        kw.lower() in user_input_lower 
        for kw in FINANCIAL_KEYWORDS
    )
    
    # If financial keyword present, it's on-topic
    if has_financial_keyword:
        return False
    
    # Check for explicit off-topic keywords
    has_off_topic_keyword = any(
        kw.lower() in user_input_lower
        for kw in OFF_TOPIC_KEYWORDS
    )
    
    return has_off_topic_keyword


@action(name="CheckPIIAction")
async def check_pii(text: str) -> bool:
    """Check if text contains PII"""
    for pattern_name, pattern in PII_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


@action(name="MaskPIIAction")
async def mask_pii(text: str) -> str:
    """Mask PII in text"""
    masked_text = text
    
    replacements = {
        "email": "[EMAIL REDACTED]",
        "phone": "[PHONE REDACTED]",
        "ssn": "[SSN REDACTED]",
        "credit_card": "[CARD REDACTED]",
        "ip_address": "[IP REDACTED]",
    }
    
    for pattern_name, pattern in PII_PATTERNS.items():
        masked_text = re.sub(pattern, replacements[pattern_name], masked_text, flags=re.IGNORECASE)
    
    return masked_text


@action(name="CheckHarmfulOutputAction")
async def check_harmful_output(output: str) -> bool:
    """Check if output contains harmful content"""
    harmful_patterns = [
        r"guaranteed\s+return",
        r"100%\s+profit",
        r"risk[- ]free\s+investment",
        r"insider\s+information",
        r"market\s+manipulation",
    ]
    
    output_lower = output.lower()
    
    for pattern in harmful_patterns:
        if re.search(pattern, output_lower):
            return True
    
    return False


@action(name="CheckUncertaintyAction")
async def check_uncertainty(output: str) -> bool:
    """Check if output shows high uncertainty that needs disclaimer"""
    uncertainty_markers = [
        "i'm not sure",
        "i don't know",
        "uncertain",
        "might be",
        "possibly",
        "could be wrong",
        "speculating",
    ]
    
    output_lower = output.lower()
    
    uncertainty_count = sum(
        1 for marker in uncertainty_markers 
        if marker in output_lower
    )
    
    return uncertainty_count >= 2


@action(name="CheckGuaranteeAction")
async def check_guarantee(output: str) -> bool:
    """Check if output contains investment guarantees"""
    guarantee_patterns = [
        r"will\s+definitely",
        r"guaranteed\s+to",
        r"100%\s+certain",
        r"cannot\s+fail",
        r"sure\s+thing",
    ]
    
    output_lower = output.lower()
    
    for pattern in guarantee_patterns:
        if re.search(pattern, output_lower):
            return True
    
    return False


# ========== BULL-BEAR DEBATE SPECIFIC ACTIONS ==========

@action()
async def check_disclaimer(bot_message: str) -> bool:
    """Check if the bot message contains appropriate disclaimers."""
    disclaimer_keywords = [
        "not financial advice",
        "informational purposes",
        "consult a financial advisor",
        "past performance",
        "investment risks",
        "do your own research",
        "disclaimer",
        "no guarantee"
    ]
    
    message_lower = bot_message.lower()
    return any(keyword in message_lower for keyword in disclaimer_keywords)


@action()
async def check_toxicity(text: str) -> bool:
    """Check if text contains toxic or unprofessional content."""
    toxic_patterns = [
        "idiot", "stupid", "dumb", "moron",
        "garbage", "trash", "worthless",
        "hate", "terrible person"
    ]
    
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in toxic_patterns)


@action()
async def check_financial_safety(text: str) -> bool:
    """Check if text contains unsafe financial claims."""
    unsafe_patterns = [
        "guaranteed return",
        "will definitely",
        "100% certain",
        "can't lose",
        "risk-free",
        "sure thing",
        "guaranteed profit"
    ]
    
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in unsafe_patterns)
