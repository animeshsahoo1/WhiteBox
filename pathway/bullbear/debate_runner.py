"""
Bull-Bear Debate Runner
Orchestrates the debate and generates facilitator report in a single synchronous call.
"""
import os
import sys
import json
from typing import Dict, Any, TypedDict, Annotated, Optional
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv
from pathway.xpacks.llm import llms

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic_memory.memory_system import AgenticMemorySystem
from bullbear.researchers.bull_researcher import create_bull_researcher
from bullbear.researchers.bear_researcher import create_bear_researcher
from redis_cache import get_redis_client, get_reports_for_symbol, _build_symbol_key

load_dotenv()


# ============================================================
# STATE DEFINITIONS
# ============================================================
class InvestDebateState(TypedDict):
    bull_history: Annotated[str, "Bullish conversation history"]
    bear_history: Annotated[str, "Bearish conversation history"]
    history: Annotated[str, "Full conversation history"]
    current_response: Annotated[str, "Latest response"]
    count: Annotated[int, "Number of exchanges"]
    last_speaker: Annotated[str, "Last agent who spoke"]


class BullBearState(TypedDict):
    company_of_interest: Annotated[str, "Company/Symbol being analyzed"]
    market_report: Annotated[str, "Market analysis report"]
    sentiment_report: Annotated[str, "Sentiment analysis report"]
    news_report: Annotated[str, "News analysis report"]
    fundamentals_report: Annotated[str, "Fundamental analysis report"]
    investment_debate_state: Annotated[InvestDebateState, "Debate state"]
    sender: Annotated[str, "Current sender"]
    max_rounds: Annotated[int, "Maximum debate rounds"]


# ============================================================
# CONDITIONAL LOGIC
# ============================================================
def should_continue_debate(state: BullBearState) -> str:
    """Determine if debate should continue or end."""
    debate_state = state["investment_debate_state"]
    max_rounds = state.get("max_rounds", 2)
    
    if debate_state["count"] >= 2 * max_rounds:
        return "end"
    
    last_speaker = debate_state.get("last_speaker", "")
    
    if last_speaker == "bull_researcher":
        return "bear_researcher"
    elif last_speaker == "bear_researcher":
        return "bull_researcher"
    else:
        return "bull_researcher"


# ============================================================
# GRAPH SETUP
# ============================================================
def create_bull_bear_graph(llm, max_rounds: int = 2):
    """Create the LangGraph workflow for bull-bear debate."""
    session_id = str(uuid4())[:8]
    
    bear_memory = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model="openai/gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        collection_name=f"bear_memories_{session_id}",
    )

    bull_memory = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model="openai/gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        collection_name=f"bull_memories_{session_id}",
    )

    bull_node = create_bull_researcher(llm, bull_memory)
    bear_node = create_bear_researcher(llm, bear_memory)
    
    workflow = StateGraph(BullBearState)
    workflow.add_node("bull_researcher", bull_node)
    workflow.add_node("bear_researcher", bear_node)
    workflow.add_edge(START, "bull_researcher")
    
    workflow.add_conditional_edges(
        "bull_researcher",
        should_continue_debate,
        {"bear_researcher": "bear_researcher", "end": END},
    )
    
    workflow.add_conditional_edges(
        "bear_researcher",
        should_continue_debate,
        {"bull_researcher": "bull_researcher", "end": END},
    )
    
    return workflow.compile()


# ============================================================
# FACILITATOR REPORT GENERATOR
# ============================================================
def generate_facilitator_report(
    symbol: str,
    bull_history: str,
    bear_history: str,
    total_exchanges: int,
    max_rounds: int
) -> str:
    """Generate facilitator report using LLM."""
    
    llm = llms.LiteLLMChat(
        model="openrouter/openai/gpt-4o-mini",
        temperature=0.3,
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base="https://openrouter.ai/api/v1",
    )
    
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    system_prompt = f"""You are a Senior Financial Analyst acting as a Debate Facilitator for {symbol}.

Your role is to:
1. **Summarize** the bull-bear debate objectively
2. **Identify** key arguments from both sides
3. **Highlight** consensus points and major disagreements
4. **Assess** the strength of each position
5. **Provide** a balanced market outlook based on the debate
6. **Recommend** actionable insights with a clear BUY/HOLD/SELL recommendation

Output a well-structured markdown report with these sections:
- Executive Summary
- Bull Arguments (top 3-5 points)
- Bear Arguments (top 3-5 points)
- Areas of Agreement
- Major Disagreements
- Facilitator's Assessment (with BUY/HOLD/SELL recommendation)
- Risk Considerations
- Action Items

Be objective and balanced. Include confidence level (High/Medium/Low).
"""

    user_prompt = f"""Analyze this bull-bear debate for {symbol}:

**BULL ARGUMENTS:**
{bull_history}

**BEAR ARGUMENTS:**
{bear_history}

**Debate Info:**
- Total Exchanges: {total_exchanges}
- Rounds Completed: {max_rounds}
- Timestamp: {current_time} UTC

Generate a comprehensive facilitator report in markdown format.
End with "Last Analysis: {current_time} UTC"
"""

    import pandas as pd
    import pathway as pw
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    df = pw.debug.table_to_pandas(
        pw.debug.table_from_pandas(pd.DataFrame({"m": [messages]}))
        .select(reply=llm(pw.this.m))
    )
    
    report = df["reply"].iloc[0]
    return report


