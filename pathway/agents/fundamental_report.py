import os
import requests
from typing import List, Dict, Literal
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "false"

REPORT_SECTIONS = [
    {
        "name": "Executive Summary",
        "tools": ["rag"],
        "description": "High-level snapshot of the company’s business, financial condition, and key fundamental insights."
    },
    {
        "name": "Business Overview",
        "tools": ["rag"],
        "description": "Core operations, segments, revenue sources, business model mechanics, industry structure."
    },
    # {
    #     "name": "Financial Statements Analysis",
    #     "tools": ["rag"],
    #     "description": "Income statement, balance sheet, and cash-flow trends; margin behavior; capital structure; liquidity."
    # },
    # {
    #     "name": "Operational Performance",
    #     "tools": ["rag"],
    #     "description": "Unit economics, cost drivers, efficiency metrics, productivity, and management execution."
    # },
    # {
    #     "name": "Valuation Context (Non-Recommendation)",
    #     "tools": [],
    #     "description": "Multiples comparison, historical valuation ranges, and fundamental factors influencing valuation."
    # },
    # {
    #     "name": "Growth Drivers",
    #     "tools": ["web_search", "rag"],
    #     "description": "Structural demand trends, product/tech developments, capacity expansion, strategic initiatives."
    # },
    # {
    #     "name": "Risks & Constraints",
    #     "tools": ["web_search", "rag"],
    #     "description": "Operational, financial, regulatory, competitive, and macro risks based on filings and external data."
    # },
    # {
    #     "name": "ESG & Governance",
    #     "tools": ["rag"],
    #     "description": "Environmental practices, governance quality, board oversight, compliance factors."
    # }
]

class RouteQuery(BaseModel):
    tool: Literal["rag", "web_search", "none"] = Field(description="Tool to use: rag, web_search, or none")

class GradeHallucinations(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="Answer is grounded in facts")

class GradeAnswer(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="Answer addresses section goal")

class ReportState(TypedDict):
    symbol: str
    fundamental_data: str
    completed_sections: List[str]
    current_section_index: int
    current_section_name: str
    section_content: str
    full_report: str
    attempts: int
    tools_output: str

