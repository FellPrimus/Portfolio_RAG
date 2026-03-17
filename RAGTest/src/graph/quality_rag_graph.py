"""
품질 중심 LangGraph RAG 워크플로우 (리팩토링 버전)

정확도와 피드백 기반 개선에 초점을 맞춘 고급 RAG 시스템

주요 기능:
1. 다중 검색 전략 (하이브리드 검색)
2. 답변 품질 자동 검증
3. 저품질 시 자동 재시도
4. 피드백 수집 및 학습
5. 단계별 진행 상황 추적

리팩토링: 2026-01-12
- 노드별 분리 (nodes/)
- 스트리밍 핸들러 분리 (stream/)
- 유틸리티 분리 (utils/)
"""
from __future__ import annotations

import os
import json
from typing import Literal
from datetime import datetime
from langgraph.graph import StateGraph, END

# 상태 정의
from src.graph.state import QualityRAGState, create_initial_state

# 노드 클래스
from src.graph.nodes import (
    QuestionAnalyzerNode,
    DocumentRetrieverNode,
    DocumentRerankerNode,
    AnswerGeneratorNode,
    QualityVerifierNode,
    WebSearchVerifierNode,
    RetryHandlerNode,
    FinalizeNode
)

# 유틸리티
from src.graph.utils import LLMSelector

# 스트리밍
from src.graph.stream import StreamHandler

# 외부 의존성
from src.utils import get_llm
from src.prompts import get_system_prompt
from src.config.settings import get_settings

# RAG 모듈
from src.reranker.qwen_reranker import QwenReranker
from src.vectorstore.hybrid_search import HybridSearcher
from src.query.query_transformer import QueryTransformer
from src.query.query_classifier import QueryClassifier
from src.verification.self_rag import SelfRAGVerifier
from src.verification.web_cross_verifier import WebCrossVerifier
from src.websearch.tavily_search import create_tavily_service


