"""
문서 서비스 세션 상태 관리

여러 서비스 간 공유되는 상태를 중앙 관리합니다.
"""

from typing import Dict, List, Optional, Set, TYPE_CHECKING
from collections import OrderedDict

if TYPE_CHECKING:
    from src.vectorstore.faiss_store import FAISSVectorStore
    from src.graph.quality_rag_graph import QualityRAGGraph


class DocumentSessionState:
    """
    문서 서비스의 공유 상태를 관리하는 클래스

    모든 하위 서비스(Loader, Search, Metadata 등)가 이 상태 객체를 공유하여
    상태 동기화 문제를 방지합니다.
    """

    def __init__(self):
        # 벡터스토어 관련
        self.vectorstore: Optional['FAISSVectorStore'] = None
        self.current_vectorstore: Optional['FAISSVectorStore'] = None  # 크롤링용

        # 다중 컬렉션 관리
        self.active_vectorstores: OrderedDict[str, 'FAISSVectorStore'] = OrderedDict()
        self.active_filenames: Optional[Set[str]] = None
        self.max_loaded_collections: int = 20

        # RAG 시스템
        self.rag: Optional['QualityRAGGraph'] = None

        # 문서 관련
        self.current_documents: List = []

        # 임베딩 모델
        self.embedding_model = None

        # 카테고리 관리자 (외부 주입)
        self.category_manager = None

    def reset_session(self) -> None:
        """세션 상태 초기화 (컬렉션 언로드)"""
        self.active_vectorstores.clear()
        self.active_filenames = None
        self.vectorstore = None
        self.rag = None
        self.current_documents = []

    def set_active_filenames(self, filenames: Optional[List[str]]) -> None:
        """활성 파일명 필터 설정"""
        self.active_filenames = set(filenames) if filenames else None

    def get_active_filenames(self) -> Optional[Set[str]]:
        """활성 파일명 필터 반환"""
        return self.active_filenames

    def add_vectorstore(self, collection_name: str, vectorstore: 'FAISSVectorStore') -> None:
        """벡터스토어 추가"""
        self.active_vectorstores[collection_name] = vectorstore
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """메모리 관리: 최대 로드 수 초과 시 가장 오래된 컬렉션 제거 (LRU)"""
        while len(self.active_vectorstores) > self.max_loaded_collections:
            oldest_collection = next(iter(self.active_vectorstores))
            del self.active_vectorstores[oldest_collection]
            print(f"[MEMORY] 컬렉션 언로드: {oldest_collection}")

    def has_active_vectorstores(self) -> bool:
        """활성 벡터스토어 존재 여부"""
        return bool(self.active_vectorstores)

    def get_first_vectorstore(self) -> Optional['FAISSVectorStore']:
        """첫 번째 활성 벡터스토어 반환"""
        if self.active_vectorstores:
            return next(iter(self.active_vectorstores.values()))
        return None
