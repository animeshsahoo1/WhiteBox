"""
LangGraph Nodes for Bull-Bear Debate
Each node represents a step in the debate workflow
"""
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from .state import DebateState, DebatePoint, DebateParty, create_initial_state
from .clients import SyncReportsClient, SyncRAGClient, Report
from .cache_manager import CacheManager, DeltaComputer, FacilitatorValidator
from .memory_manager import MemoryManager
from .debate_points import DebatePointsManager, convert_dict_to_debate_point
from .llm_utils import (
    LLMClient, 
    parse_json_safely,
    DELTA_EXTRACTION_PROMPT,
    FACILITATOR_VALIDATION_PROMPT,
    BULL_POINT_PROMPT,
    BEAR_POINT_PROMPT,
    UNIQUENESS_CHECK_PROMPT,
    FACILITATOR_CONCLUSION_PROMPT,
    REPHRASE_POINT_PROMPT,
    RAG_QUERY_GENERATION_PROMPT
)
from .config import get_config

# Event publishing imports
try:
    from event_publisher import publish_debate_point, publish_debate_progress, publish_recommendation, publish_graph_state
    print("✅ [BullBear] Event publisher imported successfully (direct)")
except ImportError as e1:
    try:
        from ..event_publisher import publish_debate_point, publish_debate_progress, publish_recommendation, publish_graph_state
        print("✅ [BullBear] Event publisher imported successfully (relative)")
    except ImportError as e2:
        # Fallback if event_publisher not available
        print(f"⚠️ [BullBear] Event publisher NOT available - events will NOT be published")
        print(f"   Import error 1: {e1}")
        print(f"   Import error 2: {e2}")
        publish_debate_point = None
        publish_debate_progress = None
        publish_recommendation = None
        publish_graph_state = None

logger = logging.getLogger(__name__)


