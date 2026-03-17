"""
웹 검색 교차 검증 노드

웹 검색 결과를 통한 답변 교차 검증을 담당합니다.
"""
from __future__ import annotations

from src.graph.state import QualityRAGState
from src.verification.web_cross_verifier import VerificationStatus


class WebSearchVerifierNode:
    """웹 검색 교차 검증 노드"""

    def __init__(
        self,
        web_search_service,
        web_cross_verifier,
        web_search_settings
    ):
        """
        Args:
            web_search_service: TavilySearchService 인스턴스
            web_cross_verifier: WebCrossVerifier 인스턴스
            web_search_settings: 웹 검색 설정
        """
        self.web_search_service = web_search_service
        self.web_cross_verifier = web_cross_verifier
        self.web_search_settings = web_search_settings

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        웹 검색 교차 검증 실행

        - 웹 검색 실행
        - 교차 검증
        - 답변 보강 또는 신뢰도 조정
        """
        print("[5.5/8] Web search cross-verification...")

        # 웹 검색 비활성화 시 건너뜀
        if not self._should_run_verification(state):
            return self._skip_verification(state)

        try:
            # 1. 웹 검색 실행
            print("   Running web search...")
            web_results = self.web_search_service.search(state['question'])
            state['web_search_results'] = web_results

            if not web_results:
                return self._no_results(state)

            print(f"   Found {len(web_results)} web results")

            # 2. 교차 검증 실행
            print("   Running cross-verification...")
            from src.verification.web_cross_verifier import VerificationStatus

            verification = self.web_cross_verifier.verify_and_enhance(
                question=state['question'],
                rag_answer=state['answer'],
                web_results=web_results
            )

            # 3. 검증 결과 적용
            state['web_verification_status'] = verification.status.value
            state['web_sources'] = verification.web_sources
            state['web_confidence_delta'] = verification.confidence_delta
            state['web_enhanced_answer'] = verification.enhanced_answer
            state['web_verification_details'] = verification.verification_details

            # 4. 답변 보강 (enhanced 상태)
            if verification.status == VerificationStatus.ENHANCED and verification.enhanced_answer:
                print("   Answer enhanced with web search results")
                state['answer'] = verification.enhanced_answer
                state['warnings'].append("Answer enhanced with web search results.")

            # 5. 신뢰도 조정
            current_quality = state.get('quality_score', 0.5)
            new_quality = max(0.0, min(1.0, current_quality + verification.confidence_delta))
            state['quality_score'] = new_quality

            # 상태 메시지
            status_msg = self._get_status_message(verification.status.value)
            print(f"   Verification complete: {status_msg}")
            print(f"   Confidence change: {verification.confidence_delta:+.2f} -> Final: {new_quality:.2f}")

            state['steps'].append(
                f"Web search verification complete ({verification.status.value}, "
                f"confidence delta: {verification.confidence_delta:+.2f})"
            )

            # 충돌 경고
            if verification.status == VerificationStatus.CONFLICTING:
                state['warnings'].append(
                    f"Web search results differ. {verification.verification_notes}"
                )

        except Exception as e:
            import traceback
            print(f"   Web search verification failed: {e}")
            print(traceback.format_exc())
            return self._handle_error(state, str(e))

        return state

    def _should_run_verification(self, state: 'QualityRAGState') -> bool:
        """검증 실행 여부 판단"""
        if not state.get('web_search_enabled', False):
            return False

        if not self.web_search_service:
            return False

        # 보안 모드 체크
        if state.get('secure_mode', False):
            if not self.web_search_settings.allowed_in_secure_mode:
                return False

        return True

    def _skip_verification(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """검증 건너뛰기"""
        state['web_verification_status'] = 'skipped'
        state['web_search_results'] = []
        state['web_sources'] = []
        state['web_confidence_delta'] = 0.0
        state['web_enhanced_answer'] = None
        state['web_verification_details'] = None

        reason = "disabled" if not state.get('web_search_enabled') else "secure mode"
        state['steps'].append(f"Web search verification skipped ({reason})")

        if state.get('secure_mode', False) and state.get('web_search_enabled', False):
            state['warnings'].append("Web search disabled in secure mode.")

        return state

    def _no_results(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """검색 결과 없음 처리"""
        state['web_verification_status'] = 'no_data'
        state['web_sources'] = []
        state['web_confidence_delta'] = 0.0
        state['web_enhanced_answer'] = None
        state['web_verification_details'] = None
        state['steps'].append("No web search results")
        print("   No web search results found")
        return state

    def _handle_error(self, state: 'QualityRAGState', error: str) -> 'QualityRAGState':
        """에러 처리"""
        state['web_verification_status'] = 'skipped'
        state['web_search_results'] = []
        state['web_sources'] = []
        state['web_confidence_delta'] = 0.0
        state['web_enhanced_answer'] = None
        state['web_verification_details'] = None
        state['warnings'].append(f"Web search verification failed: {error}")
        state['steps'].append("Web search verification failed")
        return state

    def _get_status_message(self, status: str) -> str:
        """상태 메시지 반환"""
        messages = {
            'confirmed': "Confirmed by web search",
            'enhanced': "Answer enhanced by web search",
            'conflicting': "Some conflicts with web search",
            'no_data': "No relevant web results"
        }
        return messages.get(status, "Verification complete")
