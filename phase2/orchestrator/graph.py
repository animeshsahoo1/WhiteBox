"""
Strategy Orchestrator Graph - Phase 2

This module implements the LangGraph workflow for the Strategy Orchestrator.
It builds the state graph by connecting nodes, defining edges, and setting routing logic.

All node functions are in nodes.py
All tool functions are in tools.py
All state definitions are in state.py
"""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    # Classification & Routing
    classify_query,
    route_after_classification,
    
    # Strategy Extraction
    extract_user_strategy,
    
    # Hypothesis Handling
    decide_hypothesis_need,
    route_hypothesis_decision,
    fetch_hypotheses,
    
    # Strategy Search
    build_search_params,
    search_strategy_bank,
    
    # Web Search & Synthesis
    decide_web_search_need,
    route_after_web_search_decision,
    synthesize_strategy_from_web,
    route_after_synthesis,
    
    # Backtesting & Risk Analysis
    backtest_strategy,
    analyze_risk,
    
    # Response Generation
    generate_response,
    update_memory
)
from .tools import TRADING_SYMBOL


# ============================================================================
# BUILD LANGGRAPH
# ============================================================================

def build_graph():
    """Build the LangGraph workflow"""
    
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("classify_query", classify_query)
    workflow.add_node("extract_user_strategy", extract_user_strategy)
    workflow.add_node("decide_hypothesis_need", decide_hypothesis_need)
    workflow.add_node("fetch_hypotheses", fetch_hypotheses)
    workflow.add_node("build_search_params", build_search_params)
    workflow.add_node("search_strategy_bank", search_strategy_bank)
    workflow.add_node("synthesize_strategy_from_web", synthesize_strategy_from_web)
    workflow.add_node("backtest_strategy", backtest_strategy)
    workflow.add_node("analyze_risk", analyze_risk)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("update_memory", update_memory)
    workflow.add_node("decide_web_search_need", decide_web_search_need)
    
    # Set entry point
    workflow.set_entry_point("classify_query")
    
    # Add edges
    workflow.add_conditional_edges(
        "classify_query",
        route_after_classification,
        {
            "strategy_input": "extract_user_strategy",
            "is_hypothesis_needed": "decide_hypothesis_need"
        }
    )
    
    workflow.add_edge("extract_user_strategy", "backtest_strategy")
    
    workflow.add_conditional_edges(
        "decide_hypothesis_need",
        route_hypothesis_decision,
        {
            "need_hypothesis": "fetch_hypotheses",
            "hypothesis_not_needed": "build_search_params"
        }
    )
    
    workflow.add_edge("fetch_hypotheses", "build_search_params")
    workflow.add_edge("build_search_params", "search_strategy_bank")
    workflow.add_edge("search_strategy_bank", "decide_web_search_need")
    
    workflow.add_conditional_edges(
        "decide_web_search_need",
        route_after_web_search_decision,
        {
            "found_strategy": "analyze_risk",
            "no_strategy_found": "synthesize_strategy_from_web",
        }
    )
    
    workflow.add_conditional_edges(
        "synthesize_strategy_from_web",
        route_after_synthesis,
        {
            "no_valid_strategy": "generate_response",
            "strategy_generated": "backtest_strategy",
        }
    )
    
    workflow.add_edge("backtest_strategy", "analyze_risk")
    workflow.add_edge("analyze_risk", "generate_response")
    workflow.add_edge("generate_response", "update_memory")
    workflow.add_edge("update_memory", END)
    
    return workflow.compile()


def print_graph(graph):
    """Print the LangGraph structure"""

    # New visualization using graph helper
    graph_repr = graph.get_graph()  # returns a visualizable graph helper

    # Generate Mermaid diagram as PNG
    mermaid_png_bytes = graph_repr.draw_mermaid_png()

    # Display PNG (Jupyter-safe)
    from IPython.display import Image, display
    display(Image(mermaid_png_bytes))


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution loop"""
    
    print("=" * 70)
    print("STRATEGY ORCHESTRATOR - Phase 2 (Updated)")
    print("=" * 70)
    print("\nWelcome! I'm your AI Investment Assistant.")
    print(f"Currently trading: {TRADING_SYMBOL}")
    print("\nSupported queries:")
    print("  - 'Show me momentum strategies'")
    print("  - 'Analyze this strategy: buy when RSI < 30 and MACD positive'")
    print("  - 'What should I trade now?'")
    print("  - 'Give me low-risk RSI strategies'")
    print("  - 'Top performing strategies'")
    print("\nType 'quit' or 'exit' to end.\n")
    
    # Build and print graph
    graph = build_graph()
    print_graph(graph)  # Commented out - causes timeout with mermaid.ink
    
    # # Initialize conversation history
    # conversation_history = []
    
    # while True:
    #     # Get user input
    #     user_query = input("\n🤔 You: ").strip()
        
    #     if not user_query:
    #         continue
        
    #     if user_query.lower() in ['quit', 'exit', 'q']:
    #         print("\n👋 Goodbye! Happy trading!\n")
    #         break
        
    #     # Initialize state
    #     initial_state = {
    #         "messages": [HumanMessage(content=user_query)],
    #         "user_query": user_query,
    #         "query_type": "",
    #         "user_inputted_strategy": {},
    #         "need_hypothesis": False,
    #         "hypotheses": [],
    #         "search_params": {},
    #         "strategies_found": [],
    #         "selected_strategy": {},
    #         "backtest_results": {},
    #         "web_search_results": [],
    #         "risk_analyses": {},
    #         "final_response": "",
    #         "conversation_history": conversation_history
    #     }
        
    #     print("\n🤖 Processing...")
        
    #     try:
    #         # Run graph
    #         final_state = graph.invoke(initial_state)
            
    #         # Print response
    #         print("\n" + "=" * 70)
    #         print("📊 ORCHESTRATOR RESPONSE:")
    #         print("=" * 70)
    #         print(final_state["final_response"])
    #         print("=" * 70)
            
    #         # Update conversation history
    #         conversation_history = final_state.get("conversation_history", [])
            
    #     except Exception as e:
    #         print(f"\n❌ Error: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         print("Please try again or rephrase your query.\n")


if __name__ == "__main__":
    main()
    # import os
    # if not os.getenv("ANTHROPIC_API_KEY"):
    #     print("⚠️  Warning: ANTHROPIC_API_KEY environment variable not set!")
    #     print("Please set it: export ANTHROPIC_API_KEY='your-key'\n")
    
    # try:
    #     main()
    # except KeyboardInterrupt:
    #     print("\n\n👋 Interrupted. Goodbye!\n")
    # except Exception as e:
    #     print(f"\n❌ Fatal error: {e}\n")
    #     import traceback
    #     traceback.print_exc()
