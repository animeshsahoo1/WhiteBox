"""Tools for Bull-Bear Researchers."""
from typing import List, Dict, Any
import requests
import os


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
            docs.append({
                "content": src.get("content", ""),
                "metadata": src.get("metadata", {})
            })
        return docs
    except Exception as e:
        print(f"RAG error: {e}")
        return []
