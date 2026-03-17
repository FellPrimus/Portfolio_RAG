"""
Qwen3-Reranker-8B 재순위화 모듈

Cross-Encoder 기반 문서 재순위화
"""

import os
import requests
from typing import List, Tuple
from langchain_core.documents import Document
from tenacity import retry, stop_after_attempt, wait_exponential


class QwenReranker:
    """Qwen3-Reranker-8B 기반 Cross-Encoder Reranker"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "Qwen3-Reranker-8B",
        base_url: str = "https://namc-aigw.io.naver.com"
    ):
        """
        QwenReranker 초기화

        Args:
            api_key (str): Qwen API 키 (None이면 환경변수에서 읽음)
            model (str): Reranker 모델명. 기본값 "Qwen3-Reranker-8B"
            base_url (str): API 기본 URL
        """
        self.api_key = api_key or os.getenv("QWEN_RERANKER_API_KEY") or os.getenv("QWEN_API_KEY")
        self.model = model
        self.endpoint = f"{base_url}/rerank"

        if not self.api_key:
            raise ValueError(
                "QWEN_RERANKER_API_KEY 또는 QWEN_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 파일을 확인해주세요."
            )

        print(f"[OK] Qwen Reranker API 초기화 완료")
        print(f"  - 모델: {self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_n: int = 5
    ) -> List[Tuple[Document, float]]:
        """
        문서 재순위화

        Args:
            query: 검색 쿼리
            documents: 재순위화할 Document 리스트
            top_n: 반환할 상위 문서 수

        Returns:
            List[Tuple[Document, float]]: (문서, 관련성 점수) 튜플 리스트
                점수가 높은 순으로 정렬됨

        Raises:
            requests.HTTPError: API 요청 실패 시
        """
        if not documents:
            return []

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Document에서 텍스트 추출
        doc_texts = [doc.page_content for doc in documents]

        payload = {
            "query": query,
            "documents": doc_texts,
            "model": self.model,
            "top_n": min(top_n, len(documents))
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()

            # API 응답 형식:
            # {
            #   "results": [
            #     {"index": 0, "relevance_score": 0.95},
            #     {"index": 2, "relevance_score": 0.82},
            #     ...
            #   ],
            #   "model": "Qwen3-Reranker-8B"
            # }

            if "results" not in result:
                raise ValueError(f"예상하지 못한 API 응답 형식: {result}")

            # 결과를 점수순으로 정렬하여 Document와 매핑
            reranked = []
            for item in result["results"]:
                idx = item["index"]
                score = item["relevance_score"]
                reranked.append((documents[idx], score))

            return reranked

        except requests.exceptions.HTTPError as e:
            error_msg = f"Qwen Reranker API 요청 실패: {e}"
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f"\n상세: {error_detail}"
                except:
                    error_msg += f"\n응답: {e.response.text}"

            print(f"[ERROR] {error_msg}")
            raise

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 네트워크 에러: {e}")
            raise


# 사용 예제 및 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=== Qwen Reranker 테스트 ===\n")

    try:
        reranker = QwenReranker()

        # 테스트 문서
        test_docs = [
            Document(page_content="Python은 간단하고 읽기 쉬운 프로그래밍 언어입니다."),
            Document(page_content="Java는 객체지향 프로그래밍 언어입니다."),
            Document(page_content="Python은 데이터 분석과 머신러닝에 널리 사용됩니다."),
            Document(page_content="JavaScript는 웹 개발을 위한 언어입니다."),
            Document(page_content="Python의 인기는 계속 증가하고 있습니다.")
        ]

        query = "Python 특징"

        print(f"쿼리: {query}")
        print(f"문서 수: {len(test_docs)}")
        print("\n재순위화 실행 중...")

        results = reranker.rerank(query, test_docs, top_n=3)

        print(f"\n재순위화 결과 (상위 {len(results)}개):")
        for i, (doc, score) in enumerate(results):
            print(f"\n{i+1}. 점수: {score:.4f}")
            print(f"   내용: {doc.page_content}")

        print("\n[SUCCESS] 테스트 완료!")

    except Exception as e:
        print(f"\n[ERROR] 에러: {e}")
        import traceback
        traceback.print_exc()
