"""
Multilingual E5 임베딩 모델

intfloat/multilingual-e5-large 모델을 사용한 로컬 임베딩
- 차원: 1024
- 최대 토큰: 512
- 100+ 언어 지원
- "query:"/"passage:" 접두사 자동 처리
"""

import logging
from typing import List, Optional

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class E5Embeddings(Embeddings):
    """
    Multilingual E5 임베딩 클래스

    E5 모델은 입력에 "query:" 또는 "passage:" 접두사가 필요합니다.
    - 검색 쿼리: "query: {text}"
    - 문서/패시지: "passage: {text}"

    Example:
        >>> from src.embeddings.e5_embeddings import E5Embeddings
        >>> embeddings = E5Embeddings()
        >>> query_embedding = embeddings.embed_query("서버 생성 방법")
        >>> doc_embeddings = embeddings.embed_documents(["문서1 내용", "문서2 내용"])
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        device: str = "cpu",
        normalize_embeddings: bool = True,
        batch_size: int = 32,
        show_progress: bool = True
    ):
        """
        E5 임베딩 모델 초기화

        Args:
            model_name: HuggingFace 모델명
            device: 실행 디바이스 ("cpu" 또는 "cuda")
            normalize_embeddings: L2 정규화 적용 여부
            batch_size: 배치 크기
            show_progress: 진행률 표시 여부
        """
        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self.batch_size = batch_size
        self.show_progress = show_progress

        self._model = None
        self._initialize_model()

    def _initialize_model(self):
        """모델 초기화 (지연 로딩)"""
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"E5 임베딩 모델 로딩 중: {self.model_name}")
            print(f"[LOG] E5 임베딩 모델 로딩 중: {self.model_name}")
            print(f"      (처음 실행 시 모델 다운로드로 시간이 걸릴 수 있습니다)")

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device
            )

            # 모델 정보 출력
            embedding_dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"E5 임베딩 모델 로드 완료 - 차원: {embedding_dim}")
            print(f"[OK] E5 Embedding 초기화 완료")
            print(f"  - 모델: {self.model_name}")
            print(f"  - 차원: {embedding_dim}")
            print(f"  - 디바이스: {self.device}")

        except ImportError:
            raise ImportError(
                "sentence-transformers 패키지가 필요합니다.\n"
                "pip install sentence-transformers 로 설치하세요."
            )
        except Exception as e:
            logger.error(f"E5 모델 초기화 실패: {e}")
            raise

    def _add_prefix(self, texts: List[str], prefix: str) -> List[str]:
        """텍스트에 접두사 추가"""
        return [f"{prefix}: {text}" for text in texts]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서 임베딩 생성 (passage: 접두사 사용)

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            임베딩 벡터 리스트 (각 벡터는 1024차원)
        """
        if not texts:
            return []

        # "passage:" 접두사 추가
        prefixed_texts = self._add_prefix(texts, "passage")

        # 임베딩 생성
        embeddings = self._model.encode(
            prefixed_texts,
            normalize_embeddings=self.normalize_embeddings,
            batch_size=self.batch_size,
            show_progress_bar=self.show_progress and len(texts) > 10
        )

        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """
        검색 쿼리 임베딩 생성 (query: 접두사 사용)

        Args:
            text: 검색 쿼리 텍스트

        Returns:
            임베딩 벡터 (1024차원)
        """
        # "query:" 접두사 추가
        prefixed_text = f"query: {text}"

        # 임베딩 생성
        embedding = self._model.encode(
            prefixed_text,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False
        )

        return embedding.tolist()

    def get_embedding_dimension(self) -> int:
        """임베딩 차원 반환"""
        return self._model.get_sentence_embedding_dimension()


# 편의를 위한 팩토리 함수
def get_e5_embeddings(
    model_name: str = "intfloat/multilingual-e5-large",
    device: str = "cpu"
) -> E5Embeddings:
    """
    E5 임베딩 인스턴스 생성

    Args:
        model_name: 모델명 (기본: multilingual-e5-large)
        device: 실행 디바이스

    Returns:
        E5Embeddings 인스턴스
    """
    return E5Embeddings(model_name=model_name, device=device)