def extract_recommendation(report: str) -> str:
    """Extract BUY/HOLD/SELL recommendation from report."""
    report_upper = report.upper()
    
    if "STRONG BUY" in report_upper:
        return "STRONG BUY"
    elif "STRONG SELL" in report_upper:
        return "STRONG SELL"
    elif "BUY" in report_upper and "SELL" not in report_upper:
        return "BUY"
    elif "SELL" in report_upper and "BUY" not in report_upper:
        return "SELL"
    elif "HOLD" in report_upper:
        return "HOLD"
    else:
        return "HOLD"


def save_facilitator_report(symbol: str, report: str, reports_dir: str = None):
    """Save facilitator report to Redis and file."""
    
    # Save to Redis
    try:
        client = get_redis_client()
        symbol_key = _build_symbol_key(symbol)
        
        entry = {
            "symbol": symbol,
            "report_type": "facilitator",
            "content": report,
            "last_updated": datetime.utcnow().isoformat(),
            "received_at": datetime.utcnow().isoformat(),
        }
        
        client.hset(symbol_key, "facilitator", json.dumps(entry))
        client.sadd("reports:symbols", symbol)
        print(f"✅ Saved facilitator report to Redis for {symbol}")
    except Exception as e:
        print(f"⚠️  Failed to save to Redis: {e}")
    
    # Save to file
    if reports_dir is None:
        reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports", "facilitator")
    
    symbol_dir = os.path.join(reports_dir, symbol)
    os.makedirs(symbol_dir, exist_ok=True)
    
    report_path = os.path.join(symbol_dir, "facilitator_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✅ Saved facilitator report to {report_path}")
    return report_path


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def run_debate_and_generate_report(
    symbol: str,
    max_rounds: int = 2
) -> Dict[str, Any]:
    """
    Run bull-bear debate and generate facilitator report.
    
    This is a synchronous function that:
    1. Fetches reports from Redis
    2. Runs the LangGraph debate
    3. Generates facilitator report
    4. Saves to Redis and file
    5. Returns the result
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        max_rounds: Number of debate rounds (default 2)
        
    Returns:
        Dict with status, facilitator_report, recommendation, etc.
    """
    symbol = symbol.upper()
    
    print(f"\n{'='*60}")
    print(f"🎭 Starting Bull-Bear Debate for {symbol}")
    print(f"   Max Rounds: {max_rounds}")
    print(f"{'='*60}\n")
    
    # Step 1: Fetch reports from Redis
    print("📡 Fetching reports from Redis...")
    
    try:
        reports = get_reports_for_symbol(symbol)
    except Exception as e:
        raise ValueError(f"Failed to fetch reports from Redis: {e}")
    
    if not reports:
        raise ValueError(f"No reports found for {symbol}")
    
    market_report = reports.get("market", {}).get("content", "")
    sentiment_report = reports.get("sentiment", {}).get("content", "")
    news_report = reports.get("news", {}).get("content", "")
    fundamental_report = reports.get("fundamental", {}).get("content", "")
    
    missing = []
    if not market_report:
        missing.append("market")
    if not sentiment_report:
        missing.append("sentiment")
    if not news_report:
        missing.append("news")
    if not fundamental_report:
        missing.append("fundamental")
    
    if missing:
        print(f"⚠️  Missing reports: {', '.join(missing)}")
        # Continue anyway with available reports
    
    print(f"✅ Reports loaded:")
    print(f"   Market: {len(market_report)} chars")
    print(f"   Sentiment: {len(sentiment_report)} chars")
    print(f"   News: {len(news_report)} chars")
    print(f"   Fundamental: {len(fundamental_report)} chars")
    
    # Step 2: Run LangGraph debate
    print(f"\n🎭 Running debate ({max_rounds} rounds)...")
    
    llm = llms.LiteLLMChat(
        model="openrouter/openai/gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base="https://openrouter.ai/api/v1",
    )
    
    graph = create_bull_bear_graph(llm, max_rounds)
    
    initial_state: BullBearState = {
        "company_of_interest": symbol,
        "market_report": market_report or "No market data available.",
        "sentiment_report": sentiment_report or "No sentiment data available.",
        "news_report": news_report or "No news data available.",
        "fundamentals_report": fundamental_report or "No fundamental data available.",
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "history": "",
            "current_response": "",
            "count": 0,
            "last_speaker": "",
        },
        "sender": "",
        "max_rounds": max_rounds,
    }
    
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        raise RuntimeError(f"Debate execution failed: {e}")
    
    debate_state = final_state["investment_debate_state"]
    
    print(f"\n✅ Debate completed!")
    print(f"   Total exchanges: {debate_state['count']}")
    
    # Step 3: Generate facilitator report
    print(f"\n📝 Generating facilitator report...")
    
    facilitator_report = generate_facilitator_report(
        symbol=symbol,
        bull_history=debate_state["bull_history"],
        bear_history=debate_state["bear_history"],
        total_exchanges=debate_state["count"],
        max_rounds=max_rounds
    )
    
    recommendation = extract_recommendation(facilitator_report)
    print(f"   Recommendation: {recommendation}")
    
    # Step 4: Save report
    print(f"\n💾 Saving facilitator report...")
    report_path = save_facilitator_report(symbol, facilitator_report)
    
    # Step 5: Return result
    print(f"\n{'='*60}")
    print(f"✅ Complete! Facilitator report ready for {symbol}")
    print(f"{'='*60}\n")
    
    return {
        "status": "success",
        "symbol": symbol,
        "rounds_completed": max_rounds,
        "total_exchanges": debate_state["count"],
        "recommendation": recommendation,
        "facilitator_report": facilitator_report,
        "report_path": report_path,
    }


if __name__ == "__main__":
    # Test run
    result = run_debate_and_generate_report("AAPL", max_rounds=2)
    print(f"\nResult: {result['status']}")
    print(f"Recommendation: {result['recommendation']}")
