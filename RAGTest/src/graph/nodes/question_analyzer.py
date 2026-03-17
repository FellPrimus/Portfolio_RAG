"""
질문 분석 노드

Adaptive RAG 기반 질문 분석 및 쿼리 변환을 담당합니다.
"""
from __future__ import annotations

from datetime import datetime
from src.graph.state import QualityRAGState


class QuestionAnalyzerNode:
    """질문 분석 노드"""

    def __init__(self, query_classifier, query_transformer):
        """
        Args:
            query_classifier: QueryClassifier 인스턴스
            query_transformer: QueryTransformer 인스턴스
        """
        self.query_classifier = query_classifier
        self.query_transformer = query_transformer

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        질문 분석 실행 (Adaptive RAG + Query Transformation)

        - 질문 유형 파악 (Query Classifier)
        - 검색 전략 결정
        - 쿼리 재작성 또는 다중 쿼리 생성
        """
        print("\n[1/7] Analyzing question (Adaptive RAG)...")

        # 상태 초기화
        state['retry_count'] = 0
        state['warnings'] = []
        state['timestamp'] = datetime.now().isoformat()
        state['steps'] = ["Question analysis started"]
        state['used_model'] = ""
        state['model_selection_reason'] = ""
        state['original_question'] = state['question']
        state['hybrid_search_used'] = False
        state['semantic_chunking_used'] = False
        state['hallucination_detected'] = False
        state['self_rag_verification'] = {}

        # 질문 유효성 검사
        if not state.get('question') or len(state['question'].strip()) < 3:
            state['error'] = "Question is too short."
            state['steps'].append("Error: Invalid question")
            return state

        try:
            # 쿼리 유형 분류
            query_type = self.query_classifier.classify(state['question'])
            state['query_type'] = query_type.value

            # 쿼리 유형에 따른 검색 설정
            retrieval_config = self.query_classifier.get_retrieval_config(query_type)
            state['retrieval_config'] = retrieval_config

            print(f"   Query type: {query_type.value}")
            print(f"   Strategy: {retrieval_config['description']}")

            # 다중 쿼리 생성 (COMPLEX, MULTI_HOP 타입)
            if retrieval_config.get('use_multi_query', False):
                print("   Generating multi-queries...")
                search_queries = self.query_transformer.generate_multi_queries(
                    state['question'],
                    num_queries=2
                )
                state['search_queries'] = search_queries
                print(f"   Generated {len(search_queries)} search queries")
            else:
                # 단순 쿼리 재작성
                rewritten = self.query_transformer.rewrite_query(state['question'])
                state['search_queries'] = [rewritten]
                if rewritten != state['question']:
                    print(f"   Query rewritten: {rewritten}")

            state['steps'].append(
                f"Question analysis complete ({query_type.value}, {len(state['search_queries'])} queries)"
            )

        except Exception as e:
            print(f"   Query analysis failed, using defaults: {e}")
            state['query_type'] = "COMPLEX"
            state['search_queries'] = [state['question']]
            state['retrieval_config'] = {
                "retrieval_k": 5,
                "use_multi_query": False,
                "use_rerank": True,
                "use_hybrid": True
            }
            state['steps'].append("Question analysis complete (default settings)")

        return state
