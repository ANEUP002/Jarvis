# =========================
# UPGRADED VECTOR DATABASE
# =========================
# Real embeddings with cosine similarity search

import hashlib
import json
import math
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any

from app.event_streaming import event_stream
from tools.base_tool import BaseTool
from tools.embeddings import get_embedding_provider

TFIDF_FALLBACK_PROVIDER = "tfidf_fallback"
TFIDF_FALLBACK_VERSION = 2
TFIDF_FALLBACK_DIMENSION = 256


class AdvancedVectorStore:
    """
    Advanced vector database with real embeddings.
    Supports OpenAI, Google, and Hugging Face embeddings.
    Falls back to a deterministic hashed sparse embedding if unavailable.
    """

    def __init__(self, db_dir: str = "vector_db_advanced", embedding_provider: str = "huggingface"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)
        self.metadata_file = self.db_dir / "metadata.json"
        self.embeddings_file = self.db_dir / "embeddings.json"

        self.requested_provider = embedding_provider
        self.embedding_provider = get_embedding_provider(embedding_provider)
        self.provider_name = embedding_provider if self.embedding_provider else TFIDF_FALLBACK_PROVIDER

        self.load_metadata()
        self.load_embeddings()
        self._migrate_legacy_fallback_embeddings()

    @property
    def fallback_active(self) -> bool:
        return self.provider_name == TFIDF_FALLBACK_PROVIDER

    def load_metadata(self):
        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}

    def save_metadata(self):
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

    def load_embeddings(self):
        if self.embeddings_file.exists():
            with open(self.embeddings_file, "r", encoding="utf-8") as f:
                self.embeddings = json.load(f)
        else:
            self.embeddings = {}

    def save_embeddings(self):
        with open(self.embeddings_file, "w", encoding="utf-8") as f:
            json.dump(self.embeddings, f)

    def store(self, key: str, text: str, metadata: Dict = None) -> bool:
        try:
            embedding, provider_used, version_used = self._embed_text(text)

            self.embeddings[key] = {
                "embedding": embedding,
                "provider": provider_used,
                "dimension": len(embedding),
                "version": version_used,
            }

            self.metadata[key] = {
                "text": text,
                "text_length": len(text),
                "tokens": len(self._tokenize(text)),
                "metadata": metadata or {},
                "provider": provider_used,
                "version": version_used,
            }

            self.save_embeddings()
            self.save_metadata()
            return True
        except Exception as e:
            print(f"[STORE ERROR] {e}")
            return False

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def _embed_text(self, text: str) -> Tuple[List[float], str, int]:
        if self.embedding_provider:
            try:
                return self.embedding_provider.embed(text), self.provider_name, 1
            except Exception as e:
                print(f"[EMBEDDING ERROR] {e}, using fallback embedding")

        return self._hashed_fallback_embed(text), TFIDF_FALLBACK_PROVIDER, TFIDF_FALLBACK_VERSION

    def _hashed_fallback_embed(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * TFIDF_FALLBACK_DIMENSION

        vector = [0.0] * TFIDF_FALLBACK_DIMENSION
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % TFIDF_FALLBACK_DIMENSION
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        scale = float(len(tokens))
        return [value / scale for value in vector]

    def _migrate_legacy_fallback_embeddings(self) -> None:
        updated = False
        for key, emb_data in self.embeddings.items():
            provider = emb_data.get("provider")
            version = emb_data.get("version")
            if provider != TFIDF_FALLBACK_PROVIDER or version == TFIDF_FALLBACK_VERSION:
                continue

            text = self.metadata.get(key, {}).get("text", "")
            new_embedding = self._hashed_fallback_embed(text)
            emb_data["embedding"] = new_embedding
            emb_data["dimension"] = len(new_embedding)
            emb_data["version"] = TFIDF_FALLBACK_VERSION

            if key in self.metadata:
                self.metadata[key]["version"] = TFIDF_FALLBACK_VERSION
                self.metadata[key]["provider"] = TFIDF_FALLBACK_PROVIDER
            updated = True

        if updated:
            self.save_embeddings()
            self.save_metadata()

    def search(self, query: str, top_k: int = 5, min_similarity: float = 0.0) -> List[Tuple[str, float, str]]:
        try:
            if not self.embeddings:
                return []

            query_emb, query_provider, query_version = self._embed_text(query)
            compatible_keys = self._compatible_keys(query_provider, query_version, len(query_emb))

            scores = []
            for key in compatible_keys:
                doc_emb = self.embeddings.get(key, {}).get("embedding", [])
                if not doc_emb:
                    continue

                similarity = self._cosine_similarity(query_emb, doc_emb)
                if similarity >= min_similarity:
                    text = self.metadata.get(key, {}).get("text", "")
                    scores.append((key, similarity, text))

            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]
        except Exception as e:
            print(f"[SEARCH ERROR] {e}")
            return []

    def _compatible_keys(self, provider: str, version: int, dimension: int) -> List[str]:
        compatible = []
        for key, emb_data in self.embeddings.items():
            if emb_data.get("provider") != provider:
                continue
            if emb_data.get("dimension") != dimension:
                continue
            if provider == TFIDF_FALLBACK_PROVIDER and emb_data.get("version") != version:
                continue
            compatible.append(key)
        return compatible

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(x ** 2 for x in vec1))
        norm2 = math.sqrt(sum(x ** 2 for x in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def delete(self, key: str) -> bool:
        if key in self.embeddings:
            del self.embeddings[key]
        if key in self.metadata:
            del self.metadata[key]

        self.save_embeddings()
        self.save_metadata()
        return True

    def list_entries(self) -> List[Dict[str, Any]]:
        entries = []
        for key, meta in self.metadata.items():
            emb_data = self.embeddings.get(key, {})
            entries.append({
                "key": key,
                "text_length": meta.get("text_length", 0),
                "tokens": meta.get("tokens", 0),
                "provider": emb_data.get("provider", "unknown"),
                "dimension": emb_data.get("dimension", 0),
                "version": emb_data.get("version"),
            })
        return entries


class StoreVectorAdvancedTool(BaseTool):
    name = "store_vector_advanced"
    description = "Store text with real embeddings (OpenAI, Google, HuggingFace)"

    def execute(
        self,
        key: str,
        text: str,
        metadata: Dict = None,
        db_dir: str = "vector_db_advanced",
        embedding_provider: str = "huggingface",
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_store_started",
                    "provider": embedding_provider,
                    "key": key,
                },
            )
            vector_store = AdvancedVectorStore(db_dir, embedding_provider)
            success = vector_store.store(key, text, metadata)
            entry = vector_store.embeddings.get(key, {})
            provider = entry.get("provider", vector_store.provider_name)
            fallback_used = provider == TFIDF_FALLBACK_PROVIDER

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_store_completed",
                    "provider": provider,
                    "fallback_used": fallback_used,
                    "key": key,
                },
                level="warning" if fallback_used else "info",
            )

            return {
                "success": success,
                "result": {
                    "key": key,
                    "stored": success,
                    "provider": provider,
                    "dimension": entry.get("dimension", 0),
                    "version": entry.get("version"),
                    "fallback_used": fallback_used,
                },
                "error": None if success else "Failed to store",
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class SemanticSearchAdvancedTool(BaseTool):
    name = "vector_search_advanced"
    description = "Search with real embeddings"

    def execute(
        self,
        query: str,
        top_k: int = 5,
        db_dir: str = "vector_db_advanced",
        embedding_provider: str = "huggingface",
        min_similarity: float = 0.0,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_search_started",
                    "provider": embedding_provider,
                    "query": query,
                    "top_k": top_k,
                },
            )
            vector_store = AdvancedVectorStore(db_dir, embedding_provider)
            results = vector_store.search(query, top_k, min_similarity)

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_search_completed",
                    "provider": vector_store.provider_name,
                    "fallback_used": vector_store.fallback_active,
                    "results_count": len(results),
                },
                level="warning" if vector_store.fallback_active else "info",
            )

            formatted_results = [
                {
                    "key": key,
                    "similarity": round(score, 4),
                    "text_preview": text[:200] + "..." if len(text) > 200 else text,
                }
                for key, score, text in results
            ]

            return {
                "success": True,
                "result": {
                    "query": query,
                    "embedding_provider": vector_store.provider_name,
                    "fallback_used": vector_store.fallback_active,
                    "results": formatted_results,
                    "count": len(formatted_results),
                },
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ListVectorsAdvancedTool(BaseTool):
    name = "list_vectors_advanced"
    description = "List all stored vector entries with metadata"

    def execute(
        self,
        db_dir: str = "vector_db_advanced",
        embedding_provider: str = "huggingface",
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_list_started",
                    "provider": embedding_provider,
                    "db_dir": db_dir,
                },
            )
            vector_store = AdvancedVectorStore(db_dir, embedding_provider)
            entries = vector_store.list_entries()
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "vector_list_completed",
                    "provider": vector_store.provider_name,
                    "fallback_used": vector_store.fallback_active,
                    "count": len(entries),
                },
                level="warning" if vector_store.fallback_active else "info",
            )

            return {
                "success": True,
                "result": {
                    "entries": entries,
                    "count": len(entries),
                    "embedding_provider": vector_store.provider_name,
                    "fallback_used": vector_store.fallback_active,
                },
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
