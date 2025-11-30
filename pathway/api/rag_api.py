"""
Enhanced Agentic RAG API with Pathway MCP Server
Features: ReAct reasoning, MCP tool calling, self-reflection
Serves on port 8000, MCP on port 8766
"""
import os
import asyncio
import threading
import json
from typing import List, Literal, Annotated, Sequence
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, APIRouter

# Guardrails
from guardrails import guard_input, guard_output
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
import requests

import pathway as pw
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm.servers import DocumentStoreServer
from pathway.xpacks.llm.llms import LiteLLMChat
from pathway.xpacks.llm.embedders import LiteLLMEmbedder
from pathway.xpacks.llm.mcp_server import PathwayMcp

load_dotenv()
pw.set_license_key(os.getenv("PATHWAY_LICENSE_KEY", ""))
# ==================== Pathway DocumentStore Setup ====================

# Initialize LLM for contextual summarization
summary_llm = LiteLLMChat(
    model="openrouter/google/gemini-2.0-flash-lite-001",
    api_key=os.getenv('OPENROUTER_API_KEY'),
    api_base="https://openrouter.ai/api/v1",
    temperature=0.0
)

def helper(text: str, full_text: str) -> str:
    """
    Generate a contextual summary of a chunk within the full document using LLM.
    This function creates a Pathway table with the prompt and calls the LLM.
    Returns the summary text.
    """
    prompt_content = f"""Summarize the following text chunk in the context of the entire document.
Provide a concise summary that captures the main points of the chunk.

Full Document Context:
{full_text[:500]}...

Text Chunk:
{text}

Summary:
"""
    
    # Create a Pathway table with the prompt in chat format
    queries = pw.debug.table_from_markdown(
        """
        prompt
        placeholder
        """
    )
    
    # Build the chat messages
    queries = queries.select(
        prompt=[{"role": "user", "content": prompt_content}]
    )
    
    # Call the LLM
    responses = queries.select(
        result=summary_llm(pw.this.prompt)
    )

    # Compute and extract the result
    result_df = pw.debug.table_to_pandas(responses)
    if len(result_df) > 0:
        return result_df.iloc[0]['result']
    return "No summary generated"

def prechunked_json_parser(data: bytes) -> list[tuple[str, dict]]:
    """
    Parse a JSONL file where each line is already a chunk.
    Returns a list with one tuple per line: (text, metadata_dict)
    """
    import json
    lines = data.decode('utf-8').strip().split('\n')
    chunks = []
    
    # First pass: collect all text to build full_text
    all_texts = []
    for line in lines:
        if not line.strip():
            continue
        chunk = json.loads(line)
        text = chunk.get("text", "")
        all_texts.append(text)
    
    full_text = " ".join(all_texts)
    
    # Second pass: build chunks with summaries
    for line in lines:
        if not line.strip():
            continue
        chunk = json.loads(line)
        text = chunk.get("text", "")
        
        # Generate contextual summary using helper function
        summary = helper(text, full_text)
        
        metadata = {
            "page": chunk.get("page", 0),
            "chunk_type": chunk.get("type", ""),
            "summary": summary,
        }
        chunks.append((text, metadata))
    
    return chunks

def start_pathway_docstore():
    """Run Pathway DocumentStore in background thread."""
    knowledge_base_path = os.getenv("KNOWLEDGE_BASE_PATH", "/app/knowledge_base")
    jsonl_pattern = f"{knowledge_base_path}/**/jsons/*.jsonl"
    
    raw_docs = pw.io.fs.read(
        path=jsonl_pattern,
        format="binary",
        mode="streaming",
    ).select(data=pw.this.data, _metadata={})

    embedder = LiteLLMEmbedder(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
        capacity=5,
        retry_strategy=pw.udfs.ExponentialBackoffRetryStrategy(max_retries=3),
        cache_strategy=None,
    )

    retriever_factory = BruteForceKnnFactory(embedder=embedder)

    store = DocumentStore(
        docs=raw_docs,
        retriever_factory=retriever_factory,
        parser=prechunked_json_parser,
        splitter=None,
    )

    server = DocumentStoreServer(
        host="127.0.0.1",
        port=8765,
        document_store=store,
    )
    
    # MCP Server - exposes DocumentStore as MCP tools
    mcp_server = PathwayMcp(
        name="RAG Document Store MCP",
        transport="streamable-http",
        host="127.0.0.1",
        port=8766,
        serve=[store],  # DocumentStore inherits McpServable
    )
    
    # server.run() internally calls pw.run() - no need to call it separately
    server.run(threaded=False, with_cache=False)

# Start Pathway in background
pathway_thread = threading.Thread(target=start_pathway_docstore, daemon=True)
pathway_thread.start()

# MCP Server URL for tool calls
MCP_SERVER_URL = "http://127.0.0.1:8766/mcp/"

