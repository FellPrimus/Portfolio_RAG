"""
문서 검색 노드

Hybrid Search 기반 문서 검색을 담당합니다.
"""
from __future__ import annotations

import os
from typing import Optional

from src.graph.state import QualityRAGState


class DocumentRetrieverNode:
    """문서 검색 노드 (Hybrid Search)"""

    def __init__(
        self,
        vectorstore,
        hybrid_searcher=None,
        doc_service=None,
        retrieval_k: int = 5
    ):
        """
        Args:
            vectorstore: 벡터스토어 인스턴스
            hybrid_searcher: HybridSearcher 인스턴스 (선택)
            doc_service: DocumentService 인스턴스 (다중 컬렉션용)
            retrieval_k: 기본 검색 문서 수
        """
        self.vectorstore = vectorstore
        self.hybrid_searcher = hybrid_searcher
        self.doc_service = doc_service
        self.default_retrieval_k = retrieval_k

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        Hybrid Search 문서 검색 실행

        - 다중 쿼리 검색 (설정된 경우)
        - Hybrid Search (BM25 + Vector)
        - 다중 컬렉션 검색
        """
        print("[2/7] Searching documents (Hybrid Search)...")

        if state.get('error'):
            return state

        try:
            retrieval_config = state.get('retrieval_config', {})
            search_queries = state.get('search_queries', [state['question']])
            retrieval_k = retrieval_config.get('retrieval_k', self.default_retrieval_k)

            all_docs = []

            for i, query in enumerate(search_queries):
                if len(search_queries) > 1:
                    print(f"   Query {i+1}/{len(search_queries)}: {query[:50]}...")

                docs = self._search_single_query(
                    query, retrieval_k, retrieval_config, state
                )
                all_docs.extend(docs)

            # 중복 제거
            unique_docs = self._deduplicate_docs(all_docs)
            state['retrieved_docs'] = unique_docs[:retrieval_k * 2]
            state['num_docs_retrieved'] = len(state['retrieved_docs'])

            # 출처 추출
            sources = list(set([
                os.path.basename(doc.metadata.get('source', 'unknown'))
                for doc in state['retrieved_docs']
            ]))
            state['sources_used'] = sources

            print(f"   Found {len(state['retrieved_docs'])} docs ({len(sources)} sources)")
            state['steps'].append(
                f"Document search complete ({state.get('retrieval_method', 'unknown')}, "
                f"{len(state['retrieved_docs'])} docs)"
            )

            if len(state['retrieved_docs']) == 0:
                state['warnings'].append("No documents found. Answer quality may be limited.")

        except Exception as e:
            import traceback
            print(f"   Search error: {e}")
            print(traceback.format_exc())
            state['error'] = f"Document search failed: {str(e)}"
            state['steps'].append("Error: Search failed")

        return state

    def _search_single_query(
        self,
        query: str,
        retrieval_k: int,
        retrieval_config: dict,
        state: 'QualityRAGState'
    ) -> list:
        """단일 쿼리 검색"""
        use_hybrid = retrieval_config.get('use_hybrid', True)
        has_multi_collection = self._has_multi_collection()

        # Hybrid Search 시도
        if self.hybrid_searcher and use_hybrid:
            try:
                if has_multi_collection:
                    docs = self.doc_service.multi_collection_search(query, k=retrieval_k)
                    state['retrieval_method'] = "multi_collection_hybrid"
                else:
                    results = self.hybrid_searcher.search(
                        query,
                        k=retrieval_k,
                        semantic_k=retrieval_k * 2,
                        bm25_k=retrieval_k * 2
                    )
                    docs = [doc for doc, score in results]
                    state['retrieval_method'] = "hybrid_search"

                state['hybrid_search_used'] = True
                return docs

            except Exception as e:
                print(f"   Hybrid search failed, falling back to vector search: {e}")

        # 폴백: 순수 벡터 검색
        return self._fallback_vector_search(query, retrieval_k, state)

    def _fallback_vector_search(
        self,
        query: str,
        retrieval_k: int,
        state: 'QualityRAGState'
    ) -> list:
        """벡터 검색 폴백"""
        if self._has_multi_collection():
            docs = self.doc_service.multi_collection_search(query, k=retrieval_k)
            state['retrieval_method'] = "multi_collection_vector"
        else:
            docs = self.vectorstore.similarity_search(query, k=retrieval_k)
            state['retrieval_method'] = "vector_similarity"

        return docs

    def _has_multi_collection(self) -> bool:
        """다중 컬렉션 사용 가능 여부"""
        return (
            self.doc_service and
            hasattr(self.doc_service, 'active_vectorstores') and
            self.doc_service.active_vectorstores
        )

    def _deduplicate_docs(self, docs: list) -> list:
        """중복 문서 제거"""
        unique_docs = []
        seen_contents = set()

        for doc in docs:
            content_hash = hash(doc.page_content)
            if content_hash not in seen_contents:
                unique_docs.append(doc)
                seen_contents.add(content_hash)

        return unique_docs
