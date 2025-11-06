# python graph/trading_graph.py

import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timezone

from langgraph.checkpoint.mongodb import MongoDBSaver

from graph.propagation import Propagator
from graph.setup import GraphSetup
from all_agents.utils.llm import chat_model
from graph.conditional_logic import ConditionalLogic
from utils.reports_client import PathwayReportsClient

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


def fetch_reports_from_pathway(symbol: str, use_fallback: bool = False) -> dict:
    """
    Fetch reports from Pathway API.
    
    Args:
        symbol: Stock ticker symbol
        use_fallback: If True, use sample data as fallback when reports are not available
    
    Returns:
        Dictionary with report keys
    """
    # Initialize the client
    pathway_api_url = os.getenv('PATHWAY_API_URL', 'http://pathway-service:8000')
    client = PathwayReportsClient(base_url=pathway_api_url)
    
    print(f"\n📡 Connecting to Pathway API at {pathway_api_url}...")
    
    # Check if API is healthy
    if not client.health_check():
        error_msg = f"❌ Pathway API is not available at {pathway_api_url}"
        if use_fallback:
            print(f"{error_msg}\n⚠️  Using fallback sample data...")
            from all_agents.utils.sample import (
                market_report_example,
                sentiment_report_example,
                news_report_example,
                fundamentals_report_example
            )
            return {
                "market_report": market_report_example,
                "sentiment_report": sentiment_report_example,
                "news_report": news_report_example,
                "fundamentals_report": fundamentals_report_example
            }
        else:
            raise ConnectionError(error_msg)
    
    print("✅ Pathway API is healthy")
    
    # Fetch reports
    print(f"\n🔍 Fetching reports for {symbol}...")
    
    try:
        reports = client.get_all_reports(symbol)
        
        # Check completeness
        if not reports.is_complete():
            missing = reports.missing_reports()
            warning_msg = f"⚠️  Missing reports for {symbol}: {', '.join(missing)}"
            
            if use_fallback:
                print(f"{warning_msg}\n⚠️  Using fallback sample data for missing reports...")
                from all_agents.utils.sample import (
                    market_report_example,
                    sentiment_report_example,
                    news_report_example,
                    fundamentals_report_example
                )
                return {
                    "market_report": reports.market_report or market_report_example,
                    "sentiment_report": reports.sentiment_report or sentiment_report_example,
                    "news_report": reports.news_report or news_report_example,
                    "fundamentals_report": reports.fundamental_report or fundamentals_report_example
                }
            else:
                raise ValueError(warning_msg)
        
        print(f"✅ All reports fetched successfully for {symbol}")
        
        return {
            "market_report": reports.market_report,
            "sentiment_report": reports.sentiment_report,
            "news_report": reports.news_report,
            "fundamentals_report": reports.fundamental_report
        }
        
    except Exception as e:
        error_msg = f"❌ Failed to fetch reports for {symbol}: {e}"
        if use_fallback:
            print(f"{error_msg}\n⚠️  Using fallback sample data...")
            from all_agents.utils.sample import (
                market_report_example,
                sentiment_report_example,
                news_report_example,
                fundamentals_report_example
            )
            return {
                "market_report": market_report_example,
                "sentiment_report": sentiment_report_example,
                "news_report": news_report_example,
                "fundamentals_report": fundamentals_report_example
            }
        else:
            raise


def run(company_name: str, trade_date: str, use_fallback: bool = False):
    """
    Run the trading graph for a given company and date.
    
    Args:
        company_name: Stock ticker symbol (e.g., AAPL, GOOGL)
        trade_date: Trading date string
        use_fallback: If True, use sample data as fallback when reports unavailable
    """
    
    # Fetch reports from Pathway API
    try:
        reports = fetch_reports_from_pathway(company_name, use_fallback=use_fallback)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("💡 Tip: Make sure the Pathway service is running and has processed data for this symbol")
        print("💡 Or run with use_fallback=True to use sample data")
        sys.exit(1)
    
    # --- MONGODB CHECKPOINTER ---
    DB_URI = os.getenv("MONGODB_URI")
    config = {"configurable": {"thread_id": f"{company_name}_{trade_date}"}}
    
    with MongoDBSaver.from_conn_string(DB_URI) as mongo_checkpointer:
        graph = create_trading_graph(mongo_checkpointer)
        
        # --- initial state ---
        prop = Propagator()
        state = prop.create_initial_state(company_name, trade_date)
        
        # Inject reports from Pathway API
        state["market_report"] = reports["market_report"]
        state["sentiment_report"] = reports["sentiment_report"]
        state["news_report"] = reports["news_report"]
        state["fundamentals_report"] = reports["fundamentals_report"]
        
        print("\n🚀 Starting trading graph execution...")
        
        # --- run graph ---
        final_state = graph.invoke(state, config)
        
        print("\n\n================ FINAL REPORT ================\n")
        print(final_state.get("final_report", ""))
        
        print("\n\n================ FINAL TRADE SIGNAL ================\n")
        print(final_state.get("trade_signal", {}))
        
        return final_state


if __name__ == "__main__":
    # Get symbol from command line or environment variable
    symbol = os.getenv("STOCK_SYMBOL")
    
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
    
    if not symbol:
        print("❌ Error: No stock symbol provided")
        print("Usage: python run.py <SYMBOL>")
        print("   Or: Set STOCK_SYMBOL environment variable")
        print("Example: python run.py AAPL")
        sys.exit(1)
    
    # Check if fallback mode is enabled
    use_fallback = os.getenv("USE_FALLBACK_DATA", "false").lower() == "true"
    
    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    
    print("=" * 70)
    print(f"🤖 Trading Agent for {symbol}")
    print(f"📅 Trade Date: {trade_date}")
    print(f"🔄 Fallback Mode: {'Enabled' if use_fallback else 'Disabled'}")
    print("=" * 70)
    
    run(symbol, trade_date, use_fallback=use_fallback)