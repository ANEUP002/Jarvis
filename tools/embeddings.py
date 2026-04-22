# =========================
# EMBEDDING PROVIDERS
# =========================
# Real embedding models for semantic search

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _safe_notice(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="ignore").decode())


class OpenAIEmbeddings:
    """OpenAI Embeddings API"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = "text-embedding-3-small"
        self.dimension = 1536

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("OpenAI library required: pip install openai")

    def embed(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"OpenAI embedding error: {e}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [e.embedding for e in embeddings]
        except Exception as e:
            raise Exception(f"OpenAI batch embedding error: {e}")


class HuggingFaceEmbeddings:
    """Hugging Face Embeddings (local inference)"""

    _model_cache = {}

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        local_only = os.getenv("HF_EMBEDDINGS_LOCAL_ONLY", "true").lower() in ("1", "true", "yes")

        try:
            from sentence_transformers import SentenceTransformer
            cache_key = (model_name, local_only)
            if cache_key not in self._model_cache:
                self._model_cache[cache_key] = SentenceTransformer(model_name, local_files_only=local_only)
            self.model = self._model_cache[cache_key]
            if hasattr(self.model, "get_embedding_dimension"):
                self.dimension = self.model.get_embedding_dimension()
            else:
                self.dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise ImportError("sentence-transformers required: pip install sentence-transformers")
        except Exception as e:
            raise RuntimeError(f"Unable to load Hugging Face model '{model_name}': {e}")

    def embed(self, text: str) -> List[float]:
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        except Exception as e:
            raise Exception(f"Hugging Face embedding error: {e}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embeddings]
        except Exception as e:
            raise Exception(f"Hugging Face batch embedding error: {e}")


class GoogleEmbeddings:
    """Google embeddings API"""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_AI_API_KEY")
        self.dimension = 768

        if not self.api_key:
            raise ValueError("GOOGLE_AI_API_KEY not found in .env")

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai
        except ImportError:
            raise ImportError("google-generativeai required: pip install google-generativeai")

    def embed(self, text: str) -> List[float]:
        try:
            result = self.client.embed_content(
                model="models/embedding-001",
                content=text
            )
            return result["embedding"]
        except Exception as e:
            raise Exception(f"Google embedding error: {e}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(text) for text in texts]


def get_embedding_provider(provider: str = "huggingface"):
    """
    Get an embedding provider.

    Args:
        provider: "openai", "huggingface", or "google"

    Returns:
        Embedding provider instance or None
    """
    provider = provider.lower().strip()

    if provider == "openai":
        try:
            return OpenAIEmbeddings()
        except (ValueError, ImportError) as e:
            _safe_notice(f"OpenAI embeddings unavailable: {e}")
            return None

    if provider == "google":
        try:
            return GoogleEmbeddings()
        except (ValueError, ImportError, RuntimeError) as e:
            _safe_notice(f"Google embeddings unavailable: {e}")
            return None

    if provider == "huggingface":
        try:
            return HuggingFaceEmbeddings()
        except (ImportError, RuntimeError) as e:
            _safe_notice(f"Hugging Face embeddings unavailable: {e}")
            _safe_notice("Install with: pip install sentence-transformers and make sure the model can be downloaded or cached.")
            return None

    return None