class DebateNodes:
    """
    Collection of nodes for the Bull-Bear debate LangGraph.
    Each method is a node that takes state and returns updated state.
    """
    
    def __init__(self, use_dummy: bool = False):
        print("🔧 [DebateNodes] Initializing debate nodes...")
        print(f"    use_dummy: {use_dummy}")
        self.config = get_config()
        self.llm = LLMClient(self.config.llm)  # Initialize LLM first
        self.reports_client = SyncReportsClient(self.config.reports, use_dummy=use_dummy)
        self.rag_client = SyncRAGClient(self.config.rag, use_dummy=use_dummy)
        self.cache_manager = CacheManager(self.config.debate)
        self.delta_computer = DeltaComputer(llm=self.llm)  # Pass LLM for smart extraction
        self.facilitator_validator = FacilitatorValidator(llm=self.llm)  # Pass LLM for market analysis
        self.memory_manager = None  # Initialized per session
        self.debate_points_manager = DebatePointsManager(self.config.debate)
        print("✅ [DebateNodes] Initialization complete")
    
    # ============================================================
    # SHARED HELPER METHODS
    # ============================================================
    
    def _publish_event(self, state: DebateState, event_type: str, data: Dict[str, Any]) -> None:
        """Safely publish an event to the room_id channel."""
        room_id = state.get("room_id", f"symbol:{state.get('symbol', 'UNKNOWN')}")
        print(f"🔔 [BullBear] Publishing {event_type} to room: {room_id}")
        try:
            if event_type == "debate_point" and publish_debate_point:
                publish_debate_point(room_id, data)
                print(f"   ✅ debate_point published")
            elif event_type == "debate_progress" and publish_debate_progress:
                publish_debate_progress(room_id, data)
                print(f"   ✅ debate_progress published")
            elif event_type == "recommendation" and publish_recommendation:
                publish_recommendation(room_id, data)
                print(f"   ✅ recommendation published")
            elif event_type == "graph_state" and publish_graph_state:
                publish_graph_state(room_id, data)
                print(f"   ✅ graph_state published")
            else:
                print(f"   ⚠️ No handler for {event_type} or function is None")
        except Exception as e:
            logger.warning(f"Failed to publish {event_type} event: {e}")
            print(f"   ❌ Failed to publish {event_type}: {e}")
    
    def _get_memory_manager(self, session_id: str, symbol: str = "") -> MemoryManager:
        """Get or create memory manager for symbol (persists across sessions)"""
        if self.memory_manager is None:
            # Use symbol for persistent memory across API calls
            # session_id is only used if symbol not provided
            memory_id = f"bullbear_{symbol}" if symbol else f"debate_{session_id}"
            print(f"  🧠 [DebateNodes] Creating memory manager: {memory_id}")
            self.memory_manager = MemoryManager(
                config=self.config.memory,
                user_id=memory_id
            )
        return self.memory_manager
    
    def _generate_rag_query_for_party(self, state: DebateState, party: str) -> DebateState:
        """
        Shared method to generate RAG query for either party.
        
        Args:
            state: Current debate state
            party: 'bull' or 'bear'
        """
        party_upper = party.upper()
        party_emoji = "🐂" if party == "bull" else "🐻"
        opponent_party = "bear" if party == "bull" else "bull"
        opponent_emoji = "🐻" if party == "bull" else "🐂"
        
        print(f"\n{'='*60}")
        print(f"🔍 NODE: GENERATE {party_upper} RAG QUERY + MEMORY")
        print(f"{'='*60}")
        
        self._publish_event(state, "graph_state", {"symbol": state["symbol"], "current_node": f"gen_{party}_rag_query", "status": "RUNNING"})
        
        # Get opponent's last point
        debate_points = state.get("debate_points", [])
        opponent_point = ""
        if debate_points:
            last_point = debate_points[-1]
            if last_point.get("party") == opponent_party:
                opponent_point = last_point.get("content", "")
                print(f"  {opponent_emoji} {opponent_party.capitalize()}'s last point to counter: {opponent_point[:80]}...")
        
        if not opponent_point:
            print(f"  ℹ️ No opponent point - {party_upper} will start fresh")
        
        # Fetch memory context related to opponent's point
        memory = self._get_memory_manager(state["session_id"], state["symbol"])
        if opponent_point:
            print(f"  🧠 Fetching memory to help counter {opponent_party.capitalize()}'s point...")
            memory_query = f"{party}ish counter to: {opponent_point[:200]}"
            memories = memory.get_debate_context(
                query=memory_query,
                party=party,
                limit=3
            )
            state[f"{party}_memory_context"] = memories
            print(f"    Found {len(memories)} relevant memories")
            if memories:
                for i, mem in enumerate(memories[:2], 1):
                    print(f"      {i}. {mem[:60]}...")
        
        # Build context summary
        context = f"""
News highlights: {state.get('news_report', '')}
Market conditions: {state.get('market_report', '')}
"""
        
        # Set stance description based on party
        if party == "bull":
            stance_description = "optimistic, looking for growth opportunities, positive indicators, bullish signals"
        else:
            stance_description = "cautious, looking for risks, concerns, bearish signals, potential downsides"
        
        # Generate RAG query using LLM
        print(f"  🤖 Generating search query for knowledge base...")
        prompt = RAG_QUERY_GENERATION_PROMPT.format(
            party=party_upper,
            symbol=state["symbol"],
            opponent_point=opponent_point if opponent_point else "No opponent point yet - you are starting the debate",
            stance_description=stance_description,
            context=context
        )
        
        messages = [
            {"role": "system", "content": f"You are a {party}ish analyst generating a search query. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm.complete_json(messages)
            rag_query = response.get("query", "")
            
            if rag_query:
                print(f"  📝 Generated query: {rag_query[:80]}...")
                print(f"  🎯 Intent: {response.get('search_intent', 'N/A')}")
                state["pending_rag_query"] = rag_query
            else:
                print(f"  ℹ️ No RAG query generated")
                state["pending_rag_query"] = None
        except Exception as e:
            logger.error(f"LLM error generating RAG query for {party}: {e}")
            print(f"  ⚠️ LLM error: {e}")
            state["pending_rag_query"] = None
            state["errors"].append(f"RAG query generation failed for {party}: {str(e)}")
        
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: GENERATE {party_upper} RAG QUERY + MEMORY")
        return state
    
    def _present_point_for_party(self, state: DebateState, party: str) -> DebateState:
        """
        Shared method for party to present a point.
        
        Args:
            state: Current debate state
            party: 'bull' or 'bear'
        """
        party_upper = party.upper()
        party_emoji = "🐂" if party == "bull" else "🐻"
        party_enum = DebateParty.BULL if party == "bull" else DebateParty.BEAR
        opponent_party = "bear" if party == "bull" else "bull"
        opponent_emoji = "🐻" if party == "bull" else "🐂"
        prompt_template = BULL_POINT_PROMPT if party == "bull" else BEAR_POINT_PROMPT
        
        print(f"\n{'='*60}")
        print(f"{party_emoji} NODE: {party_upper} PRESENTS POINT")
        print(f"{'='*60}")
        print(f"  Round: {state.get('round_number', 0) + 1}")
        logger.info(f"{party.capitalize()} presenting point")
        
        # Get opponent's last point if any
        opponent_point = ""
        debate_points = state.get("debate_points", [])
        if debate_points:
            last_point = debate_points[-1]
            if last_point.get("party") == opponent_party:
                opponent_point = last_point.get("content", "")
                print(f"  {opponent_emoji} {opponent_party.capitalize()}'s last point: {opponent_point[:80]}...")
        else:
            print(f"  ℹ️ No previous points - {party_upper} starts the debate")
        
        # Build debate history
        debate_history = "\n".join([
            f"[{p.get('party', 'unknown').upper()}]: {p.get('content', '')}"
            for p in debate_points[-6:]  # Last 6 points
        ])
        
        # Build context
        context = f"""
News Report: {state['news_report']}
Sentiment Report: {state['sentiment_report']}
Market Report: {state['market_report']}
Fundamental Report: {state['fundamental_report']}
"""
        
        # Deltas summary
        deltas_summary = "\n".join([
            f"{k}: {len(v.get('new_points', []))} new points"
            for k, v in state.get("report_deltas", {}).items()
            if isinstance(v, dict)
        ])
        
        # Correctness info
        conclusion = state.get("facilitator_conclusion", {})
        correct_status = "CORRECT" if conclusion.get("was_correct") else "INCORRECT" if conclusion.get("was_correct") is False else "UNKNOWN"
        correctness_reasoning = conclusion.get("reasoning", "No previous conclusion")
        
        print(f"  📋 Previous conclusion was: {correct_status}")
        
        # RAG info
        rag_info = state.get("rag_response", "No RAG information available")
        
        # Build prompt
        print(f"  🤖 Calling LLM for {party_upper}'s argument...")
        prompt = prompt_template.format(
            symbol=state["symbol"],
            context=context,
            deltas=deltas_summary,
            correct_status=correct_status,
            correctness_reasoning=correctness_reasoning,
            memory_context="\n".join(state.get(f"{party}_memory_context", [])),
            debate_history=debate_history,
            opponent_point=opponent_point,
            rag_info=rag_info
        )
        
        # Get LLM response with exponential backoff retry
        messages = [
            {"role": "system", "content": f"You are a {party}ish investment analyst. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        response = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.complete_json(messages)
                break  # Success, exit retry loop
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                if attempt < max_retries - 1:
                    logger.warning(f"LLM attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    print(f"  ⚠️ LLM attempt {attempt + 1} failed. Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"LLM error in {party}_present_point after {max_retries} attempts: {e}")
                    print(f"  ❌ LLM error after {max_retries} attempts: {e}")
        
        # Fallback if all retries failed
        if response is None:
            if party == "bull":
                response = {
                    "point": f"Based on the current data for {state['symbol']}, positive indicators suggest upside potential.",
                    "supporting_evidence": ["Report data suggests positive trends"],
                    "confidence": 0.5
                }
            else:
                response = {
                    "point": f"Based on the current data for {state['symbol']}, risk factors warrant caution.",
                    "supporting_evidence": ["Report data suggests potential concerns"],
                    "confidence": 0.5
                }
            state["errors"].append(f"LLM error in {party} presentation after {max_retries} retries")
        
        # Create debate point
        point_id = str(uuid.uuid4())[:8]
        point = DebatePoint(
            id=point_id,
            party=party_enum,
            content=response.get("point", ""),
            supporting_evidence=response.get("supporting_evidence", []),
            counter_to=debate_points[-1].get("id") if opponent_point else None,
            confidence=response.get("confidence", 0.7),
            is_unique=True  # Will be validated in next node
        )
        
        print(f"  {party_emoji} {party_upper}'s point: {point.content[:100]}...")
        print(f"  📊 Confidence: {point.confidence:.0%}")
        
        state["current_point"] = point.to_dict()
        state["current_speaker"] = party
        
        # Publish debate point event
        self._publish_event(state, "debate_point", {
            "symbol": state["symbol"],
            "party": party,
            "status": "SPEAKING",
            "point_id": point_id,
            "content": point.content,
            "confidence": point.confidence,
            "supporting_evidence": point.supporting_evidence,
            "counter_to": point.counter_to,
            "round": state.get("round_number", 0) + 1
        })
        
        # Publish graph state for visualization
        self._publish_event(state, "graph_state", {
            "symbol": state["symbol"],
            "current_node": f"{party}_present",
            "current_speaker": party,
            "round": state.get("round_number", 0) + 1,
            "total_points": len(debate_points) + 1
        })
        
        # Check if RAG query is needed (for additional context)
        if response.get("needs_rag_query") and response.get("rag_query"):
            state["rag_query"] = response["rag_query"]
            print(f"  🔍 RAG query requested: {response['rag_query'][:50]}...")
        else:
            state["rag_query"] = None
        
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: {party_upper} PRESENTS POINT")
        return state
    
    # ============================================================
    # NODE 1: FETCH REPORTS
    # ============================================================
    def fetch_reports(self, state: DebateState) -> DebateState:
        """
        Fetch the 4 reports from the reports API.
        """
        print(f"\n{'='*60}")
        print(f"📥 NODE: FETCH REPORTS")
        print(f"{'='*60}")
        print(f"  Symbol: {state['symbol']}")
        logger.info(f"Fetching reports for {state['symbol']}")
        
        # Publish debate started event
        self._publish_event(state, "debate_progress", {
            "symbol": state["symbol"],
            "status": "STARTED",
            "current_round": 0,
            "max_rounds": state.get("max_rounds", 5),
            "message": "Fetching reports..."
        })
        
        # Publish graph state
        self._publish_event(state, "graph_state", {
            "symbol": state["symbol"],
            "current_node": "fetch_reports",
            "nodes_completed": [],
            "nodes_pending": ["compute_deltas", "fetch_memory_context", "debate_rounds", "generate_report"]
        })
        
        try:
            reports = self.reports_client.fetch_all_reports(state["symbol"])
            facilitator = self.reports_client.fetch_facilitator_report(state["symbol"])
            
            state["news_report"] = reports.get("news", Report("news", "", "", state["symbol"])).content
            state["sentiment_report"] = reports.get("sentiment", Report("sentiment", "", "", state["symbol"])).content
            state["market_report"] = reports.get("market", Report("market", "", "", state["symbol"])).content
            state["fundamental_report"] = reports.get("fundamental", Report("fundamental", "", "", state["symbol"])).content
            
            print(f"  ✅ News report: {len(state['news_report'])} chars")
            print(f"  ✅ Sentiment report: {len(state['sentiment_report'])} chars")
            print(f"  ✅ Market report: {len(state['market_report'])} chars")
            print(f"  ✅ Fundamental report: {len(state['fundamental_report'])} chars")
            
            if facilitator:
                state["facilitator_report"] = facilitator.content
                print(f"  ✅ Previous facilitator report: {len(state['facilitator_report'])} chars")
                
                # Extract last speaker from previous session for turn order
                last_speaker = facilitator.metadata.get("last_speaker", "")
                if last_speaker:
                    state["previous_session_last_speaker"] = last_speaker
                    print(f"  🗣️ Previous session ended with: {last_speaker.upper()}")
            else:
                print(f"  ℹ️ No previous facilitator report")
            
            state["updated_at"] = datetime.utcnow().isoformat()
            logger.info("Reports fetched successfully")
            print(f"✅ NODE COMPLETE: FETCH REPORTS")
            
        except Exception as e:
            error_msg = f"Error fetching reports: {e}"
            logger.error(error_msg)
            print(f"  ❌ ERROR: {error_msg}")
            state["errors"].append(error_msg)
        
        return state
    
    # ============================================================
    # NODE 2: COMPUTE DELTAS
    # ============================================================
    def compute_deltas(self, state: DebateState) -> DebateState:
        """
        Compare new reports with cached reports and compute deltas.
        Also validate the previous facilitator conclusion.
        """
        print(f"\n{'='*60}")
        print(f"📊 NODE: COMPUTE DELTAS")
        print(f"{'='*60}")
        logger.info("Computing report deltas")
        
        symbol = state["symbol"]
        
        # Publish graph state
        self._publish_event(state, "graph_state", {
            "symbol": symbol,
            "current_node": "compute_deltas",
            "status": "RUNNING"
        })
        
        # Get cached reports
        print(f"  📂 Checking cached reports for {symbol}...")
        cached = self.cache_manager.get_all_cached_reports(symbol)
        cached_count = sum(1 for v in cached.values() if v is not None)
        print(f"  📂 Found {cached_count}/5 cached reports")
        
        # Create Report objects from state
        new_reports = {
            "news": Report("news", state["news_report"], datetime.utcnow().isoformat(), symbol),
            "sentiment": Report("sentiment", state["sentiment_report"], datetime.utcnow().isoformat(), symbol),
            "market": Report("market", state["market_report"], datetime.utcnow().isoformat(), symbol),
            "fundamental": Report("fundamental", state["fundamental_report"], datetime.utcnow().isoformat(), symbol)
        }
        
        # Compute deltas for each report type
        print(f"  🔄 Computing deltas between cached and new reports...")
        deltas = self.delta_computer.compute_all_deltas(cached, new_reports)
        state["report_deltas"] = deltas
        
        for report_type, delta in deltas.items():
            if isinstance(delta, dict):
                new_pts = len(delta.get("new_points", []))
                removed_pts = len(delta.get("removed_points", []))
                print(f"    📝 {report_type}: {new_pts} new points, {removed_pts} removed")
        
        # Validate previous facilitator conclusion
        print(f"\n  🔍 Validating previous facilitator conclusion...")
        if cached.get("facilitator"):
            validation = self.facilitator_validator.validate_conclusion(
                cached.get("facilitator"),
                cached.get("market"),
                new_reports["market"]
            )
            state["facilitator_conclusion"] = validation
            print(f"    📋 Previous recommendation: {validation.get('old_recommendation', 'N/A')}")
            print(f"    📈 Market moved: {validation.get('market_validation', 'N/A')}")
            print(f"    ✅ Was correct: {validation.get('was_correct', 'N/A')}")
            print(f"    💭 Reasoning: {validation.get('reasoning', 'N/A')[:100]}...")
            
            # Save facilitator validation to memory for learning
            memory = self._get_memory_manager(state["session_id"], state["symbol"])
            memory.save_facilitator_validation(
                recommendation=validation.get('old_recommendation', 'UNKNOWN'),
                was_correct=validation.get('was_correct', False),
                market_validation=validation.get('market_validation', ''),
                reasoning=validation.get('reasoning', '')
            )
            print(f"    💾 Saved prediction outcome to memory")
        else:
            state["facilitator_conclusion"] = {
                "was_correct": None,
                "reasoning": "No previous facilitator report",
                "old_recommendation": None,
                "market_validation": None,
                "confidence": 0
            }
            print(f"    ℹ️ No previous facilitator report to validate")
        
        # Extract new discussion points from all deltas
        new_points = []
        for report_type, delta in deltas.items():
            if isinstance(delta, dict):
                for point in delta.get("new_points", []):
                    new_points.append({
                        "source": report_type,
                        "content": point,
                        "type": "new"
                    })
                for change in delta.get("changed_points", []):
                    new_points.append({
                        "source": report_type,
                        "content": f"Changed: {change.get('old', '')} → {change.get('new', '')}",
                        "type": "changed"
                    })
        
        state["new_points"] = new_points
        state["updated_at"] = datetime.utcnow().isoformat()
        
        # Update cache with new reports
        print(f"\n  💾 Updating cache with new reports...")
        self.cache_manager.update_cache(symbol, new_reports)
        
        print(f"\n  📊 Total new discussion points: {len(new_points)}")
        logger.info(f"Computed {len(new_points)} new discussion points")
        print(f"✅ NODE COMPLETE: COMPUTE DELTAS")
        return state
    
    # ============================================================
    # NODE 3: FETCH MEMORY CONTEXT
    # ============================================================
    def fetch_memory_context(self, state: DebateState) -> DebateState:
        """
        Fetch relevant memory context for both parties based on new points.
        Uses dynamic queries incorporating the symbol and key data points.
        """
        print(f"\n{'='*60}")
        print(f"🧠 NODE: FETCH MEMORY CONTEXT")
        print(f"{'='*60}")
        logger.info("Fetching memory context")
        
        self._publish_event(state, "graph_state", {"symbol": state["symbol"], "current_node": "fetch_memory_context", "status": "RUNNING"})
        
        memory = self._get_memory_manager(state["session_id"], state["symbol"])
        symbol = state["symbol"]
        
        # Build query from new points
        points_text = " ".join([p.get("content", "") for p in state["new_points"][:5]])
        print(f"  📝 Building query from {len(state['new_points'])} new points")
        
        if points_text:
            # Build dynamic queries incorporating symbol context
            bull_query = f"{symbol} bullish opportunities growth potential upside momentum {points_text[:200]}"
            bear_query = f"{symbol} bearish risks concerns downside volatility warnings {points_text[:200]}"
            
            # Get context for both parties
            print(f"  🐂 Fetching bull memory context...")
            bull_context = memory.get_debate_context(
                query=bull_query,
                party="bull",
                limit=5
            )
            print(f"    Found {len(bull_context)} bull memories")
            
            print(f"  🐻 Fetching bear memory context...")
            bear_context = memory.get_debate_context(
                query=bear_query,
                party="bear",
                limit=5
            )
            
            state["bull_memory_context"] = bull_context
            state["bear_memory_context"] = bear_context
            print(f"    Found {len(bear_context)} bear memories")
            
            # Fetch facilitator prediction history
            print(f"  📊 Fetching facilitator prediction history...")
            facilitator_history = memory.get_facilitator_history(limit=3)
            state["facilitator_history"] = facilitator_history
            print(f"    Found {len(facilitator_history)} past predictions")
        else:
            print(f"  ℹ️ No new points to query memory")
        
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: FETCH MEMORY CONTEXT")
        return state
    
    # ============================================================
    # NODE 4a: GENERATE RAG QUERY FOR BULL
    # ============================================================
    def generate_bull_rag_query(self, state: DebateState) -> DebateState:
        """
        Generate a RAG query for the Bull party to find supporting/countering evidence.
        Also fetches relevant memory context based on opponent's point.
        """
        return self._generate_rag_query_for_party(state, "bull")
    
    # ============================================================
    # NODE 4b: GENERATE RAG QUERY FOR BEAR
    # ============================================================
    def generate_bear_rag_query(self, state: DebateState) -> DebateState:
        """
        Generate a RAG query for the Bear party to find supporting/countering evidence.
        Also fetches relevant memory context based on opponent's point.
        """
        return self._generate_rag_query_for_party(state, "bear")
    
    # ============================================================
    # NODE 4c: FETCH RAG EVIDENCE
    # ============================================================
    def fetch_rag_evidence(self, state: DebateState) -> DebateState:
        """
        Fetch evidence from knowledge base using the generated query.
        """
        print(f"\n{'='*60}")
        print(f"📚 NODE: FETCH RAG EVIDENCE")
        print(f"{'='*60}")
        
        self._publish_event(state, "graph_state", {"symbol": state["symbol"], "current_node": "fetch_rag_evidence", "status": "RUNNING"})
        
        query = state.get("pending_rag_query")
        if not query:
            print(f"  ℹ️ No RAG query to execute")
            state["rag_evidence"] = []
            state["rag_response"] = "No evidence fetched"
            return state
        
        print(f"  🔍 Querying knowledge base: {query[:60]}...")
        
        # Query the RAG server with retry logic
        max_retries = 2
        result = {"results": []}
        
        for attempt in range(max_retries + 1):
            try:
                result = self.rag_client.query(
                    query=query,
                    symbol=state["symbol"],
                    limit=5
                )
                if result.get("results") or attempt == max_retries:
                    break
            except Exception as e:
                logger.warning(f"RAG query attempt {attempt + 1} failed: {e}")
                if attempt == max_retries:
                    print(f"  ⚠️ RAG query failed after {max_retries + 1} attempts")
                    state["errors"].append(f"RAG query failed: {str(e)}")
        
        results = result.get("results", [])
        print(f"  📄 Found {len(results)} relevant documents")
        
        # Extract evidence
        evidence_texts = []
        for i, doc in enumerate(results[:5], 1):
            content = doc.get("content", doc.get("text", ""))
            if content:
                evidence_texts.append(content)
                print(f"    {i}. {content[:80]}...")
        
        state["rag_evidence"] = evidence_texts
        state["rag_response"] = "\n\n".join([
            f"Evidence {i}: {ev}" for i, ev in enumerate(evidence_texts, 1)
        ]) if evidence_texts else "No relevant evidence found"
        
        # Clear the pending query
        state["pending_rag_query"] = None
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: FETCH RAG EVIDENCE")
        return state
    
    # ============================================================
    # NODE 5: BULL PRESENTS POINT
    # ============================================================
    def bull_present_point(self, state: DebateState) -> DebateState:
        """
        Bull party presents a point (either new or counter to bear).
        """
        return self._present_point_for_party(state, "bull")
    
    # ============================================================
    # NODE 5: BEAR PRESENTS POINT
    # ============================================================
    def bear_present_point(self, state: DebateState) -> DebateState:
        """
        Bear party presents a point (either new or counter to bull).
        """
        return self._present_point_for_party(state, "bear")
    
    # ============================================================
    # NODE 6: CHECK UNIQUENESS
    # ============================================================
    def check_uniqueness(self, state: DebateState) -> DebateState:
        """
        Check if the current point is unique (not repeated).
        """
        current_point = state.get("current_point")
        if not current_point:
            return state
        
        print(f"\n{'='*60}")
        print(f"🔄 NODE: CHECK UNIQUENESS")
        print(f"{'='*60}")
        logger.info("Checking point uniqueness")
        
        # Publish graph state
        self._publish_event(state, "graph_state", {
            "symbol": state["symbol"],
            "current_node": "check_uniqueness",
            "status": "RUNNING"
        })
        
        memory = self._get_memory_manager(state["session_id"], state["symbol"])
        party = current_point.get("party", "bull")
        point_content = current_point.get("content", "")
        
        print(f"  Checking if {party.upper()}'s point is unique...")
        
        # Check against memory
        is_repeated = memory.is_point_repeated(
            point=point_content,
            party=party,
            threshold=self.config.debate.point_similarity_threshold
        )
        
        if is_repeated:
            current_point["is_unique"] = False
            state["current_point"] = current_point
            state["unique_point_retries"] = state.get("unique_point_retries", 0) + 1
            print(f"  ⚠️ Point is NOT unique! Retry {state['unique_point_retries']}")
            logger.info(f"Point is not unique. Retry {state['unique_point_retries']}")
        else:
            current_point["is_unique"] = True
            state["current_point"] = current_point
            state["unique_point_retries"] = 0
            print(f"  ✅ Point is unique")
        
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: CHECK UNIQUENESS")
        return state
    
    # ============================================================
    # NODE 8: REPHRASE POINT
    # ============================================================
    def rephrase_point(self, state: DebateState) -> DebateState:
        """
        Rephrase a point that was flagged as not unique.
        """
        current_point = state.get("current_point")
        if not current_point or current_point.get("is_unique", True):
            return state
        
        print(f"\n{'='*60}")
        print(f"✏️ NODE: REPHRASE POINT")
        print(f"{'='*60}")
        logger.info("Rephrasing point for uniqueness")
        
        self._publish_event(state, "graph_state", {"symbol": state["symbol"], "current_node": "rephrase_point", "status": "RUNNING"})
        
        party = current_point.get("party", "bull")
        print(f"  Rephrasing {party.upper()}'s point for uniqueness...")
        
        # Get available new information
        available_info = "\n".join([
            p.get("content", "") for p in state.get("new_points", [])[:10]
        ])
        
        prompt = REPHRASE_POINT_PROMPT.format(
            similar_point="Previous point with similar content",
            rejected_point=current_point.get("content", ""),
            available_info=available_info,
            party=party.upper()
        )
        
        messages = [
            {"role": "system", "content": f"You are a {party} investment analyst. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.llm.complete_json(messages)
        
        # Update current point
        old_point = current_point.get("content", "")[:50]
        current_point["content"] = response.get("point", current_point.get("content", ""))
        current_point["supporting_evidence"] = response.get("supporting_evidence", [])
        current_point["confidence"] = response.get("confidence", 0.6)
        # Note: Don't set is_unique=True here - let check_uniqueness verify it
        # The graph routes back to check_uniqueness after rephrase
        
        print(f"  Old: {old_point}...")
        print(f"  New: {current_point['content'][:50]}...")
        
        state["current_point"] = current_point
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: REPHRASE POINT")
        return state
    
    # ============================================================
    # NODE 9: COMMIT POINT
    # ============================================================
    def commit_point(self, state: DebateState) -> DebateState:
        """
        Commit the current point to the debate history, memory, and persistent storage.
        Points are saved to a JSON file in the symbol folder (shared across all sessions).
        """
        current_point = state.get("current_point")
        if not current_point:
            return state
        
        print(f"\n{'='*60}")
        print(f"💾 NODE: COMMIT POINT")
        print(f"{'='*60}")
        party = current_point.get('party', 'unknown')
        print(f"  Committing {party.upper()}'s point to history, memory, and disk")
        logger.info(f"Committing {party} point")
        
        # Publish graph state
        self._publish_event(state, "graph_state", {
            "symbol": state["symbol"],
            "current_node": "commit_point",
            "current_speaker": party,
            "status": "RUNNING"
        })
        
        # Add to debate points (in-memory state)
        debate_points = state.get("debate_points", [])
        debate_points.append(current_point)
        state["debate_points"] = debate_points
        print(f"  📝 Total debate points (session): {len(debate_points)}")
        
        # Save to memory (mem0)
        memory = self._get_memory_manager(state["session_id"], state["symbol"])
        memory.save_debate_point(
            point=current_point.get("content", ""),
            party=current_point.get("party", "bull"),
            counter_to=current_point.get("counter_to"),
            evidence=current_point.get("supporting_evidence", [])
        )
        print(f"  💾 Saved to memory")
        
        # Persist to JSON file in symbol folder (survives across sessions)
        try:
            debate_point = convert_dict_to_debate_point(current_point)
            self.debate_points_manager.save_point_to_symbol_folder(
                symbol=state["symbol"],
                session_id=state["session_id"],
                point=debate_point
            )
        except Exception as e:
            logger.error(f"Failed to persist point to disk: {e}")
            print(f"  ⚠️ Warning: Failed to persist to disk: {e}")
        
        # Increment round number
        if current_point.get("party") == "bear":
            state["round_number"] = state.get("round_number", 0) + 1
            print(f"  🔄 Round {state['round_number']} complete")
        
        # Clear current point
        state["current_point"] = None
        state["updated_at"] = datetime.utcnow().isoformat()
        
        print(f"✅ NODE COMPLETE: COMMIT POINT")
        return state
    
    # ============================================================
    # NODE 10: GENERATE FACILITATOR REPORT
    # ============================================================
    def generate_facilitator_report(self, state: DebateState) -> DebateState:
        """
        Generate the final facilitator report.
        """
        print(f"\n{'='*60}")
        print(f"📋 NODE: GENERATE FACILITATOR REPORT")
        print(f"{'='*60}")
        logger.info("Generating facilitator report")
        
        # Publish graph state - facilitator is generating report
        self._publish_event(state, "graph_state", {
            "symbol": state["symbol"],
            "current_node": "generate_report",
            "status": "RUNNING"
        })
        
        # Determine conclusion reason based on state
        current_round = state.get("round_number", 0)
        max_rounds = state.get("max_rounds", 5)
        debate_points = state.get("debate_points", [])
        
        if current_round >= max_rounds:
            conclusion_reason = f"Maximum rounds ({max_rounds}) reached"
        elif len(debate_points) >= 2:
            last_two = debate_points[-2:]
            low_confidence = all(p.get("confidence", 1.0) < 0.3 for p in last_two)
            if low_confidence:
                conclusion_reason = "Low confidence in recent arguments"
            else:
                conclusion_reason = "No new points to discuss"
        else:
            conclusion_reason = "Debate concluded"
        
        state["conclusion_reason"] = conclusion_reason
        print(f"  📝 Conclusion reason: {conclusion_reason}")
        
        print(f"  📊 Summarizing {len(debate_points)} debate points...")
        
        # Build debate points summary
        debate_points_text = "\n\n".join([
            f"**[{p.get('party', 'unknown').upper()}]** (Confidence: {p.get('confidence', 0.5):.0%})\n{p.get('content', '')}\nEvidence: {', '.join(p.get('supporting_evidence', []))}"
            for p in state.get("debate_points", [])
        ])
        
        # Build deltas summary
        deltas = state.get("report_deltas", {})
        
        def format_delta(d):
            if not isinstance(d, dict):
                return "N/A"
            new_pts = d.get("new_points", [])
            # Handle both string and dict formats for points
            formatted_pts = []
            for p in new_pts[:3]:
                if isinstance(p, dict):
                    formatted_pts.append(p.get("content", p.get("text", str(p))))
                else:
                    formatted_pts.append(str(p))
            return f"{len(new_pts)} new points: " + "; ".join(formatted_pts)
        
        # Correctness info
        conclusion = state.get("facilitator_conclusion", {})
        was_correct = conclusion.get("was_correct")
        was_correct_str = "Yes" if was_correct else "No" if was_correct is False else "N/A"
        
        print(f"  🤖 Calling LLM to generate report...")
        
        prompt = FACILITATOR_CONCLUSION_PROMPT.format(
            symbol=state["symbol"],
            old_report=state.get("facilitator_report", "No previous report"),
            debate_points=debate_points_text,
            news_delta=format_delta(deltas.get("news")),
            sentiment_delta=format_delta(deltas.get("sentiment")),
            market_delta=format_delta(deltas.get("market")),
            fundamental_delta=format_delta(deltas.get("fundamental")),
            was_correct=was_correct_str,
            correctness_reasoning=conclusion.get("reasoning", "N/A"),
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        messages = [
            {"role": "system", "content": "You are a senior investment facilitator. Generate a comprehensive, balanced report in markdown format."},
            {"role": "user", "content": prompt}
        ]
        
        report = self.llm.complete(messages, temperature=0.3)
        
        state["final_facilitator_report"] = report
        print(f"  ✅ Generated report: {len(report)} chars")
        
        # Extract recommendation using word boundary matching
        report_upper = report.upper()
        
        # Look for explicit "RECOMMENDATION: X" pattern first
        rec_match = re.search(r'RECOMMENDATION[:\s]+\**(STRONG\s+BUY|STRONG\s+SELL|BUY|SELL|HOLD)\**', report_upper)
        if rec_match:
            state["recommendation"] = rec_match.group(1).replace("\n", " ").strip()
        elif re.search(r'\bSTRONG\s+BUY\b', report_upper):
            state["recommendation"] = "STRONG BUY"
        elif re.search(r'\bSTRONG\s+SELL\b', report_upper):
            state["recommendation"] = "STRONG SELL"
        elif re.search(r'\bBUY\b', report_upper) and not re.search(r'\bSELL\b', report_upper):
            state["recommendation"] = "BUY"
        elif re.search(r'\bSELL\b', report_upper):
            state["recommendation"] = "SELL"
        else:
            state["recommendation"] = "HOLD"
        
        print(f"  🎯 Recommendation: {state['recommendation']}")
        
        # Publish recommendation event
        self._publish_event(state, "recommendation", {
            "symbol": state["symbol"],
            "recommendation": state["recommendation"],
            "conclusion_reason": conclusion_reason,
            "total_rounds": current_round,
            "bull_points": len([p for p in debate_points if p.get("party") == "bull"]),
            "bear_points": len([p for p in debate_points if p.get("party") == "bear"]),
            "report_length": len(report)
        })
        
        # Publish debate progress - COMPLETED
        self._publish_event(state, "debate_progress", {
            "symbol": state["symbol"],
            "status": "COMPLETED",
            "current_round": current_round,
            "max_rounds": max_rounds,
            "conclusion_reason": conclusion_reason,
            "recommendation": state["recommendation"]
        })
        
        state["updated_at"] = datetime.utcnow().isoformat()
        print(f"✅ NODE COMPLETE: GENERATE FACILITATOR REPORT")
        return state
    
    # ============================================================
    # NODE 11: SAVE AND CLEANUP
    # ============================================================
    def save_and_cleanup(self, state: DebateState) -> DebateState:
        """
        Save debate points to files and cleanup old data.
        """
        print(f"\n{'='*60}")
        print(f"💾 NODE: SAVE AND CLEANUP")
        print(f"{'='*60}")
        logger.info("Saving debate points and cleaning up")
        
        self._publish_event(state, "graph_state", {"symbol": state["symbol"], "current_node": "save_cleanup", "status": "RUNNING"})
        
        symbol = state["symbol"]
        session_id = state["session_id"]
        
        # Convert points to DebatePoint objects and save
        points = [
            convert_dict_to_debate_point(p)
            for p in state.get("debate_points", [])
        ]
        
        print(f"  📝 Saving {len(points)} debate points...")
        
        if points:
            # Cleanup old points first
            self.debate_points_manager.cleanup_old_points(symbol, session_id)
            
            # Save new points
            saved = self.debate_points_manager.save_all_points(symbol, session_id, points)
            print(f"  ✅ Saved {len(saved)} point files")
            
            # Determine last speaker for next session
            last_speaker = ""
            if points:
                last_speaker = points[-1].party.value if hasattr(points[-1].party, 'value') else str(points[-1].party)
            
            # Save session summary with last speaker
            summary = {
                "symbol": symbol,
                "session_id": session_id,
                "started_at": state["started_at"],
                "completed_at": datetime.utcnow().isoformat(),
                "total_rounds": state["round_number"],
                "total_points": len(points),
                "recommendation": state["recommendation"],
                "conclusion_reason": state.get("conclusion_reason", "Max rounds reached"),
                "last_speaker": last_speaker  # For next session's first speaker
            }
            self.debate_points_manager.save_session_summary(symbol, session_id, summary)
            print(f"  ✅ Saved session summary (last speaker: {last_speaker})")
        
        # Cleanup old sessions (keep last 5)
        removed = self.debate_points_manager.cleanup_old_sessions(symbol, keep_sessions=5)
        if removed > 0:
            print(f"  🧹 Cleaned up {removed} old sessions")
        
        # Update facilitator report in cache
        if state.get("final_facilitator_report"):
            # Determine last speaker for next session
            debate_points = state.get("debate_points", [])
            last_speaker = ""
            if debate_points:
                last_point = debate_points[-1]
                last_speaker = last_point.get("party", "")
            
            facilitator_report = Report(
                report_type="facilitator",
                content=state["final_facilitator_report"],
                timestamp=datetime.utcnow().isoformat(),
                symbol=symbol,
                metadata={
                    "recommendation": state["recommendation"],
                    "last_speaker": last_speaker  # For next session's first speaker
                }
            )
            self.cache_manager.save_to_cache(symbol, facilitator_report)
            print(f"  💾 Cached facilitator report (last speaker: {last_speaker})")
        
        state["debate_concluded"] = True
        state["updated_at"] = datetime.utcnow().isoformat()
        
        self._publish_event(state, "graph_state", {"symbol": state["symbol"], "current_node": "end", "status": "COMPLETED"})
        
        print(f"✅ NODE COMPLETE: SAVE AND CLEANUP")
        return state
