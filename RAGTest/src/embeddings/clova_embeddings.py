"""
NAVER Clova Studio Embedding API

네이버 클로바 스튜디오의 임베딩 v2 API를 사용하여 텍스트를 벡터로 변환합니다.
"""

import os
import requests
import uuid
import time
import tiktoken
from typing import List
from langchain_core.embeddings import Embeddings  # LangChain 1.0+


class ClovaEmbeddings(Embeddings):
    """
    NAVER Clova Studio Embedding v2 API 클라이언트

    API 문서: https://api.ncloud-docs.com/docs/clovastudio-embeddingv2
    """

    def __init__(
        self,
        api_key: str = None,
        endpoint: str = "https://clovastudio.stream.ntruss.com/v1/api-tools/embedding/v2/",
        request_delay: float = 1.0,  # 요청 간 기본 대기 시간 (초) - 429 에러 방지
        max_retries: int = 8,  # 429 에러 시 최대 재시도 횟수 (증가)
        retry_delay: float = 2.0,  # 재시도 시 초기 대기 시간 (초) - 더 여유있게
        max_tokens: int = 8192  # CLOVA API 최대 토큰 제한
    ):
        """
        ClovaEmbeddings 초기화

        Args:
            api_key (str): Clova Embedding API 키 (None이면 환경 변수에서 읽음)
            endpoint (str): API 엔드포인트 URL (v1 - 기존 API 유지)
            request_delay (float): 요청 간 대기 시간 (초). 기본값 1.0초 (429 에러 방지)
            max_retries (int): 429 에러 시 최대 재시도 횟수. 기본값 8회
            retry_delay (float): 재시도 시 초기 대기 시간 (초). 지수 백오프 적용 (2초 → 4초 → 8초...)
            max_tokens (int): API 최대 토큰 제한. 기본값 8192 (CLOVA 공식 제한)
        """
        # 임베딩 전용 API 키 사용 (CLOVASTUDIO_EMBEDDING_API_KEY)
        self.api_key = api_key or os.getenv("CLOVASTUDIO_EMBEDDING_API_KEY")
        if not self.api_key:
            raise ValueError("CLOVASTUDIO_EMBEDDING_API_KEY가 설정되지 않았습니다.")

        self.endpoint = endpoint
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_tokens = max_tokens

        # tiktoken 인코더 초기화 (토큰 수 계산용)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-3.5/4 기본 인코딩
        except Exception:
            self.encoding = None  # 실패 시 None (토큰 체크 비활성화)

        try:
            print(f"[OK] Clova Embedding API 초기화 완료")
            print(f"  - 요청 간격: {request_delay}초")
            print(f"  - 최대 재시도: {max_retries}회")
            print(f"  - 최대 토큰: {max_tokens:,} 토큰")
        except (ValueError, AttributeError, OSError):
            pass

    def _embed_text(self, text: str) -> List[float]:
        """
        단일 텍스트를 임베딩합니다. (Retry logic with exponential backoff)

        Args:
            text (str): 임베딩할 텍스트

        Returns:
            List[float]: 임베딩 벡터

        Raises:
            Exception: API 요청 실패 또는 재시도 횟수 초과
        """
        # ===== 토큰 수 체크 (CLOVA API 제한: 8,192 토큰) =====
        if self.encoding is not None:
            try:
                token_count = len(self.encoding.encode(text))

                if token_count > self.max_tokens:
                    # 토큰 수 초과 시 경고 및 자동 잘라내기
                    try:
                        print(f"  ⚠️  토큰 수 초과 감지: {token_count:,} 토큰 (제한: {self.max_tokens:,})")
                        print(f"  ✂️  자동으로 {self.max_tokens:,} 토큰으로 잘라냅니다...")
                    except (ValueError, AttributeError, OSError):
                        pass

                    # 토큰을 잘라내고 다시 디코딩
                    tokens = self.encoding.encode(text)[:self.max_tokens]
                    text = self.encoding.decode(tokens)

                    try:
                        print(f"  ✅ 잘라낸 후 토큰 수: {len(tokens):,}")
                    except (ValueError, AttributeError, OSError):
                        pass
            except Exception as e:
                # 토큰 계산 실패 시 무시하고 계속 진행
                try:
                    print(f"  ⚠️  토큰 수 계산 실패: {e}")
                except (ValueError, AttributeError, OSError):
                    pass

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
            "Content-Type": "application/json"
        }

        payload = {
            "text": text
        }

        # Exponential Backoff Retry Loop
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                # 429 에러 처리: Too Many Requests
                if response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff: 2초 → 4초 → 8초 → 16초 → 32초...
                        wait_time = self.retry_delay * (2 ** attempt)
                        try:
                            print(f"  ⚠️  429 Too Many Requests 발생. {wait_time:.1f}초 대기 후 재시도... (시도 {attempt + 1}/{self.max_retries})")
                        except (ValueError, AttributeError, OSError):
                            pass
                        time.sleep(wait_time)
                        continue  # 재시도
                    else:
                        error_msg = (
                            f"429 Too Many Requests: 최대 재시도 횟수 초과 ({self.max_retries}회)\n"
                            f"CLOVA API rate limit이 매우 엄격합니다.\n"
                            f"해결 방법:\n"
                            f"  1. 잠시 대기 후 다시 시도\n"
                            f"  2. .env에서 EMBEDDING_PROVIDER=huggingface로 변경 (무료, rate limit 없음)\n"
                            f"  3. 청크 크기를 늘려서 API 호출 횟수 감소"
                        )
                        raise Exception(error_msg)

                # 기타 HTTP 에러 처리
                response.raise_for_status()

                # 성공 응답 처리
                result = response.json()

                # Clova 응답 형식: {"status": {...}, "result": {"embedding": [...]}}
                if "result" in result and "embedding" in result["result"]:
                    return result["result"]["embedding"]
                else:
                    raise ValueError(f"예상하지 못한 응답 형식: {result}")

            except requests.exceptions.HTTPError as e:
                # HTTPError는 위에서 처리되지 않은 경우만 여기 도달
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    try:
                        print(f"  ⚠️  HTTP 에러 발생: {e}. {wait_time:.1f}초 대기 후 재시도...")
                    except (ValueError, AttributeError, OSError):
                        pass
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Clova Embedding API 요청 실패: {str(e)}")

            except requests.exceptions.RequestException as e:
                # 네트워크 에러 등
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    try:
                        print(f"  ⚠️  네트워크 에러: {e}. {wait_time:.1f}초 대기 후 재시도...")
                    except (ValueError, AttributeError, OSError):
                        pass
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Clova Embedding API 요청 실패: {str(e)}")

        # 모든 재시도 실패 (여기 도달하면 안 되지만 안전장치)
        error_msg = (
            f"Clova Embedding API: 최대 재시도 횟수 초과 ({self.max_retries}회)\n"
            f"API 응답이 지속적으로 실패하고 있습니다."
        )
        raise Exception(error_msg)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        여러 문서를 임베딩합니다. (Rate limiting 적용)

        Args:
            texts (List[str]): 임베딩할 텍스트 리스트

        Returns:
            List[List[float]]: 임베딩 벡터 리스트
        """
        embeddings = []
        total = len(texts)
        start_time = time.time()

        # 토큰 통계
        truncated_count = 0  # 잘려진 청크 수
        total_tokens = 0

        try:
            print(f"[임베딩 시작] 총 {total}개 청크 처리 예정")
            print(f"  - 요청 간격: {self.request_delay}초")
            print(f"  - 최대 토큰: {self.max_tokens:,} 토큰")

            # 토큰 통계 미리 계산
            if self.encoding is not None:
                token_counts = [len(self.encoding.encode(text)) for text in texts]
                total_tokens = sum(token_counts)
                max_token = max(token_counts)
                avg_token = total_tokens / len(token_counts)
                over_limit = sum(1 for tc in token_counts if tc > self.max_tokens)

                print(f"  - 평균 토큰: {avg_token:.0f} 토큰/청크")
                print(f"  - 최대 토큰: {max_token:,} 토큰")
                if over_limit > 0:
                    print(f"  - ⚠️  제한 초과 청크: {over_limit}개 (자동 잘라냄)")
        except (ValueError, AttributeError, OSError):
            pass

        for i, text in enumerate(texts):
            # 진행 상황 표시 (10개마다)
            if i % 10 == 0 and i > 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (total - i) / rate if rate > 0 else 0
                try:
                    print(f"  진행 중: {i}/{total} ({i*100//total}%) | "
                          f"속도: {rate:.1f}개/초 | 예상 남은 시간: {remaining:.0f}초")
                except (ValueError, AttributeError, OSError):
                    pass

            # 임베딩 수행
            embedding = self._embed_text(text)
            embeddings.append(embedding)

            # Rate limiting: 마지막 요청이 아니면 대기
            if i < total - 1:
                time.sleep(self.request_delay)

        elapsed = time.time() - start_time
        try:
            print(f"[OK] {total}개 문서 임베딩 완료 (총 {elapsed:.1f}초 소요)")
            if self.encoding is not None and total_tokens > 0:
                print(f"  - 총 토큰 수: {total_tokens:,} 토큰")
                print(f"  - 평균 속도: {total_tokens/elapsed:.0f} 토큰/초")
        except (ValueError, AttributeError, OSError):
            pass

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        쿼리 텍스트를 임베딩합니다.

        Args:
            text (str): 임베딩할 쿼리 텍스트

        Returns:
            List[float]: 임베딩 벡터
        """
        return self._embed_text(text)


# 사용 예제
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=== Clova Embedding 테스트 ===\n")

    try:
        embeddings = ClovaEmbeddings()

        # 단일 텍스트 테스트
        test_text = "안녕하세요. 테스트 문장입니다."
        print(f"테스트 텍스트: {test_text}")

        vector = embeddings.embed_query(test_text)
        print(f"임베딩 벡터 크기: {len(vector)}")
        print(f"벡터 샘플: {vector[:5]}")

        print("\n[SUCCESS] 테스트 완료!")

    except Exception as e:
        print(f"[ERROR] 에러: {e}")
