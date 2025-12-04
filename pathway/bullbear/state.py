"""
State definitions for the Bull-Bear Debate LangGraph
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DebateParty(str, Enum):
    """Debate participant types"""
    BULL = "bull"
    BEAR = "bear"
    FACILITATOR = "facilitator"


@dataclass
class DebatePoint:
    """Represents a single debate point"""
    id: str
    party: DebateParty
    content: str
    supporting_evidence: List[str] = field(default_factory=list)
    counter_to: Optional[str] = None  # ID of point being countered
    confidence: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_unique: bool = True
    rag_sources: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "party": self.party.value,
            "content": self.content,
            "supporting_evidence": self.supporting_evidence,
            "counter_to": self.counter_to,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "is_unique": self.is_unique,
            "rag_sources": self.rag_sources
        }


@dataclass 
class ReportDelta:
    """Changes detected between old and new reports"""
    report_type: str  # news, sentiment, market, fundamental
    new_points: List[str] = field(default_factory=list)
    removed_points: List[str] = field(default_factory=list)
    changed_points: List[Dict[str, str]] = field(default_factory=list)  # {old: ..., new: ...}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_type": self.report_type,
            "new_points": self.new_points,
            "removed_points": self.removed_points,
            "changed_points": self.changed_points
        }


@dataclass
class FacilitatorConclusion:
    """Previous facilitator's conclusion validation"""
    was_correct: bool
    reasoning: str
    old_recommendation: str  # BUY/HOLD/SELL
    market_validation: str  # What actually happened
    confidence: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "was_correct": self.was_correct,
            "reasoning": self.reasoning,
            "old_recommendation": self.old_recommendation,
            "market_validation": self.market_validation,
            "confidence": self.confidence
        }


class ReportDeltas(TypedDict):
    """All report deltas"""
    news: Optional[Dict[str, Any]]
    sentiment: Optional[Dict[str, Any]]
    market: Optional[Dict[str, Any]]
    fundamental: Optional[Dict[str, Any]]


class DebateState(TypedDict):
    """Main state for the Bull-Bear debate graph"""
    # Identifiers
    symbol: Annotated[str, "Stock symbol being debated"]
    session_id: Annotated[str, "Unique session identifier"]
    
    # Reports (raw)
    news_report: Annotated[str, "Current news report"]
    sentiment_report: Annotated[str, "Current sentiment report"]
    market_report: Annotated[str, "Current market report"]
    fundamental_report: Annotated[str, "Current fundamental report"]
    facilitator_report: Annotated[str, "Previous facilitator report"]
    
    # Report Deltas
    report_deltas: Annotated[Dict[str, Any], "Changes from cached reports"]
    facilitator_conclusion: Annotated[Optional[Dict[str, Any]], "Validation of previous conclusion"]
    
    # Debate Points
    new_points: Annotated[List[Dict[str, Any]], "New discussion points from report deltas"]
    debate_points: Annotated[List[Dict[str, Any]], "All points presented in debate"]
    current_point: Annotated[Optional[Dict[str, Any]], "Current point being discussed"]
    
    # Memory Context
    bull_memory_context: Annotated[List[str], "Relevant memories for bull"]
    bear_memory_context: Annotated[List[str], "Relevant memories for bear"]
    facilitator_history: Annotated[List[str], "History of facilitator predictions and outcomes"]
    
    # Debate Control
    current_speaker: Annotated[str, "Current party presenting: bull/bear"]
    round_number: Annotated[int, "Current debate round"]
    max_rounds: Annotated[int, "Maximum allowed rounds"]
    unique_point_retries: Annotated[int, "Retries for unique point"]
    previous_session_last_speaker: Annotated[str, "Last speaker from previous session"]
    
    # RAG Context
    pending_rag_query: Annotated[Optional[str], "Pending query for RAG server"]
    rag_query: Annotated[Optional[str], "Query for RAG server"]
    rag_evidence: Annotated[List[str], "Evidence retrieved from RAG"]
    rag_response: Annotated[Optional[str], "Formatted response from RAG server"]
    
    # Outcomes
    debate_concluded: Annotated[bool, "Whether debate has concluded"]
    conclusion_reason: Annotated[str, "Reason for conclusion"]
    final_facilitator_report: Annotated[str, "Final generated report"]
    recommendation: Annotated[str, "Final BUY/HOLD/SELL recommendation"]
    
    # Metadata
    started_at: Annotated[str, "Debate start timestamp"]
    updated_at: Annotated[str, "Last update timestamp"]
    errors: Annotated[List[str], "Any errors encountered"]


def create_initial_state(symbol: str, session_id: str, max_rounds: int = 5) -> DebateState:
    """Create initial debate state"""
    now = datetime.utcnow().isoformat()
    return DebateState(
        symbol=symbol,
        session_id=session_id,
        news_report="",
        sentiment_report="",
        market_report="",
        fundamental_report="",
        facilitator_report="",
        report_deltas={},
        facilitator_conclusion=None,
        new_points=[],
        debate_points=[],
        current_point=None,
        bull_memory_context=[],
        bear_memory_context=[],
        facilitator_history=[],
        current_speaker="bull",
        round_number=0,
        max_rounds=max_rounds,
        unique_point_retries=0,
        previous_session_last_speaker="",  # Will be loaded from cache if available
        pending_rag_query=None,
        rag_query=None,
        rag_evidence=[],
        rag_response=None,
        debate_concluded=False,
        conclusion_reason="",
        final_facilitator_report="",
        recommendation="HOLD",
        started_at=now,
        updated_at=now,
        errors=[]
    )
