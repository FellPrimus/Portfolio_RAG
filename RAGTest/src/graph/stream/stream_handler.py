"""
스트리밍 응답 핸들러

RAG 쿼리의 스트리밍 응답 처리를 담당합니다.
"""

import os
import json
import time
from datetime import datetime
from typing import Generator, Any

from src.config.settings import get_settings


class StreamHandler:
    """RAG 스트리밍 응답 핸들러"""

    def __init__(self, graph):
        """
        Args:
            graph: 컴파일된 LangGraph 인스턴스
        """
        self.graph = graph
        self.settings = get_settings()

    def stream(
        self,
        question: str,
        session_id: str = None,
        secure_mode: bool = False,
        web_search_enabled: bool = False
    ) -> Generator[dict, None, None]:
        """
        스트리밍 쿼리 실행

        Args:
            question: 사용자 질문
            session_id: 세션 ID
            secure_mode: 보안 모드
            web_search_enabled: 웹 검색 활성화

        Yields:
            dict: 이벤트 데이터
        """
        start_time = time.time()
        session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            print("=" * 60)
            print("Quality RAG Workflow Started (Streaming)")
            if web_search_enabled:
                print("Web search verification enabled")
            print("=" * 60)

            # 상태 이벤트: 질문 분석 시작
            yield self._status_event("Analyzing question...")

            # 초기 상태 구성
            initial_state = self._create_initial_state(
                question, session_id, secure_mode, web_search_enabled
            )

            # 상태 이벤트: 문서 검색 시작
            yield self._status_event("Searching documents...")

            # 그래프 실행
            final_state = self.graph.invoke(initial_state)

            # 상태 이벤트: 답변 생성 완료
            yield self._status_event("Generating answer...")

            processing_time = time.time() - start_time

            # 에러 확인
            if final_state.get('error'):
                yield self._error_event(final_state['error'])
                return

            # 답변 스트리밍
            yield from self._stream_answer(final_state)

            # 참조 문서 전송
            yield self._sources_event(final_state)

            # 웹 검증 결과 전송
            if final_state.get('web_verification_status', 'skipped') != 'skipped':
                yield self._web_verification_event(final_state)

            # 완료 메타데이터 전송
            yield self._done_event(final_state, processing_time)

            print("\n" + "=" * 60)
            print(f"Workflow complete ({processing_time:.2f}s)")
            print(f"Model used: {final_state.get('used_model', 'N/A')}")
            print("=" * 60)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            yield self._error_event(str(e))

    def _create_initial_state(
        self,
        question: str,
        session_id: str,
        secure_mode: bool,
        web_search_enabled: bool
    ) -> dict:
        """초기 상태 생성"""
        return {
            "question": question,
            "session_id": session_id,
            "retrieved_docs": [],
            "answer": "",
            "quality_score": 0.0,
            "confidence": "unknown",
            "steps": [],
            "warnings": [],
            "error": "",
            "retry_count": 0,
            "sources_used": [],
            "used_model": "",
            "model_selection_reason": "",
            "secure_mode": secure_mode,
            "web_search_enabled": web_search_enabled,
            "web_search_results": [],
            "web_verification_status": "skipped",
            "web_enhanced_answer": None,
            "web_sources": [],
            "web_confidence_delta": 0.0,
            "web_verification_details": None
        }

    def _stream_answer(self, state: dict) -> Generator[dict, None, None]:
        """답변 청크 스트리밍"""
        answer = state.get('answer', '')
        chunk_size = self.settings.streaming.chunk_size
        chunk_delay = self.settings.streaming.delay

        for i in range(0, len(answer), chunk_size):
            chunk = answer[i:i + chunk_size]
            yield {
                'type': 'answer_chunk',
                'data': json.dumps({'content': chunk}, ensure_ascii=False)
            }
            time.sleep(chunk_delay)

    def _status_event(self, message: str) -> dict:
        """상태 이벤트 생성"""
        return {
            'type': 'status',
            'data': json.dumps({'message': message}, ensure_ascii=False)
        }

    def _error_event(self, error: str) -> dict:
        """에러 이벤트 생성"""
        return {
            'type': 'error',
            'data': json.dumps({'error': error}, ensure_ascii=False)
        }

    def _sources_event(self, state: dict) -> dict:
        """참조 문서 이벤트 생성"""
        preview_length = self.settings.streaming.preview_length
        sources = []

        for doc in state.get('retrieved_docs', []):
            sources.append({
                'content': doc.page_content[:preview_length] + '...',
                'source': os.path.basename(doc.metadata.get('source', 'N/A'))
            })

        return {
            'type': 'sources',
            'data': json.dumps({'sources': sources}, ensure_ascii=False)
        }

    def _web_verification_event(self, state: dict) -> dict:
        """웹 검증 이벤트 생성"""
        return {
            'type': 'web_verification',
            'data': json.dumps({
                'status': state.get('web_verification_status'),
                'confidence_delta': state.get('web_confidence_delta', 0.0),
                'web_sources': state.get('web_sources', [])
            }, ensure_ascii=False)
        }

    def _done_event(self, state: dict, processing_time: float) -> dict:
        """완료 이벤트 생성"""
        return {
            'type': 'done',
            'data': json.dumps({
                'success': True,
                'quality_score': state.get('quality_score', 0),
                'confidence': state.get('confidence', 'unknown'),
                'used_model': state.get('used_model', 'N/A'),
                'model_selection_reason': state.get('model_selection_reason', ''),
                'processing_time': processing_time,
                'retry_count': state.get('retry_count', 0),
                'warnings': state.get('warnings', []),
                'rerank_scores': state.get('rerank_scores'),
                'query_type': state.get('query_type', ''),
                'search_queries': state.get('search_queries', []),
                'original_question': state.get('original_question', ''),
                'hybrid_search_used': state.get('hybrid_search_used', False),
                'semantic_chunking_used': state.get('semantic_chunking_used', False),
                'hallucination_detected': state.get('hallucination_detected', False),
                'self_rag_verification': state.get('self_rag_verification', {}),
                'web_search_enabled': state.get('web_search_enabled', False),
                'web_verification_status': state.get('web_verification_status', 'skipped'),
                'web_confidence_delta': state.get('web_confidence_delta', 0.0),
                'web_sources': state.get('web_sources', []),
                'web_verification_details': state.get('web_verification_details', None)
            }, ensure_ascii=False)
        }
