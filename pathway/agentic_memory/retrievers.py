"""ChromaDB Retriever for Agentic Memory System."""
import json
from pathlib import Path
from typing import Dict, List, Optional
import ast

import chromadb
from chromadb.config import Settings


class ChromaRetriever:
    """Vector database retrieval using ChromaDB with default embeddings."""

    def __init__(
        self, 
        collection_name: str = "memories", 
        model_name: str = None  # Kept for compatibility, but ignored
    ):
        """Initialize ChromaDB retriever with default embeddings.

        Args:
            collection_name: Name of the ChromaDB collection
            model_name: Ignored - uses ChromaDB default embeddings
        """
        self.client = chromadb.Client(Settings(allow_reset=True))
        # Use ChromaDB's default embedding function (no external dependencies)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_document(self, document: str, metadata: Dict, doc_id: str):
        """Add a document to ChromaDB."""
        processed_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                processed_metadata[key] = json.dumps(value)
            elif isinstance(value, dict):
                processed_metadata[key] = json.dumps(value)
            else:
                processed_metadata[key] = str(value)

        self.collection.add(
            documents=[document], metadatas=[processed_metadata], ids=[doc_id]
        )

    def delete_document(self, doc_id: str):
        """Delete a document from ChromaDB."""
        self.collection.delete(ids=[doc_id])

    def search(self, query: str, k: int = 5):
        """Search for similar documents."""
        results = self.collection.query(query_texts=[query], n_results=k)
        
        if (results is not None) and (results.get("metadatas", [])):
            results["metadatas"] = self._convert_metadata_types(results["metadatas"])
        
        return results

    def _convert_metadata_types(self, metadatas: List[List[Dict]]) -> List[List[Dict]]:
        """Convert string metadata back to original types."""
        for query_metadatas in metadatas:
            if isinstance(query_metadatas, List):
                for metadata_dict in query_metadatas:
                    if isinstance(metadata_dict, Dict):
                        self._convert_metadata_dict(metadata_dict)
        return metadatas

    def _convert_metadata_dict(self, metadata: Dict) -> None:
        """Convert metadata values from strings to appropriate types in-place."""
        for key, value in metadata.items():
            if not isinstance(value, str):
                continue
            try:
                metadata[key] = ast.literal_eval(value)
            except Exception:
                pass