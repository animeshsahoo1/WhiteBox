"""
Enhanced Agentic RAG API with Pathway MCP Server
Features: ReAct reasoning, MCP tool calling, self-reflection
Serves on port 8000, MCP on port 8766
"""
import os
import sys
import asyncio
import threading
import json
import re
from datetime import datetime
from typing import List, Literal, Annotated, Sequence, Optional
from dotenv import load_dotenv
from pathlib import Path

from fastapi import FastAPI, HTTPException, APIRouter, UploadFile, File, Form

# Add parent directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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

# OpenRouter client for contextual enrichment (OpenAI-compatible API)
from openai import OpenAI
_openrouter_client = None

def get_openrouter_client():
    """Get OpenRouter client (OpenAI-compatible)."""
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
    return _openrouter_client

def enrich_chunks_batch(chunks: list, full_context: str, batch_size: int = 20) -> list:
    """
    Enrich chunks with contextual summaries using batched OpenRouter calls.
    Much faster than per-chunk LLM calls.
    
    Args:
        chunks: List of chunk dicts with 'text' field
        full_context: Full document text for context
        batch_size: Chunks per API call (default 20)
    
    Returns:
        List of enriched text strings
    """
    client = get_openrouter_client()
    enriched_texts = []
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    
    print(f"📝 Enriching {len(chunks)} chunks in {total_batches} batches...")
    
    for batch_idx in range(0, len(chunks), batch_size):
        batch = chunks[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        
        # Progress indicator
        progress = int((batch_num / total_batches) * 20)
        bar = "█" * progress + "░" * (20 - progress)
        print(f"\r  [{bar}] {batch_num}/{total_batches}", end="", flush=True)
        
        # Build prompt for batch
        chunks_text = '\n'.join(f'Chunk {i+1}: {c.get("text", "")[:250]}' for i, c in enumerate(batch))
        
        prompt = f"""You are analyzing an SEC 10-K financial filing. For each chunk, provide a brief context (1-2 sentences) that helps retrieve this chunk when searching.

Focus on: company name, financial metrics, time periods, section references (Item 1, 7, 8), key topics.

Document (first 1500 chars):
{full_context[:1500]}

Chunks:
{chunks_text}

Format (one line per chunk):
Chunk 1: <context>
Chunk 2: <context>
..."""
        
        try:
            response = client.chat.completions.create(
                model="google/gemini-2.0-flash-lite-001",  # Fast & cheap via OpenRouter
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            # Parse contexts
            contexts = []
            for line in content.strip().split('\n'):
                if line.startswith('Chunk '):
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        contexts.append(parts[1].strip())
            
            # Pad if needed
            while len(contexts) < len(batch):
                contexts.append("")
            
            # Build enriched texts
            for chunk, context in zip(batch, contexts[:len(batch)]):
                text = chunk.get("text", "")
                if context:
                    enriched_texts.append(f"Context: {context}\n\nContent: {text}")
                else:
                    enriched_texts.append(text)
                    
        except Exception as e:
            print(f"\n  ⚠️ Batch {batch_num} error: {e}")
            # Fallback: use raw text
            for chunk in batch:
                enriched_texts.append(chunk.get("text", ""))
    
    print(f"\r  [{'█' * 20}] {total_batches}/{total_batches} ✓")
    return enriched_texts


def prechunked_json_parser(data: bytes) -> list[tuple[str, dict]]:
    """
    Parse a JSONL file where each line is already a chunk.
    Returns a list with one tuple per line: (text, metadata_dict)
    
    Handles malformed JSONL where multiple JSON objects may be on the same line.
    """
    import json
    import re
    
    content = data.decode('utf-8').strip()
    chunks = []
    
    # Split by newlines first
    lines = content.split('\n')
    
    # Collect all JSON objects, handling multiple per line
    all_json_objects = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try parsing the line directly first
        try:
            obj = json.loads(line)
            all_json_objects.append(obj)
        except json.JSONDecodeError:
            # Line might have multiple JSON objects concatenated
            # Split by }{ pattern and reconstruct valid JSON
            parts = re.split(r'\}\s*\{', line)
            for i, part in enumerate(parts):
                # Reconstruct the JSON object
                if i == 0:
                    part = part + '}'  # First part missing closing brace
                elif i == len(parts) - 1:
                    part = '{' + part  # Last part missing opening brace
                else:
                    part = '{' + part + '}'  # Middle parts missing both
                
                # Handle edge case where original was already complete
                if not part.startswith('{'):
                    part = '{' + part
                if not part.endswith('}'):
                    part = part + '}'
                
                try:
                    obj = json.loads(part)
                    all_json_objects.append(obj)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Skipping malformed JSON chunk: {e}")
                    continue
    
    # Build full_text from all objects
    all_texts = [obj.get("text", "") for obj in all_json_objects]
    full_text = " ".join(all_texts)
    
    # Check if contextual enrichment is enabled (default: False for baseline testing)
    enable_contextual = os.getenv("CONTEXTUAL_ENRICHMENT", "false").lower() == "true"
    
    # Enrich chunks in batch if enabled (fast batch processing with progress bar)
    if enable_contextual and all_json_objects:
        enriched_texts = enrich_chunks_batch(all_json_objects, full_text)
    else:
        enriched_texts = [obj.get("text", "") for obj in all_json_objects]
    
    # Build final chunks with metadata
    for i, chunk in enumerate(all_json_objects):
        text = enriched_texts[i] if i < len(enriched_texts) else chunk.get("text", "")
        timestamp = chunk.get("timestamp", datetime.now().isoformat())
        
        metadata = {
            "symbol": chunk.get("symbol", "AAPL"),
            "timestamp": timestamp,
        }
        chunks.append((text, metadata))
    
    return chunks

def start_pathway_docstore():
    """Run Pathway DocumentStore in background thread."""
    # Use /app/knowledge_base for Docker, local path for development
    # Docker sets KNOWLEDGE_BASE_PATH env var explicitly
    default_path = str(Path(__file__).parent.parent.parent / "knowledge_base")
    knowledge_base_path = os.getenv("KNOWLEDGE_BASE_PATH", default_path)
    jsonl_pattern = f"{knowledge_base_path}/**/*.jsonl"  # Watch all JSONL files recursively
    
    print(f"📂 Knowledge base path: {knowledge_base_path}")
    print(f"📂 Loading documents from: {jsonl_pattern}")
    
    # Check if files exist
    import glob
    files = glob.glob(jsonl_pattern, recursive=True)
    print(f"📂 Found {len(files)} JSONL files: {files}")
    
    # Use 'static' mode to load existing files on startup
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

# ==================== Retrieval Layer (with optional Reranking) ====================

# Check for Cohere availability
try:
    import cohere
    COHERE_AVAILABLE = True
except ImportError:
    COHERE_AVAILABLE = False
    print("⚠️ Cohere not installed. Reranking disabled. Run: pip install cohere")

# Config: Enable/disable reranking via env var
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"


def rerank_documents(query: str, documents: list, top_n: int = 5) -> list:
    """
    Rerank documents using Cohere Rerank API (like competitor's CohereRerank).
    This is the core reranking function used across the pipeline.
    
    Args:
        query: The search query
        documents: List of document dicts with 'text' field
        top_n: Number of top documents to return after reranking
    
    Returns:
        Reranked list of documents sorted by relevance
    """
    cohere_key = os.getenv("COHERE_API_KEY")
    
    if not COHERE_AVAILABLE or not cohere_key or not RERANK_ENABLED:
        return documents[:top_n]  # Fallback: return as-is
    
    if not documents:
        return []
    
    try:
        co = cohere.ClientV2(api_key=cohere_key)
        
        # Extract texts for reranking
        doc_texts = [d.get("text", "") for d in documents]
        
        response = co.rerank(
            model="rerank-v3.5",  # Latest Cohere rerank model
            query=query,
            documents=doc_texts,
            top_n=min(top_n, len(documents))
        )
        
        # Reorder documents based on rerank results
        reranked = []
        for result in response.results:
            doc = documents[result.index].copy()
            doc["rerank_score"] = result.relevance_score
            reranked.append(doc)
        
        return reranked
    except Exception as e:
        print(f"⚠️ Rerank failed: {e}")
        return documents[:top_n]


def retrieve_from_pathway(query: str, k: int = 5, use_rerank: bool = True) -> list:
    """
    Central retrieval function - retrieves from Pathway and optionally reranks.
    Used by both agent tools and API endpoints.
    
    Strategy: Over-retrieve (k*2) then rerank to top k (like competitor's approach)
    
    Args:
        query: Search query
        k: Final number of documents to return
        use_rerank: Whether to apply Cohere reranking
    
    Returns:
        List of document dicts with text and metadata
    """
    try:
        url = "http://127.0.0.1:8765/v1/retrieve"
        # Over-retrieve if reranking (retrieve 2x, rerank to top k)
        retrieve_k = k * 2 if (use_rerank and RERANK_ENABLED) else k
        
        r = requests.post(url, json={"query": query, "k": retrieve_k}, timeout=200)  # Increased timeout
        r.raise_for_status()
        results = r.json()
        
        if not results:
            return []
        
        # Apply reranking if enabled
        if use_rerank and RERANK_ENABLED:
            results = rerank_documents(query, results, top_n=k)
        
        return results
    except Exception as e:
        print(f"⚠️ Retrieval error: {e}")
        return []


# ==================== MCP Tools ====================

@tool
def retrieve_documents(query: str, k: int = 5) -> str:
    """
    Retrieve relevant financial documents from the Pathway knowledge base.
    Uses over-retrieval + Cohere reranking for better precision.
    
    Args:
        query: The search query to find relevant documents
        k: Number of documents to retrieve (default 5)
    """
    results = retrieve_from_pathway(query, k=k, use_rerank=True)
    
    if not results:
        return "No documents found for the query."
    
    # Format results for LLM
    formatted = []
    for i, result in enumerate(results, 1):
        text = result.get("text", "")[:500]
        metadata = result.get("metadata", {})
        score_info = f" (relevance: {result.get('rerank_score', 'N/A'):.3f})" if 'rerank_score' in result else ""
        formatted.append(f"[Doc {i}{score_info}] {text}\nMetadata: {json.dumps(metadata)}")
    
    return "\n\n".join(formatted)

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
    refinement_prompt = f"""Original: "{original_query}"
Missing: {context}
Generate a more specific search query (query only):"""
    
    response = llm.invoke(refinement_prompt)
    return f"Refined query: {response.content}"

# List of tools available to agent
agent_tools = [retrieve_documents, web_search, refine_query]

# Bind tools to LLM
llm_with_tools = llm.bind_tools(agent_tools)

# Reflection LLM
reflection_prompt = ChatPromptTemplate.from_messages([
    ("system", """Evaluate the answer:
1. Grounded: Claims supported by context? (no hallucinations)
2. Complete: Fully addresses the question?
3. Sufficient: Needs more retrieval?
Be strict. Unsupported claims = not grounded."""),
    ("human", "Question: {question}\n\nContext: {context}\n\nAnswer: {answer}")
])
reflection_llm = reflection_prompt | llm.with_structured_output(ReflectionResult)

# ==================== Agent System Prompt ====================

AGENT_SYSTEM_PROMPT = """Financial research assistant with tool access.

Workflow (ReAct):
1. THINK: What information do I need?
2. ACT: Use tools
   - retrieve_documents: Financial reports, earnings, company data
   - web_search: Current news, real-time prices
   - refine_query: Improve search if results are insufficient
3. OBSERVE: Review results
4. REPEAT: Fill gaps if needed
5. ANSWER: Provide comprehensive response with sources

Rules:
- Start with document retrieval for financial questions
- Use web search for current/recent information
- Cite sources
- Be concise but thorough
- If information unavailable, state clearly
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


@router.get("/debug/stats")
def debug_stats():
    """Get document store statistics - useful for debugging."""
    try:
        # Try to retrieve with a generic query to see if anything is indexed
        url = "http://127.0.0.1:8765/v1/statistics"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return {"status": "ok", "statistics": r.json()}
    except:
        pass
    
    # Fallback: try retrieve endpoint with empty-ish query
    try:
        url = "http://127.0.0.1:8765/v1/retrieve"
        r = requests.post(url, json={"query": "document", "k": 10}, timeout=10)
        results = r.json() if r.status_code == 200 else []
        return {
            "status": "ok",
            "message": "Retrieved sample documents",
            "count": len(results),
            "samples": results[:5] if results else "No documents found - check if files are being loaded"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/debug/retrieve")
def debug_retrieve(q: str = "Apple", k: int = 5, rerank: bool = True):
    """
    Debug endpoint to test retrieval directly.
    Uses centralized retrieve_from_pathway with optional reranking.
    
    Args:
        q: Query string
        k: Number of results
        rerank: Enable/disable reranking (default True)
    """
    results = retrieve_from_pathway(q, k=k, use_rerank=rerank)
    return {
        "query": q,
        "count": len(results),
        "rerank_enabled": rerank and RERANK_ENABLED,
        "results": results
    }


# ==================== Ingestion API ====================

# Knowledge base path for ingestion - use env var for Docker, fallback to local for dev
_default_kb_path = str(Path(__file__).parent.parent.parent / "knowledge_base")
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", _default_kb_path)


class IngestTextRequest(BaseModel):
    text: str
    symbol: str = "UNKNOWN"


class IngestDocumentRequest(BaseModel):
    text: str
    symbol: str = "UNKNOWN"
    chunk_size: int = 999  # characters per chunk


@router.post("/ingest/text")
def ingest_text(req: IngestTextRequest):
    """Ingest a single text as one chunk into the vector store."""
    timestamp = datetime.now().isoformat()
    filename = f"ingest_text_{int(datetime.now().timestamp())}.jsonl"
    filepath = Path(KNOWLEDGE_BASE_PATH) / filename
    
    chunk = {
        "text": req.text,
        "symbol": req.symbol,
        "timestamp": timestamp
    }
    
    with open(filepath, "a") as f:
        f.write(json.dumps(chunk) + "\n")
    
    return {
        "status": "ok",
        "message": "Text ingested",
        "file": filename,
        "chunks": 1
    }


@router.post("/ingest/document")
def ingest_document(req: IngestDocumentRequest):
    """Ingest a document, splitting into chunks by character count."""
    timestamp = datetime.now().isoformat()
    filename = f"ingest_doc_{int(datetime.now().timestamp())}.jsonl"
    filepath = Path(KNOWLEDGE_BASE_PATH) / filename
    
    # Split text into chunks by characters
    text = req.text
    chunks = []
    for i in range(0, len(text), req.chunk_size):
        chunk_text = text[i:i + req.chunk_size]
        chunks.append({
            "text": chunk_text,
            "symbol": req.symbol,
            "chunk_index": len(chunks),
            "timestamp": timestamp
        })
    
    with open(filepath, "w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    
    return {
        "status": "ok",
        "message": f"Document ingested as {len(chunks)} chunks",
        "file": filename,
        "chunks": len(chunks)
    }


@router.get("/ingest/list")
def ingest_list():
    """List all ingested files (text, documents, and parsed files)."""
    path = Path(KNOWLEDGE_BASE_PATH)
    # Get all ingest_* files (text, doc, file)
    files = list(path.glob("ingest_*.jsonl"))
    # Also list uploaded source files
    uploads_dir = path / "uploads"
    uploads = list(uploads_dir.glob("*")) if uploads_dir.exists() else []
    
    return {
        "jsonl_files": [f.name for f in files],
        "source_files": [f.name for f in uploads],
        "count": len(files)
    }


@router.delete("/ingest/{filename}")
def ingest_delete(filename: str):
    """Delete an ingested file (and its source if applicable)."""
    if not filename.startswith("ingest_"):
        raise HTTPException(status_code=400, detail="Can only delete ingest_* files")
    
    filepath = Path(KNOWLEDGE_BASE_PATH) / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Also try to delete corresponding source file if it exists
    # ingest_file_xxx.jsonl -> try to find source in uploads/
    filepath.unlink()
    
    return {"status": "ok", "message": f"Deleted {filename}"}


# ==================== File Parsing (PDF/Image) ====================

def normalize_text(markdown: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", "", markdown)
    text = text.replace("\n\n", "\n").strip()
    return text


# ==================== Unstructured Parser (Fallback) ====================

def unstructured_request(
    api_key: str,
    contents: bytes,
    strategy: str = "hi_res",
    max_retries: int = 3,
    retry_delay: float = 2.0,
):
    """Send request to Unstructured API with retry logic."""
    import time
    import logging
    
    api_url = "https://api.unstructuredapp.io/general/v0/general"
    headers = {
        "accept": "application/json",
        "unstructured-api-key": api_key,
    }
    files = {"files": contents}
    data = {"strategy": strategy}

    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return None
    return None


def parse_file_with_unstructured(file_path: Path, symbol: str) -> List[dict]:
    """
    Parse PDF/Image using Unstructured API (fallback parser).
    Requires UNSTRUCTURED_API_KEY env var.
    """
    api_key = os.getenv("UNSTRUCTURED_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="UNSTRUCTURED_API_KEY not set")
    
    print(f"📄 Parsing with Unstructured: {file_path.name}")
    
    with open(file_path, "rb") as f:
        contents = f.read()
    
    response = unstructured_request(api_key, contents)
    
    if response is None:
        raise HTTPException(status_code=500, detail="Unstructured API request failed")
    
    try:
        elements = response.json()
    except:
        elements = eval(response.text)
    
    timestamp = datetime.now().isoformat()
    chunks = []
    
    for element in elements:
        text = element.get("text", "")
        if not text.strip():
            continue
        
        chunks.append({
            "text": text,
            "symbol": symbol,
            "type": element.get("type", "unknown"),
            "element_id": element.get("element_id", ""),
            "timestamp": timestamp
        })
    
    print(f"✓ Extracted {len(chunks)} chunks from {file_path.name} (Unstructured)")
    return chunks


# ==================== LandingAI Parser (Primary) ====================

def parse_file_with_landingai(file_path: Path, symbol: str) -> List[dict]:
    """
    Parse PDF/Image using LandingAI ADE and return chunks.
    Extracted from streaming/producers/pdf_parser.py
    """
    try:
        from landingai_ade import LandingAIADE
        client = LandingAIADE()
        
        print(f"📄 Parsing with LandingAI: {file_path.name}")
        
        response = client.parse(
            document=file_path,
            model="dpt-2-latest"
        )
        
        timestamp = datetime.now().isoformat()
        chunks = []
        for ch in response.chunks:
            chunks.append({
                "text": normalize_text(ch.markdown),
                "symbol": symbol,
                "page": ch.grounding.page,
                "type": ch.type,
                "chunk_id": ch.id,
                "timestamp": timestamp
            })
        
        print(f"✓ Extracted {len(chunks)} chunks from {file_path.name}")
        return chunks
        
    except ImportError:
        raise HTTPException(status_code=500, detail="LandingAI ADE not installed. Run: pip install landingai-ade")
    except Exception as e:
        print(f"❌ Error parsing {file_path.name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")


@router.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    symbol: str = Form(default="UNKNOWN"),
    parser: str = Form(default="landingai")  # hidden option: "unstructured"
):
    """
    Upload and parse a PDF or image file into the vector store.
    Uses LandingAI ADE (primary) with Unstructured API fallback.
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed: {allowed_extensions}"
        )
    
    # Create uploads directory
    uploads_dir = Path(KNOWLEDGE_BASE_PATH) / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    
    # Save uploaded file
    timestamp = int(datetime.now().timestamp())
    source_filename = f"{timestamp}_{file.filename}"
    source_path = uploads_dir / source_filename
    
    with open(source_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    print(f"📁 Saved upload: {source_path}")
    
    # Parse file - try primary parser, fallback to secondary
    chunks = None
    used_parser = parser
    
    if parser == "unstructured":
        # Direct unstructured parsing
        chunks = parse_file_with_unstructured(source_path, symbol)
    else:
        # Try LandingAI first, fallback to Unstructured
        try:
            chunks = parse_file_with_landingai(source_path, symbol)
            used_parser = "landingai"
        except Exception as e:
            print(f"⚠️ LandingAI failed: {e}, trying Unstructured fallback...")
            try:
                chunks = parse_file_with_unstructured(source_path, symbol)
                used_parser = "unstructured"
            except Exception as e2:
                source_path.unlink()
                raise HTTPException(status_code=500, detail=f"All parsers failed. LandingAI: {e}, Unstructured: {e2}")
    
    if not chunks:
        source_path.unlink()
        raise HTTPException(status_code=500, detail="No content extracted from file")
    
    # Save chunks to JSONL
    jsonl_filename = f"ingest_file_{timestamp}.jsonl"
    jsonl_path = Path(KNOWLEDGE_BASE_PATH) / jsonl_filename
    
    with open(jsonl_path, "w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    
    return {
        "status": "ok",
        "message": f"File parsed and ingested",
        "source_file": source_filename,
        "jsonl_file": jsonl_filename,
        "chunks": len(chunks),
        "symbol": symbol,
        "parser_used": used_parser
    }


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


# ==================== Standalone Mode ====================
if __name__ == "__main__":
    import uvicorn
    
    print("=" * 70)
    print("🚀 Starting RAG API Server (Standalone Mode)")
    print("=" * 70)
    print("📡 FastAPI Server: http://127.0.0.1:8000")
    print("🔧 MCP Server: http://127.0.0.1:8766/mcp/")
    print("📚 DocumentStore: http://127.0.0.1:8765")
    print("=" * 70)
    print("\n📖 Endpoints:")
    print("  GET / - API info")
    print("  GET /health - Health check")
    print("  GET /debug/stats - Document store stats")
    print("  POST /query - Submit RAG query with guardrails")
    print("\n🔍 MCP Usage:")
    print("  The MCP server exposes DocumentStore tools for retrieval.")
    print("  Tools are automatically called by the LangGraph agent.")
    print("  Direct MCP access: http://127.0.0.1:8766/mcp/")
    print("=" * 70)
    
    app = FastAPI(title="RAG API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add root route for standalone mode
    @app.get("/")
    def root():
        return {
            "service": "RAG API (Standalone)",
            "version": "1.0.0",
            "endpoints": {
                "/health": "Health check",
                "/debug/stats": "Document store statistics",
                "/debug/retrieve": "Test retrieval",
                "/query": "RAG query with guardrails",
                "/ingest/text": "Ingest text",
                "/ingest/file": "Ingest PDF/image"
            }
        }
    
    app.include_router(router)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

