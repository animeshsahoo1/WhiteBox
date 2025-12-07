"""
Bull-Bear Debate LangGraph Workflow
Main graph definition connecting all nodes
"""
import logging
from typing import Literal, Optional
from datetime import datetime
import uuid

from langgraph.graph import StateGraph, END, START

from .state import DebateState, create_initial_state
from .nodes import DebateNodes
from .config import get_config, BullBearConfig

logger = logging.getLogger(__name__)


def should_continue_debate(state: DebateState) -> Literal["continue", "conclude"]:
    """
    Determine if the debate should continue or conclude.
    
    Concludes when:
    1. Max rounds reached
    2. No new points available
    3. Both parties have no more arguments
    """
    max_rounds = state.get("max_rounds", 5)
    current_round = state.get("round_number", 0)
    
    print(f"\n  🔄 Checking if debate should continue...")
    print(f"     Current round: {current_round}, Max rounds: {max_rounds}")
    
    # Check max rounds
    if current_round >= max_rounds:
        print(f"  ➡️ CONCLUDE: max rounds ({max_rounds}) reached")
        logger.info(f"Debate concluding: max rounds ({max_rounds}) reached")
        return "conclude"
    
    # Check if there are new points to discuss
    new_points = state.get("new_points", [])
    debate_points = state.get("debate_points", [])
    
    # If no new points and we've had at least 2 rounds
    if not new_points and current_round >= 2:
        print(f"  ➡️ CONCLUDE: no new points to discuss")
        logger.info("Debate concluding: no new points to discuss")
        return "conclude"
    
    # Check if last two points indicate no new arguments
    if len(debate_points) >= 2:
        last_two = debate_points[-2:]
        low_confidence = all(p.get("confidence", 1.0) < 0.3 for p in last_two)
        if low_confidence:
            print(f"  ➡️ CONCLUDE: low confidence in recent points")
            logger.info("Debate concluding: low confidence in recent points")
            return "conclude"
    
    print(f"  ➡️ CONTINUE: proceeding to next round")
    return "continue"


def route_to_speaker(state: DebateState) -> Literal["bull", "bear"]:
    """
    Route to the appropriate speaker based on last speaker.
    
    ASIAN PARLIAMENTARY FORMAT:
    - Normal rounds: Bull speaks first, Bear second
    - Final round: Order is REVERSED - Bear speaks first, Bull gets closing argument
    
    This ensures Bull (who opened) gets the last word (closing rebuttal).
    """
    current_speaker = state.get("current_speaker", "")
    debate_points = state.get("debate_points", [])
    max_rounds = state.get("max_rounds", 5)
    current_round = state.get("round_number", 0)
    
    # Check if we're in the final round
    is_final_round = (current_round == max_rounds - 1) or (current_round >= max_rounds)
    
    # Check current session first
    if debate_points:
        last_point = debate_points[-1]
        last_party = last_point.get("party", "bear")
        
        if is_final_round:
            # ASIAN FORMAT: In final round, reverse order
            # If last was bear, bull speaks (normal)
            # If last was bull, bear speaks (normal within round)
            # But the round itself starts with Bear to let Bull close
            next_speaker = "bear" if last_party == "bull" else "bull"
            print(f"\n  🗣️ ROUTE [FINAL ROUND]: Last was {last_party.upper()}, routing to {next_speaker.upper()} (Bull closes)")
        else:
            # Normal alternation
            next_speaker = "bear" if last_party == "bull" else "bull"
            print(f"\n  🗣️ ROUTE: Last speaker was {last_party.upper()}, routing to {next_speaker.upper()}")
        return next_speaker
    
    # Check if there's a previous session's last speaker
    previous_last_speaker = state.get("previous_session_last_speaker", "")
    if previous_last_speaker:
        next_speaker = "bear" if previous_last_speaker == "bull" else "bull"
        print(f"\n  🗣️ ROUTE: Previous session ended with {previous_last_speaker.upper()}, starting with {next_speaker.upper()}")
        return next_speaker
    
    # Starting a new debate
    if is_final_round:
        # If it's the final round and no points yet, Bear starts (so Bull closes)
        print(f"\n  🗣️ ROUTE [FINAL ROUND]: Starting with BEAR (Bull will close)")
        return "bear"
    else:
        # Default: Bull starts first
        print(f"\n  🗣️ ROUTE: First point goes to BULL")
        return "bull"


