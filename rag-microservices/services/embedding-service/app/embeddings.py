"""
E5 Embedding Model Wrapper for Microservice

Based on multilingual-e5-large model (1024 dimensions)
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class E5EmbeddingModel:
    """
    E5 Embedding Model Singleton

    Uses "query:" prefix for search queries and "passage:" for documents
    """

    _instance: Optional["E5EmbeddingModel"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        device: str = "cpu",
        cache_dir: str = "/model-cache"
    ):
        if self._initialized:
            return

        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir
        self._model = None
        self._dimension = None
        self._initialized = True

    def load_model(self):
        """Load the model (lazy initialization)"""
        if self._model is not None:
            return

        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading E5 embedding model: {self.model_name}")

        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
            cache_folder=self.cache_dir
        )

        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"E5 model loaded - dimension: {self._dimension}, device: {self.device}")

    def embed_documents(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for documents (passage: prefix)
        """
        if not texts:
            return []

        self.load_model()

        # Add "passage:" prefix
        prefixed_texts = [f"passage: {text}" for text in texts]

        embeddings = self._model.encode(
            prefixed_texts,
            normalize_embeddings=normalize,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 10
        )

        return embeddings.tolist()

    def embed_query(self, text: str, normalize: bool = True) -> List[float]:
        """
        Generate embedding for search query (query: prefix)
        """
        self.load_model()

        # Add "query:" prefix
        prefixed_text = f"query: {text}"

        embedding = self._model.encode(
            prefixed_text,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )

        return embedding.tolist()

    @property
    def dimension(self) -> int:
        """Return embedding dimension"""
        self.load_model()
        return self._dimension

    def is_ready(self) -> bool:
        """Check if model is loaded and ready"""
        return self._model is not None


# Global instance
embedding_model = E5EmbeddingModel()
