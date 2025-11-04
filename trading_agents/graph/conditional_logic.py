from all_agents.utils.agent_state import AgentState

class ConditionalLogic:
    """Defines conditional logic for the agent graph."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # rounds of back-and-forth between 2 agents
            return "trader"
        
        # Check which agent responded last
        last_speaker = state["investment_debate_state"].get("last_speaker", "")
        
        # Alternate between bull and bear researchers
        if last_speaker == "bull_researcher":
            return "bear_researcher"
        elif last_speaker == "bear_researcher":
            return "bull_researcher"
        else:
            # Default: if no last speaker (first round), go to bear
            return "bear_researcher"