"""
Service Clients for RAG API

HTTP clients for communicating with other microservices
"""

import logging
import os
from typing import Dict, List, Optional, Any

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import redis

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Client for Embedding Service"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:8001")
        self.timeout = 120.0  # Embedding can be slow

    async def embed_documents(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """Generate embeddings for documents"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/embed/documents",
                json={"texts": texts, "batch_size": batch_size}
            )
            response.raise_for_status()
            return response.json()["embeddings"]

    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/embed/query",
                json={"text": text}
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def health_check(self) -> bool:
        """Check if embedding service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class LLMClient:
    """Client for LLM Gateway Service"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8002")
        self.timeout = 180.0  # LLM generation can be slow
        self._model_name = None  # 캐시된 모델 이름

    @property
    def model_name(self) -> str:
        """현재 사용 중인 LLM 모델 이름 반환"""
        return self._model_name or "LLM"

    async def get_model_info(self) -> dict:
        """LLM 게이트웨이에서 모델 정보 조회"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/info")
                if response.status_code == 200:
                    info = response.json()
                    self._model_name = info.get("model", "LLM")
                    return info
        except Exception as e:
            logger.warning(f"모델 정보 조회 실패: {e}")
        return {"model": "LLM"}

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate LLM response"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/llm/generate",
                json={
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json()["content"]

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """Stream LLM response"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/llm/stream",
                json={
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        content = line[5:].strip()
                        if content and content != "[DONE]" and not content.startswith("[ERROR]"):
                            yield content

    async def generate_stream(self, prompt: str):
        """Simple streaming generation from a prompt string"""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.stream(messages):
            yield chunk

    async def health_check(self) -> bool:
        """Check if LLM gateway is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class QdrantService:
    """Qdrant Vector Store Service"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = "documents",
        embedding_dim: int = 1024
    ):
        self.host = host or os.getenv("QDRANT_HOST", "qdrant")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self._client = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(host=self.host, port=self.port)
        return self._client

    def ensure_collection(self, collection_name: str = None):
        """Ensure collection exists, create if not"""
        name = collection_name or self.collection_name
        try:
            self.client.get_collection(name)
        except Exception:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created collection: {name}")

    def upsert_vectors(
        self,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        collection_name: str = None
    ):
        """Insert or update vectors"""
        name = collection_name or self.collection_name
        points = [
            PointStruct(id=idx, vector=vec, payload=payload)
            for idx, (vec, payload) in enumerate(zip(vectors, payloads))
        ]
        # Use string IDs with hash
        points = []
        for id_str, vec, payload in zip(ids, vectors, payloads):
            points.append(PointStruct(
                id=abs(hash(id_str)) % (10 ** 16),  # Convert string to numeric ID
                vector=vec,
                payload={**payload, "doc_id": id_str}
            ))

        self.client.upsert(collection_name=name, points=points)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        collection_name: str = None,
        filter_conditions: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors"""
        name = collection_name or self.collection_name

        # Build filter if provided
        query_filter = None
        if filter_conditions:
            conditions = []
            for key, value in filter_conditions.items():
                conditions.append(FieldCondition(
                    key=key,
                    match=MatchValue(value=value)
                ))
            if conditions:
                query_filter = Filter(must=conditions)

        results = self.client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter
        )

        return [
            {
                "id": hit.payload.get("doc_id", str(hit.id)),
                "score": hit.score,
                "payload": hit.payload
            }
            for hit in results
        ]

    def delete_by_filter(
        self,
        filter_key: str,
        filter_value: Any,
        collection_name: str = None
    ) -> int:
        """Delete vectors by filter"""
        name = collection_name or self.collection_name

        # Get count before delete
        count_before = self.client.count(collection_name=name).count

        self.client.delete(
            collection_name=name,
            points_selector=Filter(
                must=[FieldCondition(key=filter_key, match=MatchValue(value=filter_value))]
            )
        )

        count_after = self.client.count(collection_name=name).count
        return count_before - count_after

    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get collection information"""
        name = collection_name or self.collection_name
        try:
            info = self.client.get_collection(name)
            return {
                "name": name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count
            }
        except Exception as e:
            return {"name": name, "error": str(e)}

    def list_collections(self) -> List[str]:
        """List all collections"""
        collections = self.client.get_collections()
        return [c.name for c in collections.collections]


class RedisService:
    """Redis Cache and Metadata Service"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        db: int = 0
    ):
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db
        self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True
            )
        return self._client

    def ping(self) -> bool:
        """Check Redis connection"""
        try:
            return self.client.ping()
        except Exception:
            return False

    # Document metadata
    def set_document_meta(self, doc_id: str, metadata: Dict[str, Any], ttl: int = None):
        """Store document metadata"""
        key = f"doc:{doc_id}"
        self.client.hset(key, mapping={k: str(v) for k, v in metadata.items()})
        if ttl:
            self.client.expire(key, ttl)

    def get_document_meta(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata"""
        key = f"doc:{doc_id}"
        data = self.client.hgetall(key)
        return data if data else None

    def delete_document_meta(self, doc_id: str):
        """Delete document metadata"""
        self.client.delete(f"doc:{doc_id}")

    # Categories
    def add_category(self, category_id: str, name: str, description: str = ""):
        """Add a category"""
        key = f"category:{category_id}"
        self.client.hset(key, mapping={
            "name": name,
            "description": description,
            "doc_count": "0"
        })

    def get_category(self, category_id: str) -> Optional[Dict[str, str]]:
        """Get category info"""
        return self.client.hgetall(f"category:{category_id}")

    def list_categories(self) -> List[Dict[str, str]]:
        """List all categories"""
        keys = self.client.keys("category:*")
        categories = []
        for key in keys:
            data = self.client.hgetall(key)
            data["id"] = key.replace("category:", "")
            categories.append(data)
        return categories

    def increment_category_count(self, category_id: str, delta: int = 1):
        """Increment document count for category"""
        self.client.hincrby(f"category:{category_id}", "doc_count", delta)

    # Caching
    def cache_get(self, key: str) -> Optional[str]:
        """Get cached value"""
        return self.client.get(f"cache:{key}")

    def cache_set(self, key: str, value: str, ttl: int = 3600):
        """Set cached value"""
        self.client.setex(f"cache:{key}", ttl, value)

    # Task queue (simple implementation)
    def enqueue_task(self, queue_name: str, task_data: str):
        """Add task to queue"""
        self.client.rpush(f"queue:{queue_name}", task_data)

    def dequeue_task(self, queue_name: str, timeout: int = 0) -> Optional[str]:
        """Get task from queue"""
        result = self.client.blpop(f"queue:{queue_name}", timeout=timeout)
        return result[1] if result else None
