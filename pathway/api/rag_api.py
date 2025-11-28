"""
RAG API combining Pathway DocumentStore + LangGraph workflow
Serves on port 7001
"""
import os
import asyncio
import threading
from typing import List, Literal
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict
import requests

import pathway as pw
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm.servers import DocumentStoreServer
from pathway.xpacks.llm.llms import LiteLLMChat
from pathway.xpacks.llm.embedders import LiteLLMEmbedder

load_dotenv()

# ==================== Pathway DocumentStore Setup ====================

# Initialize LLM for contextual summarization
summary_llm = LiteLLMChat(
    model="openrouter/google/gemini-2.5-flash-lite",
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
    
    # server.run() internally calls pw.run() - no need to call it separately
    server.run(threaded=False, with_cache=False)

# Start Pathway in background
pathway_thread = threading.Thread(target=start_pathway_docstore, daemon=True)
pathway_thread.start()

# ==================== LangGraph Workflow Setup ====================

# Pydantic models
class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search"] = Field(description="Route to vectorstore or web_search")

class GradeDocuments(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="Documents are relevant to the question, 'yes' or 'no'")

class GradeHallucinations(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="Answer is grounded in the facts, 'yes' or 'no'")

class GradeAnswer(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="Answer addresses the question, 'yes' or 'no'")

class GraphState(TypedDict):
    question: str
    documents: List[Document]
    generation: str
    attempts: int

# LLM setup
llm = ChatOpenAI(
    model="google/gemini-2.5-flash-lite",
    temperature=0,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Prompts
router_prompt = ChatPromptTemplate.from_messages([
    ("system", "Route user question to vectorstore or web_search. Use vectorstore for financial documents questions. Use web_search for current events or general knowledge."),
    ("human", "{question}")
])
router = router_prompt | llm.with_structured_output(RouteQuery)

retrieval_grader_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a grader assessing relevance of a retrieved document to a user question. If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. Give a binary score 'yes' or 'no'."),
    ("human", "Question: {question}\n\nDocument: {document}")
])
retrieval_grader = retrieval_grader_prompt | llm.with_structured_output(GradeDocuments)

hallucination_grader_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts. Give a binary score 'yes' or 'no'. 'yes' means that the answer is grounded in / supported by the set of facts."),
    ("human", "Facts: {documents}\n\nGeneration: {generation}")
])
hallucination_grader = hallucination_grader_prompt | llm.with_structured_output(GradeHallucinations)

answer_grader_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a grader assessing whether an answer addresses / resolves a question. Give a binary score 'yes' or 'no'. 'yes' means that the answer resolves the question."),
    ("human", "Question: {question}\n\nAnswer: {generation}")
])
answer_grader = answer_grader_prompt | llm.with_structured_output(GradeAnswer)

rag_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise."),
    ("human", "Question: {question}\n\nContext: {context}")
])

# Retrieval functions
def retrieve(question: str) -> List[Document]:
    """Retrieve from Pathway DocumentStore."""
    url = "http://127.0.0.1:8765/v1/retrieve"
    payload = {"query": question, "k": 3}
    
    try:
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()
        results = r.json()
        
        docs = []
        for result in results:
            text = result.get("text", "")
            metadata = result.get("metadata", {})
            metadata["dist"] = result.get("dist", 0)
            docs.append(Document(page_content=text, metadata=metadata))
        
        print(f"Retrieved {len(docs)} documents from Pathway")
        return docs
    except Exception as e:
        print(f"Error retrieving from Pathway: {e}")
        return []

def web_search(question: str) -> List[Document]:
    """Search the web using Serpex API."""
    serpex_api_key = os.getenv("SERPEX_API_KEY")
    
    if not serpex_api_key:
        return [Document(page_content="Web search unavailable.", metadata={"source": "web"})]
    
    try:
        url = "https://api.serpex.dev/api/search"
        headers = {"Authorization": f"Bearer {serpex_api_key}"}
        params = {"q": question, "engine": "auto", "category": "web", "time_range": "week"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        docs = []
        for item in result.get("results", [])[:5]:
            content = item.get("description", "") or item.get("snippet", "")
            title = item.get("title", "")
            full_content = f"{title}\n{content}" if title else content
            
            if full_content.strip():
                docs.append(Document(
                    page_content=full_content,
                    metadata={"source": "web_search", "url": item.get("url", ""), "title": title}
                ))
        
        return docs if docs else [Document(page_content="No results found.", metadata={"source": "web"})]
    except Exception as e:
        print(f"Error in web search: {e}")
        return [Document(page_content="Web search failed.", metadata={"source": "web"})]

# Workflow nodes
def retrieve_node(state):
    documents = retrieve(state["question"])
    filtered_docs = []
    for doc in documents:
        score = retrieval_grader.invoke({"question": state["question"], "document": doc.page_content})
        if score.binary_score == "yes":
            filtered_docs.append(doc)
    return {"documents": filtered_docs, "question": state["question"], "attempts": state.get("attempts", 0)}

def web_search_node(state):
    documents = web_search(state["question"])
    return {"documents": documents, "question": state["question"], "attempts": state.get("attempts", 0)}

def generate_node(state):
    context = "\n\n".join([doc.page_content for doc in state["documents"]])
    chain = rag_prompt | llm
    generation = chain.invoke({"question": state["question"], "context": context})
    return {"documents": state["documents"], "question": state["question"], "generation": generation.content, "attempts": state["attempts"] + 1}

def route_question_node(state):
    source = router.invoke({"question": state["question"]})
    return "web_search" if source.datasource == "web_search" else "vectorstore"

def grade_generation_node(state):
    docs_content = [doc.page_content for doc in state["documents"]]
    score = hallucination_grader.invoke({"documents": docs_content, "generation": state["generation"]})
    if score.binary_score == "yes":
        score = answer_grader.invoke({"question": state["question"], "generation": state["generation"]})
        if score.binary_score == "yes":
            return "useful"
    return "max_retries" if state["attempts"] >= 2 else "not_useful"

# Build workflow
workflow = StateGraph(GraphState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("web_search", web_search_node)
workflow.add_node("generate", generate_node)
workflow.add_conditional_edges(START, route_question_node, {"web_search": "web_search", "vectorstore": "retrieve"})
workflow.add_edge("retrieve", "generate")
workflow.add_edge("web_search", "generate")
workflow.add_conditional_edges("generate", grade_generation_node, {"useful": END, "not_useful": "web_search", "max_retries": END})
graph_app = workflow.compile()

async def run_workflow(question: str):
    """Execute the LangGraph workflow."""
    inputs = {"question": question, "documents": [], "generation": "", "attempts": 0}
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
    """Main RAG query endpoint."""
    try:
        result = await run_workflow(req.question)
        return {
            "question": req.question,
            "answer": result.get('generation', 'No answer generated'),
            "sources": [{"metadata": doc.metadata, "content": doc.page_content[:200]} for doc in result.get('documents', [])]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

