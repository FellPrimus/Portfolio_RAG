"""
품질 검증 노드

Self-RAG 기반 답변 품질 검증을 담당합니다.
"""
from __future__ import annotations

from src.config.constants import EVASIVE_PHRASES, CONFIDENCE_LEVELS
from src.graph.state import QualityRAGState


class QualityVerifierNode:
    """품질 검증 노드 (Self-RAG)"""

    def __init__(
        self,
        self_rag_verifier,
        min_quality_score: float = 0.6,
        max_retries: int = 2,
        min_answer_length: int = 100,
        quality_weights: dict = None
    ):
        """
        Args:
            self_rag_verifier: SelfRAGVerifier 인스턴스
            min_quality_score: 최소 품질 점수
            max_retries: 최대 재시도 횟수
            min_answer_length: 최소 답변 길이
            quality_weights: 품질 가중치 딕셔너리
        """
        self.self_rag_verifier = self_rag_verifier
        self.min_quality_score = min_quality_score
        self.max_retries = max_retries
        self.min_answer_length = min_answer_length
        self.quality_weights = quality_weights or {
            'length': 0.2,
            'document_grounding': 0.4,
            'directness': 0.2,
            'relevance': 0.2
        }

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        Self-RAG 기반 답변 품질 검증 실행

        평가 항목:
        1. 문서 근거성 (Grounding)
        2. 답변 완결성 (Completeness)
        3. 할루시네이션 탐지
        4. 정확성 (Accuracy)
        """
        print("[5/7] Verifying quality (Self-RAG)...")

        if state.get('error'):
            return state

        try:
            answer = state.get('answer', '')
            question = state.get('question', '')
            docs = state.get('retrieved_docs', [])

            # Self-RAG Verifier로 품질 검증 시도
            try:
                return self._verify_with_self_rag(state, question, answer, docs)
            except Exception as e:
                print(f"   Self-RAG verification failed, using heuristics: {e}")
                return self._verify_with_heuristics(state, answer, docs)

        except Exception as e:
            import traceback
            print(f"   Verification error: {e}")
            print(traceback.format_exc())
            state['error'] = f"Quality verification failed: {str(e)}"
            state['needs_retry'] = False

        return state

    def _verify_with_self_rag(
        self,
        state: 'QualityRAGState',
        question: str,
        answer: str,
        docs: list
    ) -> 'QualityRAGState':
        """Self-RAG 기반 검증"""
        print("   Running LLM-based quality verification...")

        verification = self.self_rag_verifier.verify_answer(
            question=question,
            answer=answer,
            documents=docs
        )

        # 검증 결과 적용
        state['quality_score'] = verification['quality_score']
        state['quality_checks'] = verification.get('raw_scores', {})
        state['self_rag_verification'] = verification

        # 할루시네이션 경고
        if verification.get('has_hallucination', False):
            state['hallucination_detected'] = True
            state['warnings'].append(
                f"Hallucination detected: {verification.get('hallucination_details', 'N/A')}"
            )

        # 피드백 출력
        if verification.get('feedback'):
            print(f"   Quality feedback: {verification['feedback'][:100]}...")

        # 신뢰도 평가
        quality_score = state['quality_score']
        state['confidence'] = self._calculate_confidence(quality_score)

        # 재시도 필요 여부
        state['needs_retry'] = (
            verification.get('needs_retry', False) and
            state.get('retry_count', 0) < self.max_retries
        )

        print(f"   Quality score: {quality_score:.2f} ({state['confidence']})")
        print(f"   Grounding: {verification.get('is_grounded', 'N/A')}, "
              f"Completeness: {verification.get('is_complete', 'N/A')}")

        state['steps'].append(
            f"Self-RAG verification complete (score: {quality_score:.2f}, "
            f"confidence: {state['confidence']})"
        )

        if state['needs_retry']:
            state['warnings'].append(
                f"Quality score low, retrying ({quality_score:.2f} < {self.min_quality_score})"
            )

        return state

    def _verify_with_heuristics(
        self,
        state: 'QualityRAGState',
        answer: str,
        docs: list
    ) -> 'QualityRAGState':
        """휴리스틱 기반 검증 (폴백)"""
        checks = {}

        # 길이 검사
        checks['length'] = min(len(answer) / self.min_answer_length, 1.0)

        # 문서 근거성
        if docs:
            doc_text = ' '.join([doc.page_content for doc in docs])
            answer_words = set(answer.split())
            doc_words = set(doc_text.split())
            overlap = len(answer_words & doc_words) / max(len(answer_words), 1)
            checks['document_grounding'] = overlap
        else:
            checks['document_grounding'] = 0.0

        # 직접성 (회피적 답변 감지)
        is_evasive = any(phrase in answer for phrase in EVASIVE_PHRASES)
        checks['directness'] = 0.3 if is_evasive else 1.0

        # 품질 점수 계산
        quality_score = sum(
            checks[k] * self.quality_weights[k]
            for k in checks if k in self.quality_weights
        )

        state['quality_checks'] = checks
        state['quality_score'] = quality_score
        state['confidence'] = self._calculate_confidence(quality_score)
        state['needs_retry'] = (
            quality_score < self.min_quality_score and
            state.get('retry_count', 0) < self.max_retries
        )

        state['steps'].append(f"Heuristic verification (score: {quality_score:.2f})")

        return state

    def _calculate_confidence(self, quality_score: float) -> str:
        """품질 점수로부터 신뢰도 계산"""
        if quality_score >= CONFIDENCE_LEVELS['high']:
            return "high"
        elif quality_score >= CONFIDENCE_LEVELS['medium']:
            return "medium"
        else:
            return "low"
