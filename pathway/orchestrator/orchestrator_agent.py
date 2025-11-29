"""
Orchestrator Agent - Smart query agent with auto context gathering.
Integrated version that uses direct Redis/function calls instead of HTTP.
"""
import os
import requests
import json
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client, get_reports_for_symbol

load_dotenv()

# ==================== LLM Setup ====================
llm = ChatOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    model="openai/gpt-4o-mini",
)

# ==================== Pydantic Models ====================
class ContextNeeded(BaseModel):
    fundamental_needed: Literal["yes", "no"] = Field(description="Whether fundamental/RAG context is needed")
    market_needed: Literal["yes", "no"] = Field(description="Whether market data context is needed")

class WebSearchNeeded(BaseModel):
    web_search_needed: Literal["yes", "no"] = Field(description="Whether web search is needed")

# ==================== Helper Functions ====================
def fetch_reports_direct(symbol: str) -> str:
    """Fetch reports directly from Redis (no HTTP)."""
    try:
        reports = get_reports_for_symbol(symbol)
        if not reports:
            return None
        
        text = f"Symbol: {symbol}\n\n"
        has_any = False
        
        for rtype in ["fundamental", "market", "news", "sentiment", "facilitator"]:
            content = reports.get(rtype, {}).get("content")
            if content:
                text += f"=== {rtype.upper()} REPORT ===\n{content}\n\n"
                has_any = True
        
        return text if has_any else None
    except Exception as e:
        print(f"❌ Error fetching reports: {e}")
        return None

def fetch_rag_context(question: str) -> str:
    """Fetch RAG context - calls the local RAG endpoint."""
    try:
        # Use internal endpoint (same server)
        url = os.getenv("RAG_API_URL", "http://localhost:8000") + "/query"
        r = requests.post(url, json={"question": question}, timeout=15)
        r.raise_for_status()
        data = r.json()
        answer = data.get("answer", "")
        return answer if answer and len(answer) > 10 else None
    except Exception as e:
        print(f"❌ RAG error: {e}")
        return None

def web_search(query: str) -> str:
    """Search web using Serpex API."""
    serpex_key = os.getenv("SERPEX_API_KEY")
    if not serpex_key:
        return None
    
    try:
        r = requests.get(
            "https://api.serpex.dev/api/search",
            headers={"Authorization": f"Bearer {serpex_key}"},
            params={"q": query, "engine": "auto", "category": "web", "time_range": "week"},
            timeout=10
        )
        r.raise_for_status()
        results = r.json().get("results", [])[:5]
        
        if not results:
            return None
        
        text = f"Web Results for: {query}\n\n"
        for i, item in enumerate(results, 1):
            title = item.get("title", "")
            desc = item.get("description", "") or item.get("snippet", "")
            if title:
                text += f"{i}. {title}\n   {desc}\n\n"
        return text
    except Exception as e:
        print(f"❌ Web search error: {e}")
        return None

# ==================== Graph Nodes ====================
def fetch_reports_node(state):
    """Fetch reports from Redis."""
    print(f"📊 Fetching reports for {state['symbol']}...")
    state["reports_context"] = fetch_reports_direct(state["symbol"])
    print(f"   {'✅ Got reports' if state['reports_context'] else '❌ No reports'}")
    return state

def judge_context_node(state):
    """Judge if additional context needed."""
    print("⚖️  Judging context needs...")
    
    preview = state["reports_context"][:1000] if state["reports_context"] else "No reports"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Decide if fundamental data (10K, financials via RAG) or market data is needed to answer the query. If no reports available, fundamental is usually needed."),
        ("human", "Query: {query}\n\nReports:\n{reports}\n\nWhat's needed?")
    ])
    
    result = (prompt | llm.with_structured_output(ContextNeeded)).invoke({
        "query": state["query"], "reports": preview
    })
    
    print(f"   Fundamental: {result.fundamental_needed}, Market: {result.market_needed}")
    
    if result.fundamental_needed == "yes":
        state["fundamental_context"] = fetch_rag_context(state["query"])
    
    if result.market_needed == "yes":
        state["market_context"] = f"Market data for {state['symbol']} (placeholder)"
    
    return state

def judge_websearch_node(state):
    """Judge if web search needed."""
    print("🌐 Judging web search need...")
    
    has_context = bool(state.get("reports_context") or state.get("fundamental_context"))
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Decide if web search is needed. Use it for recent news, current events, or if no other context available."),
        ("human", "Query: {query}\nHas reports: {has_reports}\nHas fundamental: {has_fund}\n\nNeed web search?")
    ])
    
    result = (prompt | llm.with_structured_output(WebSearchNeeded)).invoke({
        "query": state["query"],
        "has_reports": "Yes" if state.get("reports_context") else "No",
        "has_fund": "Yes" if state.get("fundamental_context") else "No",
    })
    
    # Force web search if no context
    if not has_context:
        result.web_search_needed = "yes"
    
    print(f"   Web search: {result.web_search_needed}")
    
    if result.web_search_needed == "yes":
        state["web_context"] = web_search(state["query"])
    
    return state

def answer_node(state):
    """Generate final answer."""
    print("💡 Generating answer...")
    
    parts = []
    if state.get("reports_context"):
        parts.append(f"=== REPORTS ===\n{state['reports_context']}")
    if state.get("fundamental_context"):
        parts.append(f"=== FUNDAMENTAL ===\n{state['fundamental_context']}")
    if state.get("market_context"):
        parts.append(f"=== MARKET ===\n{state['market_context']}")
    if state.get("web_context"):
        parts.append(f"=== WEB ===\n{state['web_context']}")
    
    context = "\n\n".join(parts) if parts else "No context available."
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a financial analyst. Answer the query using the provided context. Be direct and cite specific data when available."),
        ("human", "Query: {query}\n\nContext:\n{context}\n\nAnswer:")
    ])
    
    result = (prompt | llm).invoke({"query": state["query"], "context": context})
    state["response"] = result.content
    print(f"✅ Answer generated ({len(result.content)} chars)")
    return state

# ==================== Build Graph ====================
def _build_graph():
    g = StateGraph(dict)
    g.add_node("fetch_reports", fetch_reports_node)
    g.add_node("judge_context", judge_context_node)
    g.add_node("judge_websearch", judge_websearch_node)
    g.add_node("answer", answer_node)
    
    g.set_entry_point("fetch_reports")
    g.add_edge("fetch_reports", "judge_context")
    g.add_edge("judge_context", "judge_websearch")
    g.add_edge("judge_websearch", "answer")
    g.add_edge("answer", END)
    
    return g.compile()

_app = _build_graph()

# ==================== Main Function ====================
def run_orchestrator(query: str, symbol: str = "AAPL") -> str:
    """Run orchestrator workflow."""
    print(f"\n🚀 Orchestrator: {query} ({symbol})")
    
    state = {
        "query": query,
        "symbol": symbol.upper(),
        "reports_context": None,
        "fundamental_context": None,
        "market_context": None,
        "web_context": None,
        "response": None,
    }
    
    result = _app.invoke(state)
    return result["response"]

if __name__ == "__main__":
    print(run_orchestrator("What is Apple's revenue?", "AAPL"))
