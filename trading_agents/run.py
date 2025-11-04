# python graph/trading_graph.py

import os
from dotenv import load_dotenv
from datetime import datetime, timezone

from langgraph.checkpoint.mongodb import MongoDBSaver

from graph.propagation import Propagator
from graph.setup import GraphSetup
from all_agents.utils.sample import (
    market_report_example,
    sentiment_report_example,
    news_report_example,
    fundamentals_report_example
)
from all_agents.utils.llm import chat_model
from graph.conditional_logic import ConditionalLogic

load_dotenv()


def create_trading_graph(checkpointer):
    """Create and return the compiled trading graph with checkpointer."""
    conditional_logic = ConditionalLogic()
    
    setup = GraphSetup(
        conditional_logic=conditional_logic,
        checkpointer=checkpointer
    )
    
    setup.quick_thinking_llm = chat_model
    setup.deep_thinking_llm = chat_model
    
    return setup.setup_graph()


def run(company_name: str, trade_date: str):
    """Run the trading graph for a given company and date."""
    
    # --- MONGODB CHECKPOINTER ---
    DB_URI = os.getenv("MONGODB_URI")
    config = {"configurable": {"thread_id": f"{company_name}_{trade_date}"}}
    
    with MongoDBSaver.from_conn_string(DB_URI) as mongo_checkpointer:
        graph = create_trading_graph(mongo_checkpointer)
        
        # --- initial state ---
        prop = Propagator()
        state = prop.create_initial_state(company_name, trade_date)
        
        # sample data inject (you can remove this later)
        state["market_report"] = market_report_example
        state["sentiment_report"] = sentiment_report_example
        state["news_report"] = news_report_example
        state["fundamentals_report"] = fundamentals_report_example
        
        # --- run graph ---
        final_state = graph.invoke(state, config)
        
        print("\n\n================ FINAL REPORT ================\n")
        print(final_state.get("final_report", ""))
        
        print("\n\n================ FINAL TRADE SIGNAL ================\n")
        print(final_state.get("trade_signal", {}))
        
        return final_state


if __name__ == "__main__":
    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    run("AAPL", trade_date)