class QualityRAGGraph:
    """
    품질 중심 LangGraph RAG 시스템 (파사드)

    워크플로우:
    1. 질문 분석 및 확장
    2. 다중 전략 검색
    3. 문서 재순위화
    4. 답변 생성
    5. 품질 자동 검증
    6. 필요시 재시도
    7. 최종 답변 반환
    """

    def __init__(
        self,
        vectorstore,
        retrieval_k: int = 5,
        max_retries: int = 2,
        min_quality_score: float = 0.6,
        llm_provider: str = None,
        prompt_strategy: str = None,
        category_manager=None,
        doc_service=None
    ):
        """
        Args:
            vectorstore: 벡터 스토어 인스턴스
            retrieval_k: 검색할 문서 수
            max_retries: 최대 재시도 횟수
            min_quality_score: 최소 품질 점수
            llm_provider: LLM 제공자
            prompt_strategy: 프롬프트 전략
            category_manager: 카테고리 관리자
            doc_service: DocumentService 인스턴스
        """
        # 설정 로드
        self.settings = get_settings()

        # 기본 속성
        self.vectorstore = vectorstore
        self.doc_service = doc_service
        self.category_manager = category_manager

        # 설정에서 값 가져오기
        self.retrieval_k = retrieval_k or self.settings.rag.retrieval_k
        self.max_retries = max_retries or self.settings.rag.max_retries
        self.min_quality_score = min_quality_score or self.settings.rag.min_quality_score

        # 프롬프트 전략
        self.prompt_strategy = prompt_strategy or self.settings.llm.prompt_strategy
        self.system_prompt_template = get_system_prompt(self.prompt_strategy)

        print(f"[OK] Prompt strategy: {self.prompt_strategy}")

        # LLM 초기화
        self.default_llm_provider = llm_provider
        self.llm = get_llm(provider=llm_provider, temperature=self.settings.llm.temperature)
        self.creative_llm = get_llm(provider=llm_provider, temperature=self.settings.llm.creative_temperature)

        # 컴포넌트 초기화
        self._init_components()

        # 그래프 생성
        self.graph = self._build_graph()

        # 피드백 디렉토리
        self.feedback_dir = self.settings.paths.feedback_dir
        os.makedirs(self.feedback_dir, exist_ok=True)

    def _init_components(self):
        """컴포넌트 초기화"""
        # Reranker
        try:
            self.reranker = QwenReranker()
            print("[OK] Qwen Reranker initialized")
        except Exception as e:
            print(f"[WARN] Qwen Reranker init failed: {e}")
            self.reranker = None

        # Query components
        self.query_transformer = QueryTransformer(self.llm)
        self.query_classifier = QueryClassifier(self.llm)
        self.self_rag_verifier = SelfRAGVerifier(self.llm)
        print("[OK] Query Transformer, Classifier, Verifier initialized")

        # Hybrid Searcher
        try:
            self.hybrid_searcher = HybridSearcher(
                vectorstore=self.vectorstore,
                alpha=self.settings.rag.hybrid_alpha,
                use_konlpy=True
            )
            print("[OK] Hybrid Searcher initialized")
        except Exception as e:
            print(f"[WARN] Hybrid Searcher init failed: {e}")
            self.hybrid_searcher = None

        # 웹 검색 서비스
        self.web_search_settings = self.settings.web_search
        self.web_search_service = None
        self.web_cross_verifier = None

        if self.web_search_settings.enabled or self.web_search_settings.api_key:
            try:
                self.web_search_service = create_tavily_service(self.web_search_settings)
                if self.web_search_service:
                    # VectorStore의 임베딩 서비스 재사용
                    embedding_service = getattr(self.vectorstore, 'embedding_function', None)

                    # 임베딩 유사도 임계값 설정
                    similarity_thresholds = {
                        'confirmed': self.web_search_settings.embedding_similarity_confirmed,
                        'enhanced': self.web_search_settings.embedding_similarity_enhanced,
                        'conflicting': self.web_search_settings.embedding_similarity_conflicting
                    }

                    self.web_cross_verifier = WebCrossVerifier(
                        llm_service=self.llm,
                        embedding_service=embedding_service,
                        similarity_thresholds=similarity_thresholds
                    )

                    if embedding_service:
                        print("[OK] Web search verification initialized (embedding-based similarity)")
                    else:
                        print("[OK] Web search verification initialized (keyword-based fallback)")
            except Exception as e:
                print(f"[WARN] Web search init failed: {e}")

        # LLM 선택기
        self.llm_selector = LLMSelector(default_llm=self.llm)

        # 노드 인스턴스 생성
        self._init_nodes()

    def _init_nodes(self):
        """노드 인스턴스 생성"""
        self._question_analyzer = QuestionAnalyzerNode(
            self.query_classifier,
            self.query_transformer
        )

        self._document_retriever = DocumentRetrieverNode(
            self.vectorstore,
            self.hybrid_searcher,
            self.doc_service,
            self.retrieval_k
        )

        self._document_reranker = DocumentRerankerNode(
            self.reranker,
            top_n=5
        )

        self._answer_generator = AnswerGeneratorNode(
            self.llm,
            self.creative_llm,
            self.llm_selector,
            self.system_prompt_template,
            self.prompt_strategy
        )

        self._quality_verifier = QualityVerifierNode(
            self.self_rag_verifier,
            self.min_quality_score,
            self.max_retries,
            self.settings.rag.min_answer_length,
            {
                'length': self.settings.rag.quality_weight_length,
                'document_grounding': self.settings.rag.quality_weight_grounding,
                'directness': self.settings.rag.quality_weight_directness,
                'relevance': self.settings.rag.quality_weight_relevance
            }
        )

        self._web_search_verifier = WebSearchVerifierNode(
            self.web_search_service,
            self.web_cross_verifier,
            self.web_search_settings
        )

        self._retry_handler = RetryHandlerNode(
            self.vectorstore,
            self.doc_service,
            self._answer_generator,
            self.retrieval_k
        )

        self._finalize = FinalizeNode()

    def _build_graph(self) -> StateGraph:
        """RAG 그래프 구성"""
        workflow = StateGraph(QualityRAGState)

        # 노드 추가
        workflow.add_node("analyze_question", self._question_analyzer)
        workflow.add_node("retrieve_documents", self._document_retriever)
        workflow.add_node("rerank_documents", self._document_reranker)
        workflow.add_node("generate_answer", self._answer_generator)
        workflow.add_node("verify_quality", self._quality_verifier)
        workflow.add_node("web_search_verify", self._web_search_verifier)
        workflow.add_node("retry_generation", self._retry_handler)
        workflow.add_node("finalize_answer", self._finalize)

        # 엣지 설정
        workflow.set_entry_point("analyze_question")
        workflow.add_edge("analyze_question", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "rerank_documents")
        workflow.add_edge("rerank_documents", "generate_answer")
        workflow.add_edge("generate_answer", "verify_quality")

        # 조건부 라우팅
        workflow.add_conditional_edges(
            "verify_quality",
            self._should_retry,
            {
                "retry": "retry_generation",
                "web_verify": "web_search_verify",
                "finalize": "finalize_answer"
            }
        )

        workflow.add_edge("retry_generation", "verify_quality")
        workflow.add_edge("web_search_verify", "finalize_answer")
        workflow.add_edge("finalize_answer", END)

        return workflow.compile()

    def _should_retry(self, state: QualityRAGState) -> Literal["retry", "web_verify", "finalize"]:
        """품질 검증 후 라우팅 결정"""
        if state.get('needs_retry', False):
            return "retry"

        if state.get('web_search_enabled', False) and self.web_search_service:
            if state.get('secure_mode', False) and not self.web_search_settings.allowed_in_secure_mode:
                return "finalize"
            return "web_verify"

        return "finalize"

    # ========================================
    # 공개 API
    # ========================================

    def query(self, question: str, session_id: str = None) -> dict:
        """
        질문에 대한 답변 생성

        Args:
            question: 사용자 질문
            session_id: 세션 ID

        Returns:
            dict: 답변 및 메타데이터
        """
        import time
        start_time = time.time()

        print("=" * 60)
        print("Quality RAG Workflow Started")
        print("=" * 60)

        initial_state = create_initial_state(
            question=question,
            session_id=session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        )

        final_state = self.graph.invoke(initial_state)
        final_state['processing_time'] = time.time() - start_time

        print("\n" + "=" * 60)
        print(f"Workflow complete ({final_state['processing_time']:.2f}s)")
        print("=" * 60)

        return final_state

    def query_stream(
        self,
        question: str,
        session_id: str = None,
        secure_mode: bool = False,
        web_search_enabled: bool = False
    ):
        """
        스트리밍 답변 생성

        Args:
            question: 사용자 질문
            session_id: 세션 ID
            secure_mode: 보안 모드
            web_search_enabled: 웹 검색 활성화

        Yields:
            dict: 이벤트 데이터
        """
        handler = StreamHandler(self.graph)
        yield from handler.stream(
            question=question,
            session_id=session_id,
            secure_mode=secure_mode,
            web_search_enabled=web_search_enabled
        )

    def save_feedback(self, session_id: str, rating: int, comment: str = ""):
        """
        사용자 피드백 저장

        Args:
            session_id: 세션 ID
            rating: 평점 (1-5)
            comment: 코멘트
        """
        feedback = {
            'session_id': session_id,
            'rating': rating,
            'comment': comment,
            'timestamp': datetime.now().isoformat()
        }

        feedback_file = os.path.join(self.feedback_dir, f"{session_id}.json")
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback, f, ensure_ascii=False, indent=2)

        print(f"[OK] Feedback saved: {feedback_file}")

    def get_feedback_stats(self) -> dict:
        """
        피드백 통계 조회

        Returns:
            dict: 평균 평점, 총 피드백 수 등
        """
        feedback_files = [f for f in os.listdir(self.feedback_dir) if f.endswith('.json')]

        if not feedback_files:
            return {"total": 0, "average_rating": 0}

        ratings = []
        for file in feedback_files:
            try:
                with open(os.path.join(self.feedback_dir, file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ratings.append(data.get('rating', 0))
            except:
                continue

        return {
            "total": len(ratings),
            "average_rating": sum(ratings) / len(ratings) if ratings else 0,
            "ratings_distribution": {
                i: ratings.count(i) for i in range(1, 6)
            }
        }

    # ========================================
    # 하위 호환성을 위한 메서드 (기존 API 유지)
    # ========================================

    def _analyze_question(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 질문 분석"""
        return self._question_analyzer(state)

    def _retrieve_documents(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 문서 검색"""
        return self._document_retriever(state)

    def _rerank_documents(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 문서 재순위화"""
        return self._document_reranker(state)

    def _generate_answer(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 답변 생성"""
        return self._answer_generator(state)

    def _verify_quality(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 품질 검증"""
        return self._quality_verifier(state)

    def _web_search_verify(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 웹 검색 검증"""
        return self._web_search_verifier(state)

    def _retry_generation(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 재시도"""
        return self._retry_handler(state)

    def _finalize_answer(self, state: QualityRAGState) -> QualityRAGState:
        """[하위 호환성] 최종 확정"""
        return self._finalize(state)

    def _select_llm_for_categories(self, categories, secure_mode=False):
        """[하위 호환성] LLM 선택"""
        return self.llm_selector.select_for_categories(categories, secure_mode)
