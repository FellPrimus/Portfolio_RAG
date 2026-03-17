"""
RAG Service - Core RAG Pipeline

Handles question answering with retrieval augmented generation
"""

import logging
import time
import hashlib
from typing import Dict, List, Optional, Any, AsyncIterator

from ..utils.clients import EmbeddingClient, LLMClient, QdrantService, RedisService

logger = logging.getLogger(__name__)

# RAG Prompt Templates
SYSTEM_PROMPT = """당신은 네이버 클라우드 플랫폼(NCP)의 AI 기술 지원 전문가입니다.

주요 역할:
1. 사용자의 기술적 질문에 정확하고 명확하게 답변합니다.
2. 제공된 문서(Context)를 기반으로 답변을 생성합니다.
3. 문서에 없는 내용은 추측하지 않고 "문서에서 해당 정보를 찾을 수 없습니다"라고 답변합니다.

답변 형식:
- 명확하고 구체적으로 답변합니다.
- 필요시 단계별로 설명합니다.
- 코드 예제가 필요하면 제공합니다.
- 출처를 언급합니다."""

USER_PROMPT_TEMPLATE = """다음 문서를 참고하여 질문에 답변해주세요.

## 참고 문서
{context}

## 질문
{question}

## 답변"""


class RAGService:
    """
    RAG Pipeline Service

    Workflow:
    1. Embed query
    2. Search similar documents in Qdrant
    3. Generate answer using LLM
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        llm_client: LLMClient,
        qdrant_service: QdrantService,
        redis_service: RedisService,
        retrieval_k: int = 5,
        min_quality_score: float = 0.6
    ):
        self.embedding_client = embedding_client
        self.llm_client = llm_client
        self.qdrant_service = qdrant_service
        self.redis_service = redis_service
        self.retrieval_k = retrieval_k
        self.min_quality_score = min_quality_score

    def _get_cache_key(self, question: str, collection: str) -> str:
        """Generate cache key for question"""
        content = f"{question}:{collection}"
        return hashlib.md5(content.encode()).hexdigest()

    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents into context string"""
        context_parts = []
        for i, doc in enumerate(documents, 1):
            content = doc["payload"].get("content", "")
            source = doc["payload"].get("source", "unknown")
            context_parts.append(f"[문서 {i}] (출처: {source})\n{content}")
        return "\n\n---\n\n".join(context_parts)

    async def query(
        self,
        question: str,
        collection: str = "documents",
        top_k: int = None,
        filter_conditions: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process RAG query

        Args:
            question: User's question
            collection: Qdrant collection name
            top_k: Number of documents to retrieve
            filter_conditions: Optional filter conditions

        Returns:
            Dict with answer, sources, quality_score, processing_time
        """
        start_time = time.time()
        k = top_k or self.retrieval_k

        # Check cache
        cache_key = self._get_cache_key(question, collection)
        cached = self.redis_service.cache_get(cache_key)
        if cached:
            import json
            logger.info(f"Cache hit for question: {question[:50]}...")
            result = json.loads(cached)
            result["processing_time"] = time.time() - start_time
            return result

        # Step 1: Embed query
        logger.info(f"Embedding query: {question[:50]}...")
        query_vector = await self.embedding_client.embed_query(question)

        # Step 2: Search documents
        logger.info(f"Searching in collection: {collection}, top_k: {k}")
        search_results = self.qdrant_service.search(
            query_vector=query_vector,
            top_k=k,
            collection_name=collection,
            filter_conditions=filter_conditions
        )

        if not search_results:
            return {
                "answer": "관련 문서를 찾을 수 없습니다. 다른 질문을 시도해 주세요.",
                "sources": [],
                "quality_score": 0.0,
                "processing_time": time.time() - start_time
            }

        # Step 3: Format context
        context = self._format_context(search_results)

        # Step 4: Generate answer
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                context=context,
                question=question
            )}
        ]

        logger.info("Generating answer...")
        answer = await self.llm_client.generate(messages)

        # Format sources
        sources = [
            {
                "id": doc["id"],
                "content": doc["payload"].get("content", "")[:500],
                "metadata": {
                    k: v for k, v in doc["payload"].items()
                    if k not in ["content", "embedding"]
                },
                "score": doc["score"]
            }
            for doc in search_results
        ]

        # Calculate quality score (simple heuristic based on retrieval scores)
        avg_score = sum(doc["score"] for doc in search_results) / len(search_results)
        quality_score = min(avg_score * 1.2, 1.0)  # Normalize to 0-1

        result = {
            "answer": answer,
            "sources": sources,
            "quality_score": quality_score,
            "processing_time": time.time() - start_time
        }

        # Cache result (1 hour TTL)
        import json
        self.redis_service.cache_set(cache_key, json.dumps(result), ttl=3600)

        return result

    async def query_stream(
        self,
        question: str,
        collection: str = "documents",
        top_k: int = None,
        filter_conditions: Dict[str, Any] = None
    ) -> AsyncIterator[str]:
        """
        Stream RAG query response

        Yields answer chunks as they are generated
        """
        k = top_k or self.retrieval_k

        # Step 1: Embed query
        query_vector = await self.embedding_client.embed_query(question)

        # Step 2: Search documents
        search_results = self.qdrant_service.search(
            query_vector=query_vector,
            top_k=k,
            collection_name=collection,
            filter_conditions=filter_conditions
        )

        if not search_results:
            yield "관련 문서를 찾을 수 없습니다. 다른 질문을 시도해 주세요."
            return

        # Step 3: Format context
        context = self._format_context(search_results)

        # Step 4: Stream answer
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                context=context,
                question=question
            )}
        ]

        async for chunk in self.llm_client.stream(messages):
            yield chunk
