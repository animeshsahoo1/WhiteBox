from typing import Dict, Any
from langgraph.graph import END, StateGraph, START

from all_agents.researchers.bull_researcher import create_bull_researcher
from all_agents.researchers.bear_researcher import create_bear_researcher
from all_agents.trader import create_trader
from all_agents.risk_mngt import create_risky_debator, create_safe_debator, create_neutral_debator
from all_agents.managers.risk_manager import create_risk_manager
from all_agents.managers.final_manager import create_final_manager


from all_agents.utils.agent_state import AgentState

from conditional_logic import ConditionalLogic

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

        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Risky Analyst", risky_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Safe Analyst", safe_analyst)
        workflow.add_node("Risk Judge", risk_manager_node)
        workflow.add_node("Final Manager", final_manager_node)

        workflow.add_edge(START, "Bull Researcher")
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Trader": "Trader",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Trader": "Trader",
            },
        )
        workflow.add_edge("Trader", "Risky Analyst")
        workflow.add_edge("Trader", "Safe Analyst")
        workflow.add_edge("Trader", "Neutral Analyst")
        workflow.add_edge("Risky Analyst", "Risk Judge")
        workflow.add_edge("Safe Analyst", "Risk Judge")
        workflow.add_edge("Neutral Analyst", "Risk Judge")

        workflow.add_edge("Risk Judge", "Final Manager")
        workflow.add_edge("Final Manager", END)

        # Compile and return
        return workflow.compile(checkpointer=self.checkpointer)
        
