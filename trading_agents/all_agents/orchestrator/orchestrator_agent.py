import os
import requests
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ==================== State Definition ====================
def model_state(q, symbol="AAPL"):
    return {
        "query": q,
        "symbol": symbol,
        "reports_context": None,
        "fundamental_context": None,
        "market_context": None,
        "web_context": None,
        "response": None,
    }

# ==================== LLM Setup ====================
llm = ChatOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    model="openai/gpt-4o-mini",
)

# ==================== Pydantic Models for Structured Outputs ====================
class ContextNeeded(BaseModel):
    fundamental_needed: Literal["yes", "no"] = Field(description="Whether fundamental data (10K, financial statements) context is needed")
    market_needed: Literal["yes", "no"] = Field(description="Whether market data (price, candles, technical analysis) context is needed")

class WebSearchNeeded(BaseModel):
    web_search_needed: Literal["yes", "no"] = Field(description="Whether web search is needed for current events or additional context")

# ==================== API Helper Functions ====================
def fetch_reports(symbol: str):
    """Fetch all reports from port 8000 (Pathway Reports API)."""
    try:
        url = f"http://localhost:8000/reports/{symbol}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        reports_text = f"Symbol: {symbol}\n\n"
        has_any_report = False
        if data.get("fundamental_report"):
            reports_text += f"=== Fundamental Report ===\n{data['fundamental_report']}\n\n"
            has_any_report = True
        if data.get("market_report"):
            reports_text += f"=== Market Report ===\n{data['market_report']}\n\n"
            has_any_report = True
        if data.get("news_report"):
            reports_text += f"=== News Report ===\n{data['news_report']}\n\n"
            has_any_report = True
        if data.get("sentiment_report"):
            reports_text += f"=== Sentiment Report ===\n{data['sentiment_report']}\n\n"
            has_any_report = True
        
        return reports_text if has_any_report else None
    except Exception as e:
        print(f"❌ Error fetching reports: {e}")
        return None

def fetch_fundamental_data(question: str):
    """Fetch fundamental data QnA from RAG API on port 7001."""
    try:
        url = "http://localhost:8000/query"
        payload = {"question": question}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        answer = data.get("answer", "")
        return answer if answer and len(answer) > 10 else None
    except Exception as e:
        print(f"❌ Error fetching fundamental data: {e}")
        return None

def fetch_market_data(symbol: str, from_date: str, to_date: str, candle_length: str):
    """Placeholder for market data API on port 9001 (dummy for now)."""
    return f"Market data for {symbol} from {from_date} to {to_date} with {candle_length} candles (placeholder - API not yet implemented)"

