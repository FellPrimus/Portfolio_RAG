"""
Query Classification 모듈

쿼리 복잡도 및 유형 분류 (Adaptive RAG)
"""

from typing import Literal, Dict
from enum import Enum


class QueryType(str, Enum):
    """쿼리 유형"""
    SIMPLE = "SIMPLE"           # 단순 사실 확인
    COMPLEX = "COMPLEX"         # 비교/분석 필요
    MULTI_HOP = "MULTI_HOP"     # 여러 문서 조합 필요
    CLARIFICATION = "CLARIFICATION"  # 질문이 모호함


class QueryClassifier:
    """쿼리 유형 분류기"""

    def __init__(self, llm):
        """
        QueryClassifier 초기화

        Args:
            llm: LLM 인스턴스 (ChatClovaX, ChatAnthropic 등)
        """
        self.llm = llm

    def classify(self, query: str) -> QueryType:
        """
        쿼리 유형 분류

        Args:
            query: 분류할 쿼리

        Returns:
            QueryType: 분류된 쿼리 유형
        """
        prompt = f"""당신은 질문 분류 전문가입니다.
다음 질문을 분석하여 유형을 분류하세요.

질문: {query}

유형 설명:
- SIMPLE: 단순 사실 확인 (예: "ALB의 기본 포트는?", "Object Storage 가격은?")
- COMPLEX: 비교나 분석이 필요 (예: "ALB와 NLB의 차이점은?", "성능 최적화 방법은?")
- MULTI_HOP: 여러 개념을 조합해야 함 (예: "ALB 설정 후 모니터링하고 알림 받는 방법은?")
- CLARIFICATION: 질문이 모호하거나 추가 정보 필요 (예: "안됨", "에러남")

분류 결과 (SIMPLE/COMPLEX/MULTI_HOP/CLARIFICATION 중 하나만 출력):"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            content = content.strip().upper()

            # 유효한 유형인지 확인
            try:
                return QueryType(content)
            except ValueError:
                # 부분 매칭 시도
                if "SIMPLE" in content:
                    return QueryType.SIMPLE
                elif "MULTI" in content or "HOP" in content:
                    return QueryType.MULTI_HOP
                elif "CLARIF" in content:
                    return QueryType.CLARIFICATION
                else:
                    # 기본값
                    return QueryType.COMPLEX

        except Exception as e:
            print(f"[WARN] 쿼리 분류 실패, COMPLEX로 기본 설정: {e}")
            return QueryType.COMPLEX

    def get_retrieval_config(self, query_type: QueryType) -> Dict:
        """
        쿼리 유형에 따른 검색 설정 반환

        Args:
            query_type: 쿼리 유형

        Returns:
            dict: retrieval_k, use_multi_query, use_rerank 등 설정
        """
        configs = {
            QueryType.SIMPLE: {
                "retrieval_k": 3,
                "use_multi_query": False,
                "use_rerank": False,
                "use_hybrid": True,
                "description": "단순 사실 확인 - 빠른 검색"
            },
            QueryType.COMPLEX: {
                "retrieval_k": 5,
                "use_multi_query": True,
                "use_rerank": True,
                "use_hybrid": True,
                "description": "복잡한 질문 - 정밀 검색"
            },
            QueryType.MULTI_HOP: {
                "retrieval_k": 7,
                "use_multi_query": True,
                "use_rerank": True,
                "use_hybrid": True,
                "decompose_query": True,  # 쿼리 분해 필요
                "description": "다단계 추론 - 광범위 검색"
            },
            QueryType.CLARIFICATION: {
                "retrieval_k": 3,
                "use_multi_query": False,
                "use_rerank": False,
                "use_hybrid": False,
                "request_clarification": True,  # 사용자에게 명확화 요청
                "description": "모호한 질문 - 명확화 필요"
            }
        }

        return configs.get(query_type, configs[QueryType.COMPLEX])


# 사용 예제 및 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv
    from src.utils import get_llm

    load_dotenv()

    print("=== Query Classifier 테스트 ===\n")

    try:
        llm = get_llm()
        classifier = QueryClassifier(llm)

        test_queries = [
            "ALB의 기본 포트는?",
            "ALB와 NLB의 차이점을 비교해줘",
            "ALB 설정 후 CloudWatch로 모니터링하는 방법은?",
            "안됨"
        ]

        for query in test_queries:
            print(f"\n질문: {query}")
            query_type = classifier.classify(query)
            config = classifier.get_retrieval_config(query_type)

            print(f"  유형: {query_type.value}")
            print(f"  설명: {config['description']}")
            print(f"  검색 설정: 문서 수={config['retrieval_k']}, "
                  f"다중쿼리={config['use_multi_query']}, "
                  f"재순위={config['use_rerank']}")

        print("\n[SUCCESS] 테스트 완료!")

    except Exception as e:
        print(f"\n[ERROR] 에러: {e}")
        import traceback
        traceback.print_exc()
