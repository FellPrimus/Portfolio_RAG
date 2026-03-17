"""
문서 재순위화 노드

Qwen Reranker 기반 Cross-Encoder 재순위화를 담당합니다.
"""
from __future__ import annotations

from typing import Optional

from src.graph.state import QualityRAGState


class DocumentRerankerNode:
    """문서 재순위화 노드 (Qwen Reranker)"""

    def __init__(self, reranker=None, top_n: int = 5):
        """
        Args:
            reranker: QwenReranker 인스턴스 (선택)
            top_n: 선택할 상위 문서 수
        """
        self.reranker = reranker
        self.top_n = top_n

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        Cross-Encoder 기반 문서 재순위화 실행

        - Cross-Encoder로 정확한 관련성 평가
        - 상위 문서만 선택하여 품질 향상
        """
        print("[3/7] Reranking documents (Qwen Reranker)...")

        if state.get('error') or not state.get('retrieved_docs'):
            return state

        retrieval_config = state.get('retrieval_config', {})
        docs = state['retrieved_docs']
        use_rerank = retrieval_config.get('use_rerank', True)

        # Reranker 사용 여부 확인
        if self.reranker and use_rerank and len(docs) > 0:
            try:
                return self._rerank_with_model(state, docs)
            except Exception as e:
                print(f"   Reranking failed, keeping original order: {e}")
                return self._fallback_selection(state, docs, "Reranking failed")
        else:
            return self._fallback_selection(state, docs, "Reranker not used")

    def _rerank_with_model(
        self,
        state: 'QualityRAGState',
        docs: list
    ) -> 'QualityRAGState':
        """모델 기반 재순위화"""
        print(f"   Reranking {len(docs)} documents...")

        reranked = self.reranker.rerank(
            query=state['question'],
            documents=docs,
            top_n=min(self.top_n, len(docs))
        )

        state['retrieved_docs'] = [doc for doc, score in reranked]
        state['rerank_scores'] = [score for doc, score in reranked]

        print(f"   Selected top {len(state['retrieved_docs'])} documents")
        if state['rerank_scores']:
            print(f"   Highest score: {max(state['rerank_scores']):.4f}")

        state['steps'].append(
            f"Reranking complete (top {len(state['retrieved_docs'])}, "
            f"best: {max(state['rerank_scores']):.3f})"
        )

        return state

    def _fallback_selection(
        self,
        state: 'QualityRAGState',
        docs: list,
        reason: str
    ) -> 'QualityRAGState':
        """폴백: 상위 N개만 선택"""
        state['retrieved_docs'] = docs[:min(self.top_n, len(docs))]
        state['rerank_scores'] = None

        print(f"   Selected top {len(state['retrieved_docs'])} documents ({reason})")
        state['steps'].append(f"Top {len(state['retrieved_docs'])} documents selected")

        return state