def web_search(query: str):
    """Search the web using Serpex API."""
    serpex_api_key = os.getenv("SERPEX_API_KEY")
    
    if not serpex_api_key:
        return "Web search unavailable - SERPEX_API_KEY not set"
    
    try:
        url = "https://api.serpex.dev/api/search"
        headers = {"Authorization": f"Bearer {serpex_api_key}"}
        params = {"q": query, "engine": "auto", "category": "web", "time_range": "week"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        results_text = f"Web Search Results for: {query}\n\n"
        for i, item in enumerate(result.get("results", [])[:5], 1):
            title = item.get("title", "")
            content = item.get("description", "") or item.get("snippet", "")
            url_link = item.get("url", "")
            
            if title or content:
                results_text += f"{i}. {title}\n"
                if content:
                    results_text += f"   {content}\n"
                if url_link:
                    results_text += f"   Source: {url_link}\n"
                results_text += "\n"
        
        return results_text if len(result.get("results", [])) > 0 else "No web search results found"
    except Exception as e:
        print(f"Error in web search: {e}")
        return f"Web search failed: {str(e)}"

# ==================== Graph Nodes ====================
def fetch_reports_node(state):
    """Fetch all reports from API."""
    print("\n" + "="*60)
    print("🔄 STATE: FETCH REPORTS")
    print("="*60)
    print(f"Symbol: {state['symbol']}")
    print(f"Query: {state['query']}")
    
    reports = fetch_reports(state["symbol"])
    state["reports_context"] = reports
    
    if reports:
        print(f"✅ Reports fetched: {len(reports)} characters")
        print(f"Reports preview: {reports[:200]}..." if len(reports) > 200 else reports[:200])
    else:
        print("❌ No reports available")
    return state

def judge_context_node(state):
    """Judge if additional fundamental/market context is needed."""
    print("\n" + "="*60)
    print("⚖️  STATE: JUDGE CONTEXT")
    print("="*60)
    
    reports_preview = state["reports_context"][:1000] if state["reports_context"] else "No reports available"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a judge determining what additional context is needed to answer a user's query about stocks. Based on the query and existing reports, decide if fundamental data (10K forms, financial statements) or market data (price movements, technical analysis) is needed. If reports are unavailable, fundamental data is usually needed."),
        ("human", "Query: {query}\n\nExisting Reports:\n{reports}\n\nDetermine what additional context is needed.")
    ])
    
    chain = prompt | llm.with_structured_output(ContextNeeded)
    result = chain.invoke({
        "query": state["query"],
        "reports": reports_preview
    })
    
    print(f"📊 Decision: Fundamental needed = {result.fundamental_needed}")
    print(f"📈 Decision: Market needed = {result.market_needed}")
    
    # Fetch contexts if needed
    if result.fundamental_needed == "yes":
        print("🔍 Fetching fundamental data...")
        fundamental_data = fetch_fundamental_data(state["query"])
        state["fundamental_context"] = fundamental_data
        if fundamental_data:
            print(f"✅ Fundamental data fetched: {len(fundamental_data)} characters")
        else:
            print("❌ Fundamental data fetch failed")
    
    if result.market_needed == "yes":
        print("📉 Fetching market data...")
        # Placeholder - use default values for now
        state["market_context"] = fetch_market_data(
            state["symbol"], 
            "2024-01-01", 
            "2024-12-31", 
            "1d"
        )
        print(f"✅ Market data fetched: {len(state['market_context'])} characters")
    
    return state

def judge_websearch_node(state):
    """Judge if web search is needed."""
    print("\n" + "="*60)
    print("🌐 STATE: JUDGE WEB SEARCH")
    print("="*60)
    print(f"Current context status:")
    print(f"  - Reports: {'✅ Yes' if state['reports_context'] else '❌ No'}")
    print(f"  - Fundamental: {'✅ Yes' if state['fundamental_context'] else '❌ No'}")
    print(f"  - Market: {'✅ Yes' if state['market_context'] else '❌ No'}")
    
    # Check if we have ANY valid context
    has_any_context = bool(state['reports_context'] or state['fundamental_context'] or state['market_context'])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a judge determining if web search is needed to answer the user's query. If existing context is insufficient or unavailable (all No), you MUST use web search. Also use web search for recent data, current events, or news."),
        ("human", "Query: {query}\n\nExisting Context Available:\n- Reports: {has_reports}\n- Fundamental: {has_fundamental}\n- Market: {has_market}\n\nNote: If all context is 'No', web search is REQUIRED. Determine if web search is needed.")
    ])
    
    chain = prompt | llm.with_structured_output(WebSearchNeeded)
    result = chain.invoke({
        "query": state["query"],
        "has_reports": "Yes" if state["reports_context"] else "No",
        "has_fundamental": "Yes" if state["fundamental_context"] else "No",
        "has_market": "Yes" if state["market_context"] else "No",
    })
    
    # Override: Force web search if no context at all
    if not has_any_context:
        print("⚠️  No context available - forcing web search")
        result.web_search_needed = "yes"
    
    print(f"🔍 Decision: Web search needed = {result.web_search_needed}")
    
    if result.web_search_needed == "yes":
        print("🌍 Performing web search...")
        web_result = web_search(state["query"])
        state["web_context"] = web_result
        if web_result and not web_result.startswith("Web search"):
            print(f"✅ Web search completed: {len(web_result)} characters")
        else:
            print(f"⚠️  Web search returned: {web_result[:100]}")
    else:
        print("⏭️  Skipping web search")
    
    return state

