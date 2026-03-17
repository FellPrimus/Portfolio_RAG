"""
Query Transformation 모듈

쿼리 재작성 및 다중 쿼리 생성
"""

from typing import List
import json


class QueryTransformer:
    """쿼리 변환기"""

    def __init__(self, llm):
        """
        QueryTransformer 초기화

        Args:
            llm: LLM 인스턴스 (ChatClovaX, ChatAnthropic 등)
        """
        self.llm = llm

    def rewrite_query(self, query: str) -> str:
        """
        쿼리를 검색에 최적화된 형태로 재작성

        - 약어 확장
        - 기술 용어 명확화
        - 불필요한 조사/어미 제거

        Args:
            query: 원본 쿼리

        Returns:
            str: 재작성된 쿼리
        """
        prompt = f"""당신은 검색 쿼리 최적화 전문가입니다.
사용자의 질문을 벡터 검색과 키워드 검색에 최적화된 형태로 재작성하세요.

규칙:
1. 약어를 풀어쓰기 (예: LB → Load Balancer, ALB → Application Load Balancer)
2. 기술 용어를 명확히 (예: "안됨" → "오류 발생", "느림" → "성능 저하")
3. 핵심 키워드 유지
4. 불필요한 조사나 어미 제거
5. 원래 의도 유지

원본 질문: {query}

재작성된 쿼리 (한 줄로만 출력):"""

        try:
            response = self.llm.invoke(prompt)
            rewritten = response.content if hasattr(response, 'content') else str(response)
            return rewritten.strip()
        except Exception as e:
            print(f"[WARN] 쿼리 재작성 실패, 원본 반환: {e}")
            return query

    def generate_multi_queries(self, query: str, num_queries: int = 3) -> List[str]:
        """
        하나의 질문에서 다양한 관점의 검색 쿼리 생성

        Args:
            query: 원본 질문
            num_queries: 생성할 쿼리 수 (기본값 3)

        Returns:
            List[str]: 생성된 쿼리 리스트 (원본 포함)
        """
        prompt = f"""당신은 검색 쿼리 확장 전문가입니다.
사용자의 질문을 다양한 관점에서 검색할 수 있도록 {num_queries}개의 대안 쿼리를 생성하세요.

규칙:
1. 각 쿼리는 원본 질문과 같은 정보를 찾지만 다른 표현 사용
2. 동의어, 관련 용어, 다른 관점 활용
3. 기술 문서 검색에 적합한 형태로 작성
4. 각 쿼리는 독립적으로 검색 가능해야 함

원본 질문: {query}

JSON 형식으로 출력:
{{"queries": ["쿼리1", "쿼리2", "쿼리3"]}}"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # JSON 파싱 시도
            # 코드 블록 제거
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            queries = result.get("queries", [])

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"[WARN] 다중 쿼리 생성 실패, 원본만 반환: {e}")
            queries = []

        # 원본 쿼리를 첫 번째로 포함
        return [query] + queries[:num_queries]


# 사용 예제 및 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv
    from src.utils import get_llm

    load_dotenv()

    print("=== Query Transformer 테스트 ===\n")

    try:
        llm = get_llm()
        transformer = QueryTransformer(llm)

        test_query = "ALB 설정 방법이 궁금해"

        # 쿼리 재작성
        print(f"원본 쿼리: {test_query}")
        print("\n쿼리 재작성 중...")
        rewritten = transformer.rewrite_query(test_query)
        print(f"재작성 결과: {rewritten}")

        # 다중 쿼리 생성
        print("\n\n다중 쿼리 생성 중...")
        multi_queries = transformer.generate_multi_queries(test_query, num_queries=3)
        print(f"\n생성된 쿼리 ({len(multi_queries)}개):")
        for i, q in enumerate(multi_queries):
            print(f"  {i+1}. {q}")

        print("\n[SUCCESS] 테스트 완료!")

    except Exception as e:
        print(f"\n[ERROR] 에러: {e}")
        import traceback
        traceback.print_exc()