llm = ChatOpenAI(
    model="google/gemini-2.5-flash-lite",
    temperature=0.3,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

hallucination_grader_prompt = ChatPromptTemplate.from_messages([
    ("system", "Grade if LLM generation is grounded in facts. Binary score 'yes' or 'no'."),
    ("human", "Facts: {documents}\n\nGeneration: {generation}")
])
hallucination_grader = hallucination_grader_prompt | llm.with_structured_output(GradeHallucinations)

answer_grader_prompt = ChatPromptTemplate.from_messages([
    ("system", "Grade if answer addresses section goal. Binary score 'yes' or 'no'."),
    ("human", "Goal: {goal}\n\nAnswer: {generation}")
])
answer_grader = answer_grader_prompt | llm.with_structured_output(GradeAnswer)

def retrieve_rag(question: str) -> List[Document]:
    rag_url = os.getenv("RAG_API_URL", "http://localhost:8001")
    try:
        r = requests.post(f"{rag_url}/query", json={"question": question}, timeout=30)
        r.raise_for_status()
        result = r.json()
        docs = []
        for src in result.get("sources", []):
            docs.append(Document(
                page_content=src.get("content", ""),
                metadata=src.get("metadata", {})
            ))
        return docs
    except Exception as e:
        print(f"RAG error: {e}")
        return []

def web_search(question: str) -> List[Document]:
    serpex_api_key = os.getenv("SERPEX_API_KEY")
    if not serpex_api_key:
        return []
    
    try:
        url = "https://api.serpex.dev/api/search"
        headers = {"Authorization": f"Bearer {serpex_api_key}"}
        params = {"q": question, "engine": "auto", "category": "web", "time_range": "week"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        docs = []
        for item in result.get("results", [])[:3]:
            content = item.get("description", "") or item.get("snippet", "")
            title = item.get("title", "")
            full_content = f"{title}\n{content}" if title else content
            
            if full_content.strip():
                docs.append(Document(
                    page_content=full_content,
                    metadata={"source": "web", "url": item.get("url", "")}
                ))
        
        return docs
    except Exception as e:
        print(f"Web search error: {e}")
        return []

def plan_section_node(state: ReportState) -> Dict:
    idx = state.get("current_section_index", 0)
    
    if idx >= len(REPORT_SECTIONS):
        print(f"✓ All sections complete!")
        return {
            "current_section_index": idx,
            "current_section_name": "COMPLETE"
        }
    
    section = REPORT_SECTIONS[idx]
    print(f"\n[PLAN] Section {idx+1}/{len(REPORT_SECTIONS)}: {section['name']}")
    return {
        "current_section_index": idx,
        "current_section_name": section["name"],
        "attempts": 0
    }

def tool_router_node(state: ReportState) -> Dict:
    section_name = state["current_section_name"]
    
    section = next((s for s in REPORT_SECTIONS if s["name"] == section_name), None)
    if not section or not section["tools"]:
        print(f"[TOOLS] No tools required")
        return {"tools_output": ""}
    
    print(f"[TOOLS] Using: {', '.join(section['tools'])}")
    symbol = state["symbol"]
    query = f"{symbol} {section['description']}"
    
    all_docs = []
    for tool in section["tools"]:
        if tool == "rag":
            docs = retrieve_rag(query)
            print(f"  → RAG returned {len(docs)} documents")
            all_docs.extend(docs)
        elif tool == "web_search":
            docs = web_search(query)
            print(f"  → Web search returned {len(docs)} results")
            all_docs.extend(docs)
    
    combined = "\n\n".join([doc.page_content for doc in all_docs])
    return {"tools_output": combined}

def generate_section_node(state: ReportState) -> Dict:
    section_name = state["current_section_name"]
    fundamental_data = state.get("fundamental_data", "")
    completed_sections = state.get("completed_sections", [])
    full_report = state.get("full_report", "")
    tools_output = state.get("tools_output", "")
    
    print(f"[GENERATE] Writing '{section_name}'...")
    
    section = next((s for s in REPORT_SECTIONS if s["name"] == section_name), None)
    if not section:
        return {"section_content": ""}
    
    system_prompt = f"""You are a senior equity research analyst. Generate the '{section_name}' section for a fundamental analysis report.

Section Description: {section['description']}

Guidelines:
- Professional, analytical tone
- Use specific numbers and metrics
- Evidence-based reasoning
- Concise and actionable
- No placeholder text or incomplete information"""

    user_prompt = f"""Symbol: {state['symbol']}

Financial Data:
{fundamental_data[:2000]}

Previously Completed Sections:
{full_report[:1000]}

Additional Context:
{tools_output[:1000]}

Generate the '{section_name}' section now."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_prompt)
    ])
    
    chain = prompt | llm
    generation = chain.invoke({})
    
    return {
        "section_content": generation.content,
        "attempts": state.get("attempts", 0) + 1
    }

def verify_section_node(state: ReportState) -> Dict:
    section_content = state["section_content"]
    fundamental_data = state["fundamental_data"]
    tools_output = state.get("tools_output", "")
    attempts = state.get("attempts", 0)
    
    print(f"[VERIFY] Checking quality (attempt {attempts})...")
    
    section = next((s for s in REPORT_SECTIONS if s["name"] == state["current_section_name"]), None)
    if not section:
        return {"verification": "pass"}
    
    docs_content = f"{fundamental_data[:1000]}\n{tools_output[:1000]}"
    
    hall_score = hallucination_grader.invoke({
        "documents": docs_content,
        "generation": section_content
    })
    
    if hall_score.binary_score == "no":
        result = "fail" if attempts < 2 else "force_pass"
        print(f"  → Hallucination check: FAILED ({'retrying' if result == 'fail' else 'forcing pass'})")
        return {"verification": result}
    
    ans_score = answer_grader.invoke({
        "goal": section["description"],
        "generation": section_content
    })
    
    if ans_score.binary_score == "yes":
        print(f"  → Quality check: PASSED ✓")
        return {"verification": "pass"}
    
    result = "fail" if attempts < 2 else "force_pass"
    print(f"  → Quality check: FAILED ({'retrying' if result == 'fail' else 'forcing pass'})")
    return {"verification": result}

def accumulate_section_node(state: ReportState) -> Dict:
    section_name = state["current_section_name"]
    section_content = state["section_content"]
    completed_sections = state.get("completed_sections", [])
    full_report = state.get("full_report", "")
    
    print(f"[ACCUMULATE] Adding '{section_name}' to report ✓\n")
    
    updated_report = f"{full_report}\n\n## {section_name}\n\n{section_content}".strip()
    
    return {
        "completed_sections": completed_sections + [section_name],
        "full_report": updated_report,
        "current_section_index": state["current_section_index"] + 1
    }

def should_continue(state: ReportState) -> str:
    if state["current_section_name"] == "COMPLETE":
        return "end"
    return "continue"

def should_regenerate(state: ReportState) -> str:
    verification = state.get("verification", "pass")
    if verification == "pass" or verification == "force_pass":
        return "accumulate"
    return "regenerate"

workflow = StateGraph(ReportState)

workflow.add_node("plan_section", plan_section_node)
workflow.add_node("tool_router", tool_router_node)
workflow.add_node("generate_section", generate_section_node)
workflow.add_node("verify_section", verify_section_node)
workflow.add_node("accumulate_section", accumulate_section_node)

workflow.add_edge(START, "plan_section")
workflow.add_conditional_edges("plan_section", should_continue, {
    "continue": "tool_router",
    "end": END
})
workflow.add_edge("tool_router", "generate_section")
workflow.add_edge("generate_section", "verify_section")
workflow.add_conditional_edges("verify_section", should_regenerate, {
    "accumulate": "accumulate_section",
    "regenerate": "generate_section"
})
workflow.add_edge("accumulate_section", "plan_section")

graph = workflow.compile()

def generate_fundamental_report(symbol: str, fundamental_data: str) -> str:
    print(f"\n{'='*60}")
    print(f"Starting Fundamental Report Generation for {symbol}")
    print(f"{'='*60}\n")
    
    initial_state = {
        "symbol": symbol,
        "fundamental_data": fundamental_data,
        "completed_sections": [],
        "current_section_index": 0,
        "current_section_name": "",
        "section_content": "",
        "full_report": f"# {symbol} - Fundamental Analysis Report\n\n*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*",
        "attempts": 0,
        "tools_output": ""
    }
    
    result = graph.invoke(initial_state)
    
    print(f"\n{'='*60}")
    print(f"Report Generation Complete!")
    print(f"{'='*60}\n")
    
    return result["full_report"]

def main():
    symbol = "AAPL"
    fundamental_data = "Sample fundamental data for Apple Inc. including financial statements, ratios, and key metrics."

    report = generate_fundamental_report(symbol, fundamental_data)
    print(report)

if __name__ == "__main__":
    main()