"""
RAG 워크플로우 상태 정의

모든 RAG 노드가 공유하는 상태 타입을 정의합니다.
"""

from typing import TypedDict, List, Annotated, Optional
from langchain_core.documents import Document
import operator


class QualityRAGState(TypedDict):
    """
    품질 중심 RAG 워크플로우의 상태

    모든 중간 과정과 결과를 추적하여 품질 관리와 피드백 수집을 가능하게 함
    """
    # 입력
    question: str
    session_id: str

    # Adaptive RAG 관련
    query_type: str  # SIMPLE, COMPLEX, MULTI_HOP, CLARIFICATION
    search_queries: List[str]
    retrieval_config: dict
    original_question: str

    # 검색 관련
    retrieved_docs: List[Document]
    retrieval_method: str
    num_docs_retrieved: int
    rerank_scores: Optional[List[float]]
    hybrid_search_used: bool
    semantic_chunking_used: bool

    # 답변 생성
    answer: str
    raw_answer: str

    # 품질 검증
    quality_score: float
    quality_checks: dict
    needs_retry: bool
    retry_count: int
    self_rag_verification: dict
    hallucination_detected: bool

    # 신뢰도 및 출처
    confidence: str  # "high", "medium", "low"
    sources_used: List[str]

    # LLM 모델 정보
    used_model: str
    model_selection_reason: str
    secure_mode: bool

    # 메타데이터
    steps: Annotated[List[str], operator.add]
    processing_time: float
    timestamp: str

    # 에러 처리
    error: str
    warnings: List[str]

    # 피드백
    user_feedback: dict

    # 웹 검색 교차 검증 관련
    web_search_enabled: bool
    web_search_results: List[dict]
    web_verification_status: str
    web_enhanced_answer: Optional[str]
    web_sources: List[dict]
    web_confidence_delta: float


def create_initial_state(question: str, session_id: str, **kwargs) -> dict:
    """초기 상태 생성 헬퍼 함수"""
    return {
        "question": question,
        "session_id": session_id,
        "query_type": "",
        "search_queries": [],
        "retrieval_config": {},
        "original_question": question,
        "retrieved_docs": [],
        "rerank_scores": None,
        "hybrid_search_used": False,
        "semantic_chunking_used": False,
        "answer": "",
        "raw_answer": "",
        "quality_score": 0.0,
        "quality_checks": {},
        "needs_retry": False,
        "confidence": "unknown",
        "self_rag_verification": {},
        "hallucination_detected": False,
        "steps": [],
        "warnings": [],
        "error": "",
        "retry_count": 0,
        "sources_used": [],
        "used_model": "",
        "model_selection_reason": "",
        "secure_mode": kwargs.get('secure_mode', False),
        "web_search_enabled": kwargs.get('web_search_enabled', False),
        "web_search_results": [],
        "web_verification_status": "skipped",
        "web_enhanced_answer": None,
        "web_sources": [],
        "web_confidence_delta": 0.0,
        "web_verification_details": None
    }
