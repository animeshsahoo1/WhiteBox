"""
Bull-Bear Debate Graph using LangGraph
Uses actual bull/bear researchers from all_agents folder.
"""
import os
import sys
import json
from typing import Dict, Any, TypedDict, Annotated
from datetime import datetime
from pathlib import Path

from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from all_agents.researchers.bull_researcher import create_bull_researcher
from all_agents.researchers.bear_researcher import create_bear_researcher

load_dotenv()


#MEMORIES -> 
from agentic_memory.memory_system import AgenticMemorySystem

# ============================================================
# STATE DEFINITION (Minimal for bull-bear debate)
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


# ============================================================
# CONDITIONAL LOGIC
# ============================================================
def should_continue_debate(state: BullBearState) -> str:
    """Determine if debate should continue or end."""
    debate_state = state["investment_debate_state"]
    max_rounds = state.get("max_rounds", 2)
    
    # Check if we've completed enough rounds (2 exchanges per round)
    if debate_state["count"] >= 2 * max_rounds:
        return "end"
    
    # Alternate between bull and bear
    last_speaker = debate_state.get("last_speaker", "")
    
    if last_speaker == "bull_researcher":
        return "bear_researcher"
    elif last_speaker == "bear_researcher":
        return "bull_researcher"
    else:
        # First round, start with bull
        return "bull_researcher"

from uuid import uuid4 #to solve collection id proobelm

# ============================================================
# GRAPH SETUP
# ============================================================
def create_bull_bear_graph(llm, max_rounds: int = 2):
    """
    Create the LangGraph workflow for bull-bear debate.
    
    Args:
        llm: The LLM instance (Pathway LiteLLMChat)
        max_rounds: Maximum debate rounds
        
    Returns:
        Compiled graph
    """
    # Use unique collection names for each memory system to avoid ChromaDB conflicts
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
    

    # Create agent nodes
    bull_node = create_bull_researcher(llm, bull_memory)
    bear_node = create_bear_researcher(llm, bear_memory)
    
    # Create workflow
    workflow = StateGraph(BullBearState)
    
    # Add nodes
    workflow.add_node("bull_researcher", bull_node)
    workflow.add_node("bear_researcher", bear_node)
    
    # Set entry point
    workflow.add_edge(START, "bull_researcher")
    
    # Add conditional edges for alternating debate
    workflow.add_conditional_edges(
        "bull_researcher",
        should_continue_debate,
        {
            "bear_researcher": "bear_researcher",
            "end": END,
        },
    )
    
    workflow.add_conditional_edges(
        "bear_researcher",
        should_continue_debate,
        {
            "bull_researcher": "bull_researcher",
            "end": END,
        },
    )
    
    # Compile and return
    return workflow.compile()


# ============================================================
# MAIN DEBATE RUNNER
# ============================================================
def run_bull_bear_debate(
    market_report: str,
    sentiment_report: str,
    news_report: str,
    fundamental_report: str,
    symbol: str = "UNKNOWN",
    max_rounds: int = 2
) -> Dict[str, Any]:
    """
    Run bull-bear debate using LangGraph with actual agents.
    
    Args:
        market_report: Market analysis report
        sentiment_report: Sentiment analysis report  
        news_report: News analysis report
        fundamental_report: Fundamental analysis report
        symbol: Stock symbol
        max_rounds: Maximum number of debate rounds
        
    Returns:
        Dict containing debate results and path to saved JSON
    """
    
    print(f"\n{'='*60}")
    print(f"🎭 Starting Bull-Bear Debate for {symbol}")
    print(f"{'='*60}\n")
    
    # Initialize LLM (Pathway LiteLLMChat)
    from pathway.xpacks.llm import llms
    
    llm = llms.LiteLLMChat(
        model="openrouter/openai/gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base="https://openrouter.ai/api/v1",
    )
    
    # Create the graph
    graph = create_bull_bear_graph(llm, max_rounds)
    
    # Initialize state
    initial_state: BullBearState = {
        "company_of_interest": symbol,
        "market_report": market_report,
        "sentiment_report": sentiment_report,
        "news_report": news_report,
        "fundamentals_report": fundamental_report,
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
    
    # Run the graph
    print("🚀 Running debate graph...\n")
    
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        print(f"❌ Error running graph: {e}")
        raise
    
    # Extract results
    debate_state = final_state["investment_debate_state"]
    
    # Prepare debate points for JSON
    debate_points = {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "rounds_completed": max_rounds,
        "total_exchanges": debate_state["count"],
        "bull_history": debate_state["bull_history"],
        "bear_history": debate_state["bear_history"],
        "full_debate_transcript": debate_state["history"],
        "final_response": debate_state.get("current_response", ""),
        "summary": {
            "bull_stance": "Bullish arguments based on reports and analysis",
            "bear_stance": "Bearish counterarguments identifying risks",
            "total_rounds": debate_state["count"],
            "last_speaker": debate_state.get("last_speaker", "unknown")
        }
    }
    
    # Save to JSON file
    output_file = os.path.join(
        os.path.dirname(__file__),
        "debate_points.json"
    )
    
    with open(output_file, 'w') as f:
        json.dump(debate_points, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Debate completed!")
    print(f"📊 Total exchanges: {debate_state['count']}")
    print(f"📄 Saved to: {output_file}")
    print(f"{'='*60}\n")
    
    return {
        "status": "completed",
        "symbol": symbol,
        "rounds": max_rounds,
        "total_exchanges": debate_state["count"],
        "output_file": output_file,
        "debate_points": debate_points
    }


if __name__ == "__main__":
    # Test the debate function
    print("\n🧪 Running test debate...\n")
    
    test_result = run_bull_bear_debate(
        market_report="Strong bullish trends with high volume. RSI indicates momentum.",
        sentiment_report="Positive sentiment across social media. Retail interest growing.",
        news_report="Company announces new product launch. Analyst upgrades.",
        fundamental_report="Revenue growth of 20% YoY. Strong balance sheet.",
        symbol="AAPL",
        max_rounds=2
    )
    
    print(f"\n✅ Test completed: {test_result['status']}")
    print(f"📊 Total exchanges: {test_result['total_exchanges']}")
    print(f"📄 Output file: {test_result['output_file']}")