# ==================== LangGraph Agentic Workflow Setup ====================

# Pydantic models for reflection
class ReflectionResult(BaseModel):
    is_grounded: bool = Field(description="Is the answer grounded in the retrieved context?")
    is_complete: bool = Field(description="Does the answer fully address the question?")
    needs_more_info: bool = Field(description="Does the agent need to retrieve more information?")
    critique: str = Field(description="Brief critique of the answer")

# Enhanced Agent State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: str
    context: List[Document]
    generation: str
    iteration: int

# LLM setup
llm = ChatOpenAI(
    model="google/gemini-2.5-flash-lite",
    temperature=0,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# ==================== MCP Tools ====================

@tool
def retrieve_documents(query: str, k: int = 5) -> str:
    """
    Retrieve relevant financial documents from the Pathway knowledge base via MCP.
    Use this tool to get context about financial reports, earnings, company data.
    
    Args:
        query: The search query to find relevant documents
        k: Number of documents to retrieve (default 5)
    """
    try:
        # Call Pathway MCP Server
        url = "http://127.0.0.1:8765/v1/retrieve"
        payload = {"query": query, "k": k}
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        results = r.json()
        
        if not results:
            return "No documents found for the query."
        
        # Format results for LLM
        formatted = []
        for i, result in enumerate(results, 1):
            text = result.get("text", "")[:500]
            metadata = result.get("metadata", {})
            formatted.append(f"[Doc {i}] {text}\nMetadata: {json.dumps(metadata)}")
        
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Error retrieving documents: {str(e)}"

@tool
def web_search(query: str) -> str:
    """
    Search the web for current events, news, and real-time information.
    Use this tool for recent news, current stock prices, or information not in documents.
    
    Args:
        query: The search query for web search
    """
    serpex_api_key = os.getenv("SERPEX_API_KEY")
    
    if not serpex_api_key:
        return "Web search unavailable - API key not configured."
    
    try:
        url = "https://api.serpex.dev/api/search"
        headers = {"Authorization": f"Bearer {serpex_api_key}"}
        params = {"q": query, "engine": "auto", "category": "web", "time_range": "week"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        formatted = []
        for item in result.get("results", [])[:7]:
            title = item.get("title", "")
            snippet = item.get("description", "") or item.get("snippet", "")
            url = item.get("url", "")
            if title or snippet:
                formatted.append(f"**{title}**\n{snippet}\nSource: {url}")
        
        return "\n\n".join(formatted) if formatted else "No web results found."
    except Exception as e:
        return f"Web search failed: {str(e)}"

@tool
def refine_query(original_query: str, context: str) -> str:
    """
    Refine a search query based on initial results to get better information.
    Use this when initial retrieval didn't give enough relevant results.
    
    Args:
        original_query: The original search query
        context: What information is still missing or needed
    """
    refinement_prompt = f"""Based on this original query: "{original_query}"
And the need for: {context}
Generate a more specific search query (just the query, nothing else):"""
    
    response = llm.invoke(refinement_prompt)
    return f"Refined query: {response.content}"

# List of tools available to agent
agent_tools = [retrieve_documents, web_search, refine_query]

# Bind tools to LLM
llm_with_tools = llm.bind_tools(agent_tools)

# Reflection LLM
reflection_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a critical evaluator. Assess if the generated answer is:
1. Grounded in the retrieved context (no hallucinations)
2. Completely addresses the user's question
3. Needs more information retrieval

Be strict but fair. If the answer makes claims not supported by context, mark as not grounded."""),
    ("human", "Question: {question}\n\nContext: {context}\n\nAnswer: {answer}")
])
reflection_llm = reflection_prompt | llm.with_structured_output(ReflectionResult)

# ==================== Agent System Prompt ====================

AGENT_SYSTEM_PROMPT = """You are an intelligent financial research assistant with access to tools.

Your approach (ReAct reasoning):
1. THINK: Analyze what information you need to answer the question
2. ACT: Use tools to gather information
   - retrieve_documents: For financial reports, earnings, company data from knowledge base
   - web_search: For current news, real-time prices, recent events
   - refine_query: To improve search if initial results are insufficient
3. OBSERVE: Review the tool results
4. REPEAT: If needed, use more tools to fill gaps
5. ANSWER: When you have enough context, provide a comprehensive answer

Guidelines:
- Always start by retrieving relevant documents for financial questions
- Use web search for current/recent information
- If retrieval results seem incomplete, use refine_query and try again
- Cite your sources in the answer
- Be concise but thorough
- If you truly cannot find the information, say so honestly

IMPORTANT: When you have gathered enough information, provide your final answer directly WITHOUT calling any more tools.
"""

# ==================== Agentic Workflow Nodes ====================

def agent_node(state: AgentState) -> AgentState:
    """Main agent node - reasons and decides actions using ReAct pattern."""
    messages = state["messages"]
    
    # Add system prompt if first message
    if len(messages) == 1:  # Only user question
        messages = [HumanMessage(content=AGENT_SYSTEM_PROMPT)] + list(messages)
    
    # Call LLM with tools
    response = llm_with_tools.invoke(messages)
    
    return {
        "messages": [response],
        "question": state["question"],
        "context": state.get("context", []),
        "generation": state.get("generation", ""),
        "iteration": state.get("iteration", 0)
    }

def tool_node(state: AgentState) -> AgentState:
    """Execute tools called by agent."""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_results = []
    context_docs = state.get("context", [])
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # Execute the appropriate tool
        if tool_name == "retrieve_documents":
            result = retrieve_documents.invoke(tool_args)
            # Track retrieved content as context
            context_docs.append(Document(page_content=result, metadata={"source": "pathway_mcp"}))
        elif tool_name == "web_search":
            result = web_search.invoke(tool_args)
            context_docs.append(Document(page_content=result, metadata={"source": "web"}))
        elif tool_name == "refine_query":
            result = refine_query.invoke(tool_args)
        else:
            result = f"Unknown tool: {tool_name}"
        
        tool_results.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )
    
    return {
        "messages": tool_results,
        "question": state["question"],
        "context": context_docs,
        "generation": state.get("generation", ""),
        "iteration": state["iteration"] + 1
    }

def synthesize_node(state: AgentState) -> AgentState:
    """Generate final answer from accumulated context."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # The last AI message content is the final answer
    generation = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    return {
        "messages": messages,
        "question": state["question"],
        "context": state.get("context", []),
        "generation": generation,
        "iteration": state["iteration"]
    }

def reflect_node(state: AgentState) -> AgentState:
    """Self-reflection on generated answer."""
    context_text = "\n".join([doc.page_content[:500] for doc in state.get("context", [])])
    
    try:
        reflection = reflection_llm.invoke({
            "question": state["question"],
            "context": context_text if context_text else "No context retrieved",
            "answer": state["generation"]
        })
        
        # If needs more info and under iteration limit, add message to trigger more retrieval
        if reflection.needs_more_info and state["iteration"] < 3:
            return {
                "messages": [HumanMessage(content=f"The answer needs improvement: {reflection.critique}. Please retrieve more information and try again.")],
                "question": state["question"],
                "context": state.get("context", []),
                "generation": state["generation"],
                "iteration": state["iteration"]
            }
    except Exception as e:
        print(f"Reflection failed: {e}")
    
    return state

# ==================== Routing Functions ====================

def should_continue(state: AgentState) -> str:
    """Decide if agent should continue (call tools) or finish."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If max iterations reached, go to synthesize
    if state.get("iteration", 0) >= 3:
        return "synthesize"
    
    # If LLM wants to call tools, route to tool_node
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # Otherwise, synthesize the answer
    return "synthesize"

def should_retry(state: AgentState) -> str:
    """After reflection, decide if we need to retry or finish."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If reflection added a retry message, go back to agent
    if isinstance(last_message, HumanMessage) and "needs improvement" in last_message.content:
        return "retry"
    
    return "end"

# ==================== Build Agentic Workflow ====================

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.add_node("synthesize", synthesize_node)
workflow.add_node("reflect", reflect_node)

# Define edges
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "synthesize": "synthesize"
    }
)
workflow.add_edge("tools", "agent")  # After tools, back to agent
workflow.add_edge("synthesize", "reflect")  # After synthesis, reflect
workflow.add_conditional_edges(
    "reflect",
    should_retry,
    {
        "retry": "agent",
        "end": END
    }
)

# Compile
graph_app = workflow.compile()

async def run_workflow(question: str):
    """Execute the agentic LangGraph workflow."""
    inputs = {
        "messages": [HumanMessage(content=question)],
        "question": question,
        "context": [],
        "generation": "",
        "iteration": 0
    }
    result = await graph_app.ainvoke(inputs)
    return result


# ==================== FastAPI Setup ====================

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list

@router.get("/health")
def health():
    return {"status": "ok", "service": "rag-api"}

@router.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    """Main RAG query endpoint with guardrails."""
    try:
        # INPUT GUARDRAILS: Check for jailbreaks, off-topic, PII
        input_check = guard_input(req.question)
        if not input_check.allowed:
            return {
                "question": req.question,
                "answer": input_check.message,
                "sources": []
            }
        
        # Use guarded input (may have PII masked)
        result = await run_workflow(input_check.message)
        answer = result.get('generation', 'No answer generated')
        
        # OUTPUT GUARDRAILS: Add disclaimer, mask PII
        output_check = guard_output(answer)
        
        return {
            "question": req.question,
            "answer": output_check.message,
            "sources": [{"metadata": doc.metadata, "content": doc.page_content[:200]} for doc in result.get('context', [])]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

