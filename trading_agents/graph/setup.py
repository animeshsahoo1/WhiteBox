from typing import Dict, Any
from langgraph.graph import END, StateGraph, START

from all_agents.researchers.bull_researcher import create_bull_researcher
from all_agents.researchers.bear_researcher import create_bear_researcher
from all_agents.trader.trader import create_trader
from all_agents.risk_mngt.aggresive_debator import create_risky_debator
from all_agents.risk_mngt.conservative_debator import create_safe_debator
from all_agents.risk_mngt.neutral_debator import create_neutral_debator

from all_agents.managers.risk_manager import create_risk_manager
from all_agents.managers.final_manager import create_final_manager


from all_agents.utils.agent_state import AgentState

from graph.conditional_logic import ConditionalLogic

class GraphSetup:
    """Handles the setup and configuration of the agent graph."""
    def __init__(self,
        conditional_logic: ConditionalLogic,
        checkpointer,
    ):
        self.conditional_logic = conditional_logic
        self.checkpointer = checkpointer

    def setup_graph(self):
        """Set up and compile the agent workflow graph.
        """

        bull_researcher_node = create_bull_researcher(
            self.quick_thinking_llm
        )
        bear_researcher_node = create_bear_researcher(
            self.quick_thinking_llm
        )

        trader_node = create_trader(self.quick_thinking_llm)
        risky_analyst = create_risky_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        safe_analyst = create_safe_debator(self.quick_thinking_llm)
        risk_manager_node = create_risk_manager(
            self.deep_thinking_llm
        )
        final_manager_node = create_final_manager(
            self.deep_thinking_llm
        )
      
        workflow=StateGraph(AgentState)

        workflow.add_node("bull_researcher", bull_researcher_node)
        workflow.add_node("bear_researcher", bear_researcher_node)
        workflow.add_node("trader", trader_node)
        workflow.add_node("risky_analyst", risky_analyst)
        workflow.add_node("neutral_analyst", neutral_analyst)
        workflow.add_node("safe_analyst", safe_analyst)
        workflow.add_node("risk_judge", risk_manager_node)
        workflow.add_node("final_manager", final_manager_node)

        workflow.add_edge(START, "bull_researcher")
        workflow.add_conditional_edges(
            "bull_researcher",
            self.conditional_logic.should_continue_debate,
            {
                "bear_researcher": "bear_researcher",
                "trader": "trader",
            },
        )
        workflow.add_conditional_edges(
            "bear_researcher",
            self.conditional_logic.should_continue_debate,
            {
                "bull_researcher": "bull_researcher",
                "trader": "trader",
            },
        )
        
        # Sequential connection instead of parallel
        workflow.add_edge("trader", "risky_analyst")
        workflow.add_edge("risky_analyst", "neutral_analyst")
        workflow.add_edge("neutral_analyst", "safe_analyst")
        workflow.add_edge("safe_analyst", "risk_judge")

        workflow.add_edge("risk_judge", "final_manager")
        workflow.add_edge("final_manager", END)

        # Compile and return
        return workflow.compile(checkpointer=self.checkpointer)
    
    def setup_graph_with_checkpointer(self, checkpointer):
        workflow = self.setup_graph()
        return workflow.compile(checkpointer=checkpointer)