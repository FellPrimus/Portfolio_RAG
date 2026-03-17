"""
Hybrid Search 모듈

Semantic Search (Vector) + BM25 Keyword Search 결합
RRF (Reciprocal Rank Fusion) 알고리즘으로 점수 통합
"""

from typing import List, Tuple, Dict
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import numpy as np
from konlpy.tag import Okt  # 한국어 토크나이저


class HybridSearcher:
    """
    Hybrid Search: Vector + BM25 결합

    RRF (Reciprocal Rank Fusion) 알고리즘 사용
    """

    def __init__(
        self,
        vectorstore,
        alpha: float = 0.5,  # semantic search 가중치 (1-alpha = BM25 가중치)
        rrf_k: int = 60,     # RRF 파라미터
        use_konlpy: bool = True  # 한국어 형태소 분석기 사용 여부
    ):
        """
        HybridSearcher 초기화

        Args:
            vectorstore: FAISS 벡터 스토어 인스턴스
            alpha (float): Semantic Search 가중치 (0-1). 기본값 0.5
                - alpha=0.7: Semantic 70%, BM25 30%
                - alpha=0.5: Semantic 50%, BM25 50%
                - alpha=0.3: Semantic 30%, BM25 70%
            rrf_k (int): RRF(Reciprocal Rank Fusion) k 파라미터. 기본값 60
            use_konlpy (bool): KoNLPy 형태소 분석기 사용 여부
        """
        self.vectorstore = vectorstore
        self.alpha = alpha
        self.rrf_k = rrf_k
        self.use_konlpy = use_konlpy

        # BM25 인덱스
        self.bm25 = None
        self.documents: List[Document] = []

        # 한국어 토크나이저 초기화
        if use_konlpy:
            try:
                self.tokenizer = Okt()
                print("[OK] KoNLPy 토크나이저 초기화 완료")
            except Exception as e:
                print(f"[WARN] KoNLPy 초기화 실패. 공백 기반 토큰화로 대체합니다: {e}")
                self.use_konlpy = False
                self.tokenizer = None
        else:
            self.tokenizer = None

    def _tokenize(self, text: str) -> List[str]:
        """
        텍스트 토큰화

        Args:
            text: 토큰화할 텍스트

        Returns:
            List[str]: 토큰 리스트
        """
        if self.use_konlpy and self.tokenizer:
            try:
                # 명사, 동사, 형용사 추출 (한국어 형태소 분석)
                tokens = self.tokenizer.morphs(text, stem=True)
                return tokens
            except Exception as e:
                print(f"[WARN] 형태소 분석 실패, 공백 기반 토큰화 사용: {e}")
                return text.lower().split()
        else:
            # 공백 기반 토큰화 (폴백)
            return text.lower().split()

    def build_bm25_index(self, documents: List[Document]):
        """
        BM25 인덱스 구축

        Args:
            documents: 인덱싱할 Document 리스트
        """
        print(f"\n[BM25 인덱스 구축] {len(documents)}개 문서 토큰화 중...")

        self.documents = documents
        tokenized_docs = [self._tokenize(doc.page_content) for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)

        print(f"✓ BM25 인덱스 구축 완료: {len(documents)}개 문서")

    def _rrf_score(self, rank: int) -> float:
        """
        RRF 점수 계산

        RRF(rank) = 1 / (k + rank)
        rank가 낮을수록 (상위 결과일수록) 높은 점수

        Args:
            rank: 순위 (1부터 시작)

        Returns:
            float: RRF 점수
        """
        return 1.0 / (self.rrf_k + rank)

    def search(
        self,
        query: str,
        k: int = 10,
        semantic_k: int = 20,
        bm25_k: int = 20
    ) -> List[Tuple[Document, float]]:
        """
        Hybrid Search 실행

        Args:
            query: 검색 쿼리
            k: 최종 반환 문서 수
            semantic_k: Semantic Search에서 가져올 문서 수
            bm25_k: BM25에서 가져올 문서 수

        Returns:
            List[Tuple[Document, float]]: (문서, RRF 점수) 튜플 리스트
                점수가 높은 순으로 정렬됨

        Raises:
            ValueError: BM25 인덱스가 구축되지 않은 경우
        """
        if self.bm25 is None:
            raise ValueError(
                "BM25 인덱스가 구축되지 않았습니다. "
                "build_bm25_index()를 먼저 호출하세요."
            )

        # 1. Semantic Search (Vector Search)
        try:
            semantic_results = self.vectorstore.similarity_search_with_score(
                query, k=semantic_k
            )
        except Exception as e:
            print(f"[WARN] Semantic Search 실패: {e}")
            semantic_results = []

        # 2. BM25 Keyword Search
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # BM25 상위 k개 인덱스 추출
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:bm25_k]

        # 3. RRF (Reciprocal Rank Fusion) 점수 계산
        doc_scores: Dict[int, float] = {}  # doc_id -> RRF score
        doc_map: Dict[int, Document] = {}  # doc_id -> Document

        # Semantic Search 결과 처리
        for rank, (doc, distance) in enumerate(semantic_results):
            # 문서 고유 ID 생성 (page_content의 해시값 사용)
            doc_id = hash(doc.page_content)
            doc_map[doc_id] = doc

            # Semantic Search RRF 점수 (alpha 가중치 적용)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + self.alpha * self._rrf_score(rank + 1)

        # BM25 결과 처리
        for rank, idx in enumerate(top_bm25_indices):
            doc = self.documents[idx]
            doc_id = hash(doc.page_content)
            doc_map[doc_id] = doc

            # BM25 RRF 점수 ((1-alpha) 가중치 적용)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + (1 - self.alpha) * self._rrf_score(rank + 1)

        # 4. 점수순 정렬
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        # 상위 k개 반환
        results = [(doc_map[doc_id], score) for doc_id, score in sorted_docs[:k]]

        return results

    def update_documents(self, documents: List[Document]):
        """
        문서 업데이트 (BM25 인덱스 재구축)

        Args:
            documents: 새로운 문서 리스트
        """
        print(f"\n[BM25 인덱스 업데이트] {len(documents)}개 문서")
        self.build_bm25_index(documents)