def check_needs_rephrase(state: DebateState) -> Literal["rephrase", "commit", "conclude"]:
    """
    Check if the current point needs rephrasing due to uniqueness.
    Returns:
        - 'rephrase': Point not unique, retry
        - 'commit': Point is unique, save it
        - 'conclude': Max retries exceeded, end debate
    """
    current_point = state.get("current_point")
    if not current_point:
        print(f"\n  📝 CHECK REPHRASE: No current point, committing")
        return "commit"
    
    is_unique = current_point.get("is_unique", True)
    retries = state.get("unique_point_retries", 0)
    max_retries = get_config().debate.max_retries_for_unique_point
    
    if not is_unique:
        if retries < max_retries:
            print(f"\n  📝 CHECK REPHRASE: Point not unique, retry {retries+1}/{max_retries}")
            return "rephrase"
        else:
            print(f"\n  📝 CHECK REPHRASE: Max retries ({max_retries}) exceeded, concluding debate")
            return "conclude"
    
    print(f"\n  📝 CHECK REPHRASE: Point is unique, committing")
    return "commit"


def create_debate_graph(config: Optional[BullBearConfig] = None, use_dummy: bool = False) -> StateGraph:
    """
    Create the Bull-Bear debate LangGraph workflow.
    
    Args:
        config: Optional configuration override
        use_dummy: If True, use dummy data for reports/RAG
    
    NEW Graph Structure (with RAG before each point):
    
    START
      │
      ▼
    [fetch_reports]
      │
      ▼
    [compute_deltas]
      │
      ▼
    [fetch_memory_context]
      │
      ▼
    ┌─────────────────────────────────────┐
    │           DEBATE LOOP               │
    │                                     │
    │  [route_to_speaker]                 │
    │       │          │                  │
    │       ▼          ▼                  │
    │  [gen_bull_rag] [gen_bear_rag]      │
    │       │          │                  │
    │       └────┬─────┘                  │
    │            ▼                        │
    │    [fetch_rag_evidence]             │
    │            │                        │
    │       ┌────┴────┐                   │
    │       ▼         ▼                   │
    │   [bull]     [bear]                 │
    │       │         │                   │
    │       └────┬────┘                   │
    │            ▼                        │
    │    [check_uniqueness]               │
    │            │                        │
    │       ┌────┴────┐                   │
    │       ▼         ▼                   │
    │  [rephrase]  [commit]               │
    │       │         │                   │
    │       └────┬────┘                   │
    │            ▼                        │
    │   [should_continue]─────────────────┘
    │            │
    └────────────┼────────────────────────┘
                 │ (conclude)
                 ▼
    [generate_facilitator_report]
                 │
                 ▼
       [save_and_cleanup]
                 │
                 ▼
               END
    """
    
    nodes = DebateNodes(use_dummy=use_dummy)
    
    # Create the graph
    workflow = StateGraph(DebateState)
    
    # Add nodes
    workflow.add_node("fetch_reports", nodes.fetch_reports)
    workflow.add_node("compute_deltas", nodes.compute_deltas)
    workflow.add_node("fetch_memory_context", nodes.fetch_memory_context)
    
    # RAG query generation nodes (before presenting points)
    workflow.add_node("gen_bull_rag_query", nodes.generate_bull_rag_query)
    workflow.add_node("gen_bear_rag_query", nodes.generate_bear_rag_query)
    workflow.add_node("fetch_rag_evidence", nodes.fetch_rag_evidence)
    
    # Point presentation nodes
    workflow.add_node("bull_present", nodes.bull_present_point)
    workflow.add_node("bear_present", nodes.bear_present_point)
    
    # Point validation nodes
    workflow.add_node("check_uniqueness", nodes.check_uniqueness)
    workflow.add_node("rephrase_point", nodes.rephrase_point)
    workflow.add_node("commit_point", nodes.commit_point)
    
    # Final nodes
    workflow.add_node("generate_report", nodes.generate_facilitator_report)
    workflow.add_node("save_cleanup", nodes.save_and_cleanup)
    
    # Define edges
    workflow.add_edge(START, "fetch_reports")
    workflow.add_edge("fetch_reports", "compute_deltas")
    workflow.add_edge("compute_deltas", "fetch_memory_context")
    
    # Route to RAG query generation after memory context
    workflow.add_conditional_edges(
        "fetch_memory_context",
        route_to_speaker,
        {
            "bull": "gen_bull_rag_query",
            "bear": "gen_bear_rag_query"
        }
    )
    
    # After generating RAG query, fetch evidence
    workflow.add_edge("gen_bull_rag_query", "fetch_rag_evidence")
    workflow.add_edge("gen_bear_rag_query", "fetch_rag_evidence")
    
    # After fetching evidence, route to appropriate speaker
    def route_after_rag(state: DebateState) -> Literal["bull", "bear"]:
        """Route to the speaker who generated the RAG query"""
        # Check who's turn it is based on debate points
        debate_points = state.get("debate_points", [])
        
        if debate_points:
            # Use last speaker in current session
            last_party = debate_points[-1].get("party", "bear")
            return "bear" if last_party == "bull" else "bull"
        
        # No points yet - check previous session's last speaker
        previous_last_speaker = state.get("previous_session_last_speaker", "")
        if previous_last_speaker:
            return "bear" if previous_last_speaker == "bull" else "bull"
        
        # Default: Bull starts first
        return "bull"
    
    workflow.add_conditional_edges(
        "fetch_rag_evidence",
        route_after_rag,
        {
            "bull": "bull_present",
            "bear": "bear_present"
        }
    )
    
    # After presenting, check uniqueness directly (RAG already fetched)
    workflow.add_edge("bull_present", "check_uniqueness")
    workflow.add_edge("bear_present", "check_uniqueness")
    
    # After uniqueness check, decide rephrase, commit, or conclude
    workflow.add_conditional_edges(
        "check_uniqueness",
        check_needs_rephrase,
        {
            "rephrase": "rephrase_point",
            "commit": "commit_point",
            "conclude": "generate_report"  # End debate if can't make unique point
        }
    )
    
    # After rephrase, re-check uniqueness (loop until unique or max retries)
    workflow.add_edge("rephrase_point", "check_uniqueness")
    
    # After commit, decide continue or conclude
    workflow.add_conditional_edges(
        "commit_point",
        should_continue_debate,
        {
            "continue": "route_next_speaker",
            "conclude": "generate_report"
        }
    )
    
    # Add a router node for next speaker - routes to RAG query generation
    def route_next_speaker_node(state: DebateState) -> DebateState:
        """Just pass through - routing handled by edges"""
        print(f"\n  🔀 ROUTER NODE: Routing to next speaker's RAG query")
        return state
    
    workflow.add_node("route_next_speaker", route_next_speaker_node)
    
    # Route to RAG query generation (not directly to speaker)
    workflow.add_conditional_edges(
        "route_next_speaker",
        route_to_speaker,
        {
            "bull": "gen_bull_rag_query",
            "bear": "gen_bear_rag_query"
        }
    )
    
    # Final steps
    workflow.add_edge("generate_report", "save_cleanup")
    workflow.add_edge("save_cleanup", END)
    
    return workflow


