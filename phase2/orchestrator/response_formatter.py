"""Response formatting utilities for orchestrator"""

from typing import Dict, Any, List
import json


def format_strategy_response(
    hypothesis: Dict[str, Any],
    strategies: List[Dict[str, Any]],
    market: Dict[str, Any],
    phase1: Dict[str, Any]
) -> str:
    """
    Format conversational response with strategies and risk tiers
    
    Args:
        hypothesis: Top hypothesis used for strategy selection
        strategies: List of strategies with risk assessments
        market: Current market conditions
        phase1: Phase 1 reports summary
    
    Returns:
        Formatted markdown response
    """
    
    response = f"""
**Based on Current Market Hypothesis:**
_{hypothesis['statement']}_ (Confidence: {hypothesis['confidence']:.0%})

**Supporting Evidence:**
"""
    
    for i, evidence in enumerate(hypothesis['supporting_evidence'], 1):
        response += f"\n{i}. {evidence}"
    
    response += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    response += "## 📊 Recommended Strategies\n\n"
    
    # Format each strategy
    for i, strategy in enumerate(strategies, 1):
        perf = strategy.get("performance_metrics", {})
        trade_stats = perf.get("trade_statistics", {})
        risk_metrics = perf.get("risk_metrics", {})
        risk_tiers = strategy.get("risk_tiers", {})
        ranking = strategy.get("ranking", {})
        
        response += f"""
### {i}. **{strategy['name']}** (Rank #{ranking.get('rank_position', 'N/A')})

**30-Day Performance:**
- Win Rate: {trade_stats.get('win_rate', 0):.1%}
- Sharpe Ratio: {risk_metrics.get('sharpe_ratio', 0):.2f}
- Total Return: {perf.get('returns', {}).get('total_return', 0):.1%}
- Max Drawdown: {risk_metrics.get('max_drawdown', 0):.1%}
- Total Trades: {trade_stats.get('total_trades', 0)}

**Risk Tier Options:**

"""
        
        # No-Risk Tier
        no_risk = risk_tiers.get("no_risk", {})
        no_risk_params = no_risk.get("recommended_params", {})
        response += f"""
**🛡️ NO-RISK TIER** ({no_risk.get('approval_status', 'unknown').upper()})
- Position Size: {no_risk_params.get('position_size_pct', 0):.1f}%
- Stop Loss: {no_risk_params.get('stop_loss_pct', 0):.1f}%
- Take Profit: {no_risk_params.get('take_profit_pct', 0):.1f}%
- Max Hold: {no_risk_params.get('max_hold_days', 0)} days
- Reasoning: {no_risk.get('reasoning', 'N/A')[:100]}...
"""
        
        if no_risk.get('warnings'):
            response += f"\n- ⚠️ Warnings: {', '.join(no_risk['warnings'])}\n"
        
        # Neutral Tier
        neutral = risk_tiers.get("neutral", {})
        neutral_params = neutral.get("recommended_params", {})
        recommended_marker = " ⭐ **RECOMMENDED**" if is_recommended_tier(market, "neutral") else ""
        response += f"""
**⚖️ NEUTRAL TIER** ({neutral.get('approval_status', 'unknown').upper()}){recommended_marker}
- Position Size: {neutral_params.get('position_size_pct', 0):.1f}%
- Stop Loss: {neutral_params.get('stop_loss_pct', 0):.1f}%
- Take Profit: {neutral_params.get('take_profit_pct', 0):.1f}%
- Max Hold: {neutral_params.get('max_hold_days', 0)} days
- Reasoning: {neutral.get('reasoning', 'N/A')[:100]}...
"""
        
        # Aggressive Tier
        aggressive = risk_tiers.get("aggressive", {})
        aggressive_params = aggressive.get("recommended_params", {})
        response += f"""
**🔥 AGGRESSIVE TIER** ({aggressive.get('approval_status', 'unknown').upper()})
- Position Size: {aggressive_params.get('position_size_pct', 0):.1f}%
- Stop Loss: {aggressive_params.get('stop_loss_pct', 0):.1f}%
- Take Profit: {aggressive_params.get('take_profit_pct', 0):.1f}%
- Max Hold: {aggressive_params.get('max_hold_days', 0)} days
- Leverage: {aggressive_params.get('max_leverage', 1.0):.1f}x
- Reasoning: {aggressive.get('reasoning', 'N/A')[:100]}...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Market context
    response += f"""
## 🌐 Current Market Context

**Market Conditions:**
- Volatility: **{market.get('volatility', 'N/A').upper()}** (VIX: {market.get('vix', 0):.1f})
- Current Price: ${market.get('current_price', 0):.2f}

**Phase 1 Intelligence Summary:**
- Facilitator Stance: {extract_facilitator_stance(phase1)}
- Sentiment Score: {extract_sentiment_score(phase1)}
- News Risk Level: {extract_news_risk(phase1)}

---

**💡 Recommendation:** Given the **{market.get('volatility', 'moderate')}** volatility environment and current market intelligence, 
**{recommend_tier(market)}** risk parameters are most appropriate for this market condition.

**❓ Follow-up:** Would you like to see detailed entry/exit rules for any of these strategies, 
or explore alternative strategies for a different market scenario?
"""
    
    return response


def is_recommended_tier(market: Dict[str, Any], tier: str) -> bool:
    """Determine if tier should be marked as recommended"""
    volatility = market.get('volatility', 'moderate')
    
    if volatility == 'low' and tier == 'neutral':
        return True
    elif volatility == 'moderate' and tier == 'neutral':
        return True
    elif volatility == 'high' and tier == 'no_risk':
        return True
    
    return False


def recommend_tier(market: Dict[str, Any]) -> str:
    """Recommend tier based on market conditions"""
    volatility = market.get('volatility', 'moderate')
    vix = market.get('vix', 20)
    
    if vix > 30 or volatility == 'high':
        return 'NO-RISK'
    elif vix < 15 or volatility == 'low':
        return 'NEUTRAL to AGGRESSIVE'
    else:
        return 'NEUTRAL'


def extract_facilitator_stance(phase1: Dict[str, Any]) -> str:
    """Extract facilitator stance from Phase 1 reports"""
    try:
        facilitator = json.loads(phase1.get('facilitator', '{}'))
        return facilitator.get('stance', 'Unknown')
    except:
        return 'Unknown'


def extract_sentiment_score(phase1: Dict[str, Any]) -> str:
    """Extract sentiment score from Phase 1 reports"""
    try:
        sentiment = json.loads(phase1.get('sentiment', '{}'))
        score = sentiment.get('score', 0)
        return f"{score:+.2f}"
    except:
        return 'N/A'


def extract_news_risk(phase1: Dict[str, Any]) -> str:
    """Extract news risk level from Phase 1 reports"""
    try:
        news = json.loads(phase1.get('news', '{}'))
        risk_keywords = ['bankruptcy', 'lawsuit', 'investigation', 'fraud']
        
        news_text = str(news).lower()
        if any(keyword in news_text for keyword in risk_keywords):
            return 'HIGH'
        
        return 'LOW'
    except:
        return 'N/A'


def format_simple_response(message: str) -> str:
    """Format simple text response"""
    return f"\n{message}\n"


def format_error_response(error: str) -> str:
    """Format error message"""
    return f"""
❌ **Error Occurred**

{error}

Please try again or contact support if the issue persists.
"""