# 사용 예제 및 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=== Hybrid Search 테스트 ===\n")

    # 더미 벡터 스토어 (실제로는 FAISS 사용)
    class DummyVectorStore:
        def __init__(self, docs):
            self.docs = docs

        def similarity_search_with_score(self, query, k=5):
            # 간단한 더미 검색 (실제로는 벡터 유사도 계산)
            import random
            results = [(doc, random.random()) for doc in self.docs[:k]]
            return results

    # 테스트 문서
    test_docs = [
        Document(page_content="Python은 간단하고 읽기 쉬운 프로그래밍 언어입니다."),
        Document(page_content="Python은 데이터 분석과 머신러닝에 널리 사용됩니다."),
        Document(page_content="Java는 객체지향 프로그래밍 언어입니다."),
        Document(page_content="JavaScript는 웹 개발을 위한 언어입니다."),
        Document(page_content="Python의 인기는 계속 증가하고 있습니다."),
        Document(page_content="프로그래밍 언어 중 Python이 가장 배우기 쉽습니다."),
    ]

    dummy_store = DummyVectorStore(test_docs)

    try:
        # Hybrid Searcher 초기화
        hybrid_searcher = HybridSearcher(
            vectorstore=dummy_store,
            alpha=0.5,  # Semantic 50%, BM25 50%
            use_konlpy=True
        )

        # BM25 인덱스 구축
        hybrid_searcher.build_bm25_index(test_docs)

        # 검색 실행
        query = "Python 프로그래밍 특징"
        print(f"\n쿼리: {query}")
        print("\nHybrid Search 실행 중...")

        results = hybrid_searcher.search(query, k=3)

        print(f"\n검색 결과 (상위 {len(results)}개):")
        for i, (doc, score) in enumerate(results):
            print(f"\n{i+1}. RRF 점수: {score:.4f}")
            print(f"   내용: {doc.page_content}")

        print("\n[SUCCESS] 테스트 완료!")

    except Exception as e:
        print(f"\n[ERROR] 에러: {e}")
        import traceback
        traceback.print_exc()