def answer_node(state):
    """Generate final answer using all collected context."""
    print("\n" + "="*60)
    print("💡 STATE: GENERATE ANSWER")
    print("="*60)
    
    # Build context
    context_parts = []
    if state["reports_context"]:
        context_parts.append(f"=== REPORTS ===\n{state['reports_context']}")
    if state["fundamental_context"]:
        context_parts.append(f"=== FUNDAMENTAL DATA ===\n{state['fundamental_context']}")
    if state["market_context"]:
        context_parts.append(f"=== MARKET DATA ===\n{state['market_context']}")
    if state["web_context"]:
        context_parts.append(f"=== WEB SEARCH ===\n{state['web_context']}")
    
    full_context = "\n\n".join(context_parts) if context_parts else "No context available."
    
    print(f"📝 Total context sections: {len(context_parts)}")
    print(f"📏 Total context length: {len(full_context)} characters")
    
    # Show what context we have
    if context_parts:
        print("📦 Available contexts:")
        if state["reports_context"]: print("  ✅ Reports")
        if state["fundamental_context"]: print("  ✅ Fundamental")
        if state["market_context"]: print("  ✅ Market")
        if state["web_context"]: print("  ✅ Web Search")
    else:
        print("⚠️  No context available!")
    
    print(f"🤖 Generating answer with LLM...")
    
    system_prompt = """You are a financial analyst assistant. Use the provided context to answer the user's query accurately and comprehensively.

IMPORTANT INSTRUCTIONS:
- If web search results are provided, extract and use specific financial data from them
- Look for revenue, earnings, financial metrics in the search results
- Cite specific numbers and sources when available
- If context is limited, provide the best answer possible from what's available
- Be direct and informative, not apologetic"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Query: {query}\n\nContext:\n{context}\n\nProvide a comprehensive answer based on the available information:")
    ])
    
    chain = prompt | llm
    result = chain.invoke({
        "query": state["query"],
        "context": full_context
    })
    
    state["response"] = result.content
    print(f"✅ Answer generated: {len(result.content)} characters")
    print("="*60)
    return state

# ==================== Build Graph ====================
graph = StateGraph(dict)

# Add nodes
graph.add_node("fetch_reports", fetch_reports_node)
graph.add_node("judge_context", judge_context_node)
graph.add_node("judge_websearch", judge_websearch_node)
graph.add_node("answer", answer_node)

# Set entry point and edges
graph.set_entry_point("fetch_reports")
graph.add_edge("fetch_reports", "judge_context")
graph.add_edge("judge_context", "judge_websearch")
graph.add_edge("judge_websearch", "answer")
graph.add_edge("answer", END)

app = graph.compile()

# ==================== Main Function ====================
def run_orchestrator(query, symbol="AAPL"):
    """Run the orchestrator workflow."""
    print("\n" + "#"*60)
    print("🚀 STARTING ORCHESTRATOR WORKFLOW")
    print("#"*60)
    print(f"Query: {query}")
    print(f"Symbol: {symbol}")
    
    state = model_state(query, symbol)
    result = app.invoke(state)
    
    print("\n" + "#"*60)
    print("✨ WORKFLOW COMPLETED")
    print("#"*60)
    print(f"\n📄 FINAL ANSWER:\n{result['response']}")
    print("\n" + "#"*60)
    
    return result["response"]

if __name__ == "__main__":
    response = run_orchestrator("What is Apple's revenue?", symbol="AAPL")
    print("\n" + response)