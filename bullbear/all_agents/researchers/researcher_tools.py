from typing import List, Dict, Any
import requests
import os


# ==============================
#  TOOL 1: RETRIEVE FROM PATHWAY
# ==============================

def retrieve_from_pathway(question: str) -> List[Dict[str, Any]]:
    """
    Retrieve documents from Pathway RAG API.
    Returns a list of JSON-serializable dictionaries.
    """
    rag_url = os.getenv("RAG_API_URL", "http://localhost:8000")
    try:
        r = requests.post(f"{rag_url}/query", json={"question": question}, timeout=30)
        r.raise_for_status()
        result = r.json()
        docs = []
        for src in result.get("sources", []):
            # Return plain dicts (JSON-serializable) instead of Document objects
            docs.append({
                "content": src.get("content", ""),
                "metadata": src.get("metadata", {})
            })
        return docs
    except Exception as e:
        print(f"RAG error: {e}")
        return []



# def retrieve_from_pathway(query: str, k: int = 5, port=5091):
#     """
#     Retrieve clean and minimal documents from Pathway.
#     Filters out unwanted contextualized data and metadata.
#     """
#     # url = f"http://127.0.0.1:{str(port)}/v1/retrieve" old code
#     url = f"http://host.docker.internal:{str(port)}/v1/retrieve"

#     try:
#         response = requests.post(
#             url,
#             json={"query": query, "k": k},
#             timeout=20
#         )
#         response.raise_for_status()
#         raw = response.json()

#         cleaned_docs = []

#         for item in raw:
#             text = item.get("text", "")

#             # Extract only the original content
#             if "Original_Content:" in text:
#                 content = text.split("Original_Content:")[1].split("\nContextualized_Context:")[0].strip()
#             else:
#                 content = text.strip()

#             cleaned_docs.append({
#                 "content": content,
#                 "source": item["metadata"].get("path", ""),
#                 "filename": item["metadata"].get("filename", ""),
#                 "score": round(item.get("dist", 0), 4)
#             })

#         return cleaned_docs

#     except Exception as e:
#         print(f"❌ Retrieval error: {e}")
#         return []


# ======================
#  TOOL 2: add()
# ======================
def add(a: float, b: float):
    """Return the sum of two numbers."""
    return a + b


# ==============================
#  TOOLS LIST (FOR LLM TOOLCALL)
# ==============================
TOOLS_ = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_from_pathway",
            "description": "Retrieve relevant documents from the Pathway vector database using semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or search query to look up in the vector database."
                    },
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Adds two numbers and returns the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        }
    }
]
