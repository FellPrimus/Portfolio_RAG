"""
Semantic Chunking 모듈

문장 유사도 기반 지능형 청킹
"""

from typing import List, Optional
import numpy as np
from langchain_core.documents import Document
import re


class SemanticChunker:
    """
    의미론적 청킹

    문장 간 임베딩 유사도가 급격히 변하는 지점에서 청크 분할
    """

    def __init__(
        self,
        embedding_function,
        breakpoint_threshold_type: str = "percentile",
        breakpoint_threshold_amount: float = 95,
        min_chunk_size: int = None,
        max_chunk_size: int = None
    ):
        """
        SemanticChunker 초기화

        Args:
            embedding_function: 임베딩 함수 (QwenEmbeddings 등)
            breakpoint_threshold_type: 분할 임계값 타입
            breakpoint_threshold_amount: 분할 임계값
            min_chunk_size: 최소 청크 크기 (문자, None이면 설정에서 가져옴)
            max_chunk_size: 최대 청크 크기 (문자, None이면 설정에서 가져옴)
        """
        # Clean Code: 설정에서 청킹 값 가져오기
        from src.config.settings import get_settings
        settings = get_settings()

        self.embedding_function = embedding_function
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.breakpoint_threshold_amount = breakpoint_threshold_amount
        self.min_chunk_size = min_chunk_size if min_chunk_size is not None else settings.chunking.min_chunk_size
        self.max_chunk_size = max_chunk_size if max_chunk_size is not None else settings.chunking.max_chunk_size

    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        sentences = re.split(r'(?<=[.!?])\s+|\n\n+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _calculate_distances(self, embeddings: List[List[float]]) -> List[float]:
        """연속된 임베딩 간의 코사인 거리 계산"""
        distances = []
        for i in range(len(embeddings) - 1):
            emb1 = np.array(embeddings[i])
            emb2 = np.array(embeddings[i + 1])

            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            distance = 1 - similarity
            distances.append(distance)

        return distances

    def _find_breakpoints(self, distances: List[float]) -> List[int]:
        """분할 지점 찾기"""
        if not distances:
            return []

        distances_array = np.array(distances)

        if self.breakpoint_threshold_type == "percentile":
            threshold = np.percentile(distances_array, self.breakpoint_threshold_amount)
        else:
            threshold = np.percentile(distances_array, 95)

        breakpoints = [i + 1 for i, d in enumerate(distances) if d >= threshold]
        return breakpoints

    def chunk_text(self, text: str, metadata: Optional[dict] = None) -> List[Document]:
        """텍스트를 의미론적으로 청킹"""
        metadata = metadata or {}

        sentences = self._split_into_sentences(text)

        if len(sentences) <= 1:
            return [Document(page_content=text, metadata={**metadata, "chunk_id": 0})]

        print(f"   🔄 {len(sentences)}개 문장 임베딩 중...")
        embeddings = self.embedding_function.embed_documents(sentences)

        distances = self._calculate_distances(embeddings)
        breakpoints = self._find_breakpoints(distances)

        chunks = []
        start_idx = 0

        for bp in breakpoints + [len(sentences)]:
            chunk_sentences = sentences[start_idx:bp]
            chunk_text = " ".join(chunk_sentences)

            if len(chunk_text) < self.min_chunk_size and chunks:
                prev_chunk = chunks.pop()
                chunk_text = prev_chunk.page_content + " " + chunk_text

            if len(chunk_text) > self.max_chunk_size:
                mid = len(chunk_text) // 2
                split_pos = chunk_text.rfind(" ", 0, mid)
                if split_pos == -1:
                    split_pos = mid

                chunks.append(Document(
                    page_content=chunk_text[:split_pos].strip(),
                    metadata={**metadata, "chunk_id": len(chunks)}
                ))
                chunks.append(Document(
                    page_content=chunk_text[split_pos:].strip(),
                    metadata={**metadata, "chunk_id": len(chunks)}
                ))
            else:
                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={**metadata, "chunk_id": len(chunks)}
                ))

            start_idx = bp

        print(f"   ✓ {len(sentences)}개 문장 → {len(chunks)}개 청크")
        return chunks

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """문서 리스트 청킹"""
        all_chunks = []

        for doc in documents:
            chunks = self.chunk_text(doc.page_content, doc.metadata.copy())
            all_chunks.extend(chunks)

        for i, chunk in enumerate(all_chunks):
            chunk.metadata["chunk_id"] = i

        return all_chunks
