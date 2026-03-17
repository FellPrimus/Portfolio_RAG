"""
Qwen3-Embedding-8B 임베딩 모듈

NAMC AI Gateway를 통한 Qwen3 임베딩 API 연동
"""

import os
import requests
import time
from typing import List
from langchain_core.embeddings import Embeddings  # LangChain 1.0+
from tenacity import retry, stop_after_attempt, wait_exponential


class QwenEmbeddings(Embeddings):
    """Qwen3-Embedding-8B 임베딩 클래스"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "Qwen3-Embedding-8B",
        base_url: str = "https://namc-aigw.io.naver.com",
        batch_size: int = 32,
        request_delay: float = 0.1  # API rate limiting을 위한 요청 간 지연 (초)
    ):
        """
        QwenEmbeddings 초기화

        Args:
            api_key (str): Qwen API 키 (None이면 환경변수에서 읽음)
            model (str): 임베딩 모델명. 기본값 "Qwen3-Embedding-8B"
            base_url (str): API 기본 URL
            batch_size (int): 배치 처리 크기. 기본값 32
            request_delay (float): 요청 간 지연 시간 (초)
        """
        self.api_key = api_key or os.getenv("QWEN_EMBEDDING_API_KEY") or os.getenv("QWEN_API_KEY")
        self.model = model
        self.base_url = base_url
        self.batch_size = batch_size
        self.request_delay = request_delay
        self.endpoint = f"{base_url}/embeddings"

        if not self.api_key:
            raise ValueError(
                "QWEN_EMBEDDING_API_KEY 또는 QWEN_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 파일을 확인해주세요."
            )

        print(f"[OK] Qwen Embedding API 초기화 완료")
        print(f"  - 모델: {self.model}")
        print(f"  - 배치 크기: {self.batch_size}")
        print(f"  - 요청 지연: {self.request_delay}초")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """
        API 호출 (재시도 로직 포함)

        Args:
            texts (List[str]): 임베딩할 텍스트 리스트

        Returns:
            List[List[float]]: 임베딩 벡터 리스트

        Raises:
            requests.HTTPError: API 요청 실패 시
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "input": texts,
            "model": self.model
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
            #   "data": [
            #     {"embedding": [...], "index": 0},
            #     {"embedding": [...], "index": 1},
            #     ...
            #   ],
            #   "model": "Qwen3-Embedding-8B",
            #   "usage": {"prompt_tokens": N, "total_tokens": N}
            # }

            if "data" not in result:
                raise ValueError(f"예상하지 못한 API 응답 형식: {result}")

            # index 순서대로 정렬하여 반환
            embeddings = sorted(result["data"], key=lambda x: x["index"])

            return [item["embedding"] for item in embeddings]

        except requests.exceptions.HTTPError as e:
            error_msg = f"Qwen API 요청 실패: {e}"
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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서 리스트 임베딩 (배치 처리)

        Args:
            texts (List[str]): 임베딩할 텍스트 리스트

        Returns:
            List[List[float]]: 임베딩 벡터 리스트
        """
        all_embeddings = []
        total = len(texts)
        start_time = time.time()

        print(f"[임베딩 시작] 총 {total}개 문서 처리 예정 (배치 크기: {self.batch_size})")

        # 배치 단위로 처리
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            if batch_num % 5 == 0 or batch_num == total_batches:
                print(f"  진행 중: 배치 {batch_num}/{total_batches} ({i}/{total} 문서)")

            # API 호출
            embeddings = self._call_api(batch)
            all_embeddings.extend(embeddings)

            # Rate limiting: 마지막 배치가 아니면 대기
            if i + self.batch_size < len(texts):
                time.sleep(self.request_delay)

        elapsed = time.time() - start_time
        print(f"[OK] {total}개 문서 임베딩 완료 (총 {elapsed:.1f}초 소요)")
        print(f"  - 평균 속도: {total/elapsed:.1f}개/초")

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        단일 쿼리 임베딩

        Args:
            text (str): 임베딩할 쿼리 텍스트

        Returns:
            List[float]: 임베딩 벡터
        """
        return self._call_api([text])[0]


# 사용 예제 및 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=== Qwen Embedding 테스트 ===\n")

    try:
        embeddings = QwenEmbeddings()

        # 단일 텍스트 테스트
        test_text = "안녕하세요. Qwen3 임베딩 테스트 문장입니다."
        print(f"테스트 텍스트: {test_text}")

        vector = embeddings.embed_query(test_text)
        print(f"임베딩 벡터 크기: {len(vector)}")
        print(f"벡터 샘플 (처음 5개): {vector[:5]}")

        # 배치 테스트
        test_docs = [
            "첫 번째 문서입니다.",
            "두 번째 문서입니다.",
            "세 번째 문서입니다."
        ]
        print(f"\n배치 테스트: {len(test_docs)}개 문서")
        vectors = embeddings.embed_documents(test_docs)
        print(f"결과: {len(vectors)}개 벡터 생성")

        print("\n[SUCCESS] 테스트 완료!")

    except Exception as e:
        print(f"\n[ERROR] 에러: {e}")
        import traceback
        traceback.print_exc()
