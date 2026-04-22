# =========================
# VECTOR DATABASE TOOLS
# =========================
# Semantic search and embedding-based storage

import os
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
from app.event_streaming import event_stream
from tools.base_tool import BaseTool


class VectorStore:
    """
    Simple vector store using TF-IDF similarity.
    Can be upgraded to use real embeddings (OpenAI, HuggingFace, etc.)
    """
    
    def __init__(self, db_dir: str = "vector_db"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)
        self.metadata_file = self.db_dir / "metadata.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Load metadata from disk"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def save_metadata(self):
        """Save metadata to disk"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        return text.lower().split()
    
    def _compute_tfidf(self, text: str, all_docs: List[str]) -> Dict[str, float]:
        """Compute TF-IDF scores"""
        tokens = self._tokenize(text)
        
        # Term frequency
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        for token in tf:
            tf[token] /= len(tokens) if tokens else 1
        
        # Inverse document frequency
        idf = {}
        for token in tf:
            doc_count = sum(1 for doc in all_docs if token in self._tokenize(doc))
            idf[token] = math.log(len(all_docs) / (doc_count + 1))
        
        # TF-IDF
        tfidf = {}
        for token in tf:
            tfidf[token] = tf[token] * idf[token]
        
        return tfidf
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Compute cosine similarity between two vectors"""
        all_keys = set(vec1.keys()) | set(vec2.keys())
        
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
        
        norm1 = math.sqrt(sum(v**2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v**2 for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def store(self, key: str, text: str, metadata: Dict = None) -> bool:
        """Store text in vector database"""
        try:
            vector_file = self.db_dir / f"{key}.json"
            
            # Store document
            doc_data = {
                "text": text,
                "key": key,
                "metadata": metadata or {}
            }
            
            with open(vector_file, 'w') as f:
                json.dump(doc_data, f, indent=2)
            
            # Update metadata
            self.metadata[key] = {
                "text_length": len(text),
                "tokens": len(self._tokenize(text)),
                "metadata": metadata or {}
            }
            self.save_metadata()
            
            return True
        except Exception:
            return False
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, str]]:
        """
        Search similar documents using TF-IDF.
        
        Returns:
            List of (key, similarity_score, text)
        """
        try:
            # Get all documents
            all_docs = []
            doc_map = {}
            
            for json_file in self.db_dir.glob("*.json"):
                if json_file.name == "metadata.json":
                    continue
                
                with open(json_file, 'r') as f:
                    doc = json.load(f)
                    text = doc.get("text", "")
                    key = doc.get("key", json_file.stem)
                    all_docs.append(text)
                    doc_map[len(all_docs) - 1] = (key, text)
            
            if not all_docs:
                return []
            
            # Compute query TF-IDF
            query_tfidf = self._compute_tfidf(query, all_docs)
            
            # Compute similarity scores
            scores = []
            for idx, (key, text) in doc_map.items():
                doc_tfidf = self._compute_tfidf(text, all_docs)
                similarity = self._cosine_similarity(query_tfidf, doc_tfidf)
                scores.append((key, similarity, text))
            
            # Sort by similarity and return top-k
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]
        
        except Exception as e:
            print(f"[VECTOR DB ERROR] {e}")
            return []


class StoreVectorTool(BaseTool):
    """Store text in vector database"""
    
    name = "store_vector"
    description = "Store text in vector database for semantic search"
    
    def execute(self, key: str, text: str, metadata: Dict = None, db_dir: str = "vector_db", **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "vector_store_started", "key": key, "db_dir": db_dir},
            )
            vector_store = VectorStore(db_dir)
            success = vector_store.store(key, text, metadata)
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_store_completed" if success else "vector_store_failed",
                    "key": key,
                    "db_dir": db_dir,
                },
                level="info" if success else "warning",
            )
            
            return {
                "success": success,
                "result": {"key": key, "stored": success},
                "error": None if success else "Failed to store"
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class SemanticSearchVectorTool(BaseTool):
    """Search vector database using semantic similarity"""
    
    name = "vector_search"
    description = "Search vector database using semantic similarity (TF-IDF)"
    
    def execute(self, query: str, top_k: int = 5, db_dir: str = "vector_db", **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "vector_search_started", "query": query, "top_k": top_k},
            )
            vector_store = VectorStore(db_dir)
            results = vector_store.search(query, top_k)
            
            formatted_results = [
                {
                    "key": key,
                    "similarity": round(score, 4),
                    "text_preview": text[:200] + "..." if len(text) > 200 else text
                }
                for key, score, text in results
            ]
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "vector_search_completed", "query": query, "results_count": len(formatted_results)},
            )
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": formatted_results,
                    "count": len(formatted_results)
                },
                "error": None
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class DeleteVectorTool(BaseTool):
    """Delete entry from vector database"""
    
    name = "delete_vector"
    description = "Delete entry from vector database"
    
    def execute(self, key: str, db_dir: str = "vector_db", **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "vector_delete_started", "key": key, "db_dir": db_dir},
            )
            vector_store = VectorStore(db_dir)
            db_path = vector_store.db_dir / f"{key}.json"
            
            if db_path.exists():
                db_path.unlink()
                
                # Update metadata
                if key in vector_store.metadata:
                    del vector_store.metadata[key]
                    vector_store.save_metadata()
                
                event_stream.emit(
                    "tool_progress",
                    {"tool_name": self.name, "stage": "vector_delete_completed", "key": key, "db_dir": db_dir},
                )
                return {
                    "success": True,
                    "result": {"key": key, "deleted": True},
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Key not found: {key}"
                }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ListVectorsTool(BaseTool):
    """List all entries in vector database"""
    
    name = "list_vectors"
    description = "List all entries in vector database"
    
    def execute(self, db_dir: str = "vector_db", **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "vector_list_started", "db_dir": db_dir},
            )
            vector_store = VectorStore(db_dir)
            
            entries = []
            for key, meta in vector_store.metadata.items():
                entries.append({
                    "key": key,
                    "text_length": meta.get("text_length", 0),
                    "tokens": meta.get("tokens", 0)
                })
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "vector_list_completed", "db_dir": db_dir, "count": len(entries)},
            )
            return {
                "success": True,
                "result": {"entries": entries, "count": len(entries)},
                "error": None
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
