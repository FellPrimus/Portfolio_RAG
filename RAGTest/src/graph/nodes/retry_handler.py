"""
재시도 처리 노드

답변 재생성을 담당합니다.
"""
from __future__ import annotations

from src.graph.state import QualityRAGState


class RetryHandlerNode:
    """재시도 처리 노드"""

    def __init__(
        self,
        vectorstore,
        doc_service,
        answer_generator,
        retrieval_k: int = 5
    ):
        """
        Args:
            vectorstore: 벡터스토어 인스턴스
            doc_service: DocumentService 인스턴스
            answer_generator: AnswerGeneratorNode 인스턴스
            retrieval_k: 기본 검색 문서 수
        """
        self.vectorstore = vectorstore
        self.doc_service = doc_service
        self.answer_generator = answer_generator
        self.retrieval_k = retrieval_k

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        재시도 답변 생성

        - 더 많은 문서 검색
        - 다른 접근 방식으로 재생성
        """
        print(f"[6/7] Retrying... ({state['retry_count'] + 1})")

        state['retry_count'] += 1
        state['steps'].append(f"Retry {state['retry_count']} started")

        # 더 많은 문서 검색
        try:
            if self._has_multi_collection():
                more_docs = self.doc_service.multi_collection_search(
                    state['question'],
                    k=self.retrieval_k + 2
                )
            else:
                more_docs = self.vectorstore.similarity_search(
                    state['question'],
                    k=self.retrieval_k + 2
                )
            state['retrieved_docs'] = more_docs[:5]
            state['steps'].append(f"Additional search ({len(more_docs)} docs)")
        except:
            pass

        # 답변 재생성
        return self.answer_generator(state)

    def _has_multi_collection(self) -> bool:
        """다중 컬렉션 사용 가능 여부"""
        return (
            self.doc_service and
            hasattr(self.doc_service, 'active_vectorstores') and
            self.doc_service.active_vectorstores
        )


class FinalizeNode:
    """최종 확정 노드"""

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        최종 답변 확정

        - 최종 검증
        - 메타데이터 정리
        """
        print("[7/7] Finalizing answer...")

        state['steps'].append("Answer finalized")

        # 경고 메시지 추가
        if state.get('confidence') == 'low':
            state['warnings'].append("Answer confidence is low. Verification may be needed.")

        if not state.get('retrieved_docs'):
            state['warnings'].append("No relevant documents found. Answer may be limited.")

        return state