def compile_debate_graph(config: Optional[BullBearConfig] = None, use_dummy: bool = False):
    """
    Compile the debate graph for execution.
    
    Args:
        config: Optional configuration override
        use_dummy: If True, use dummy data for reports/RAG
    
    Returns:
        Compiled LangGraph application
    """
    workflow = create_debate_graph(config, use_dummy=use_dummy)
    # Increase recursion limit to handle multi-round debates
    return workflow.compile(checkpointer=None)


class BullBearDebate:
    """
    High-level interface for running Bull-Bear debates.
    """
    
    def __init__(self, config: Optional[BullBearConfig] = None, use_dummy: bool = False):
        self.config = config or get_config()
        self.use_dummy = use_dummy
        self.app = compile_debate_graph(self.config, use_dummy=use_dummy)
        # Set higher recursion limit for debates
        self.recursion_limit = 100
    
    def run(
        self,
        symbol: str,
        max_rounds: int = 5,
        session_id: Optional[str] = None,
        room_id: Optional[str] = None
    ) -> dict:
        """
        Run a complete Bull-Bear debate.
        
        Args:
            symbol: Stock symbol to debate
            max_rounds: Maximum debate rounds
            session_id: Optional session ID (generated if not provided)
            room_id: Optional room ID for WebSocket events
            
        Returns:
            Final state dict with facilitator report and recommendation
        """
        if session_id is None:
            session_id = f"{symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        initial_state = create_initial_state(
            symbol=symbol,
            session_id=session_id,
            max_rounds=max_rounds,
            room_id=room_id
        )
        
        print(f"\n{'='*60}")
        print(f"🚀 STARTING BULL-BEAR DEBATE")
        print(f"   Symbol: {symbol}")
        print(f"   Session ID: {session_id}")
        print(f"   Max Rounds: {max_rounds}")
        print(f"{'='*60}")
        
        logger.info(f"Starting Bull-Bear debate for {symbol}, session {session_id}")
        
        # Run the graph with higher recursion limit
        final_state = self.app.invoke(
            initial_state,
            config={"recursion_limit": self.recursion_limit}
        )
        
        print(f"\n{'='*60}")
        print(f"🏁 DEBATE COMPLETED")
        print(f"   Recommendation: {final_state.get('recommendation', 'UNKNOWN')}")
        print(f"   Total Points: {len(final_state.get('debate_points', []))}")
        print(f"{'='*60}")
        
        logger.info(f"Debate completed. Recommendation: {final_state.get('recommendation', 'UNKNOWN')}")
        
        return final_state
    
    def stream(
        self,
        symbol: str,
        max_rounds: int = 5,
        session_id: Optional[str] = None,
        room_id: Optional[str] = None
    ):
        """
        Stream a Bull-Bear debate, yielding state after each node.
        
        Args:
            symbol: Stock symbol to debate
            max_rounds: Maximum debate rounds
            session_id: Optional session ID
            room_id: Optional room ID for WebSocket events
            
        Yields:
            State dict after each node execution
        """
        if session_id is None:
            session_id = f"{symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        initial_state = create_initial_state(
            symbol=symbol,
            session_id=session_id,
            max_rounds=max_rounds,
            room_id=room_id
        )
        
        logger.info(f"Streaming Bull-Bear debate for {symbol}")
        
        for event in self.app.stream(
            initial_state,
            config={"recursion_limit": self.recursion_limit}
        ):
            yield event
    
    def get_result_summary(self, final_state: dict) -> dict:
        """
        Get a summary of the debate result.
        
        Args:
            final_state: Final state from run()
            
        Returns:
            Summary dict with key information
        """
        return {
            "symbol": final_state.get("symbol"),
            "session_id": final_state.get("session_id"),
            "recommendation": final_state.get("recommendation"),
            "total_rounds": final_state.get("round_number", 0),
            "total_points": len(final_state.get("debate_points", [])),
            "facilitator_report": final_state.get("final_facilitator_report", ""),
            "conclusion_reason": final_state.get("conclusion_reason", ""),
            "started_at": final_state.get("started_at"),
            "completed_at": final_state.get("updated_at"),
            "errors": final_state.get("errors", [])
        }
