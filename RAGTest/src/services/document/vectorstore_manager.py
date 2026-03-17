"""
벡터스토어 관리 서비스

컬렉션 로드, 언로드, 관리를 담당합니다.
"""

import os
from typing import Dict, List, Optional, Callable, TYPE_CHECKING
from collections import OrderedDict

if TYPE_CHECKING:
    from .session_state import DocumentSessionState


class VectorStoreManager:
    """벡터스토어 관리 서비스"""

    def __init__(
        self,
        state: 'DocumentSessionState',
        rag_initializer: Optional[Callable] = None
    ):
        """
        Args:
            state: 공유 상태 객체
            rag_initializer: RAG 초기화 콜백 (순환 참조 방지)
        """
        self.state = state
        self.rag_initializer = rag_initializer

    def set_rag_initializer(self, initializer: Callable) -> None:
        """RAG 초기화 콜백 설정 (지연 주입)"""
        self.rag_initializer = initializer

    def load_collection(self, collection_name: str) -> Dict:
        """
        저장된 컬렉션 활성화 (단일 컬렉션)

        Args:
            collection_name: 컬렉션 이름

        Returns:
            {'success': bool, 'stats': dict}
        """
        try:
            from src.vectorstore.faiss_store import FAISSVectorStore
            from langchain_core.documents import Document

            print(f"[LOG] 컬렉션 로드 시작: {collection_name}")

            emb_model = self.state.embedding_model
            if emb_model is None:
                return {'success': False, 'error': '임베딩 모델이 초기화되지 않았습니다.'}

            # 벡터 스토어 로드
            vectorstore = FAISSVectorStore(
                collection_name=collection_name,
                persist_directory="./data/faiss_web",
                embedding_function=emb_model
            )

            if not vectorstore.exists():
                return {'success': False, 'error': '컬렉션을 찾을 수 없습니다.'}

            self.state.vectorstore = vectorstore

            # 문서 메타데이터 업데이트
            doc_list = vectorstore.get_document_list()
            self.state.current_documents = [
                Document(
                    page_content="",
                    metadata={
                        "source": doc_info["filename"],
                        "category_id": doc_info.get("category_id", "general")
                    }
                )
                for doc_info in doc_list
            ]

            # RAG 초기화 (콜백 사용)
            if self.rag_initializer:
                self.rag_initializer(vectorstore, use_multi_collection=False)

            stats = vectorstore.get_stats()
            print(f"[LOG] 컬렉션 로드 완료: {collection_name}")

            return {
                'success': True,
                'message': f'컬렉션 "{collection_name}"이(가) 활성화되었습니다.',
                'stats': {
                    'documents': stats['document_count'],
                    'collection': collection_name
                }
            }

        except Exception as e:
            print(f"[ERROR] 컬렉션 로드 실패: {e}")
            return {'success': False, 'error': str(e)}

    def load_multiple_collections(
        self, collection_names: List[str], filenames: Optional[List[str]] = None
    ) -> Dict:
        """
        여러 컬렉션을 동시에 로드 (다중 문서 활성화)

        Args:
            collection_names: 로드할 컬렉션 이름 리스트
            filenames: 선택적 파일명 필터 리스트

        Returns:
            {'success': bool, 'loaded': int, 'failed': int, 'active_collections': list}
        """
        try:
            from src.vectorstore.faiss_store import FAISSVectorStore

            print(f"\n[LOG] 다중 컬렉션 로드 시작: {len(collection_names)}개")
            if filenames:
                print(f"[LOG] 파일명 필터 적용: {len(filenames)}개 파일")

            # 기존 활성화된 컬렉션 초기화
            if self.state.active_vectorstores:
                print(f"[LOG] 기존 활성화 컬렉션 초기화: {len(self.state.active_vectorstores)}개")
                self.state.active_vectorstores.clear()

            # 파일명 필터 설정
            self.state.set_active_filenames(filenames)
            print(f"[LOG] DEBUG - active_filenames set to: {self.state.active_filenames}")

            emb_model = self.state.embedding_model
            if emb_model is None:
                return {'success': False, 'error': '임베딩 모델이 초기화되지 않았습니다.'}

            persist_directory = "./data/faiss_web"
            loaded = 0
            failed = 0
            failed_collections = []

            for collection_name in collection_names:
                try:
                    vectorstore = self._load_single_collection(
                        collection_name, persist_directory, emb_model
                    )
                    if vectorstore:
                        self.state.add_vectorstore(collection_name, vectorstore)
                        loaded += 1
                    else:
                        failed += 1
                        failed_collections.append(collection_name)
                except Exception as e:
                    print(f"[ERROR] 컬렉션 로드 실패: {collection_name} - {e}")
                    failed += 1
                    failed_collections.append(collection_name)

            # RAG 초기화
            if self.state.has_active_vectorstores():
                self.state.vectorstore = self.state.get_first_vectorstore()
                if self.rag_initializer:
                    self.rag_initializer(self.state.vectorstore, use_multi_collection=True)
                print(f"[LOG] RAG 시스템 초기화 완료 (다중 컬렉션: {len(self.state.active_vectorstores)}개)")
            else:
                print(f"[WARN] 로드된 컬렉션이 없습니다.")
                self.state.vectorstore = None
                self.state.rag = None

            activated_doc_count = len(filenames) if filenames else loaded
            print(f"\n[LOG] 다중 컬렉션 로드 완료: 컬렉션 {loaded}개, 활성 문서 {activated_doc_count}개")

            return {
                'success': True,
                'loaded': activated_doc_count,
                'loaded_collections': loaded,
                'failed': failed,
                'failed_collections': failed_collections,
                'active_collections': list(self.state.active_vectorstores.keys())
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 다중 컬렉션 로드 실패: {e}")
            print(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'loaded': 0,
                'failed': len(collection_names)
            }

    def _load_single_collection(
        self, collection_name: str, persist_directory: str, emb_model
    ):
        """단일 컬렉션 로드"""
        from src.vectorstore.faiss_store import FAISSVectorStore

        print(f"[LOG] 컬렉션 로드 시작: {collection_name}")

        vectorstore = FAISSVectorStore(
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_function=emb_model
        )

        if not vectorstore.exists():
            print(f"[WARN] 컬렉션이 존재하지 않음: {collection_name}")
            return None

        print(f"[LOG] 컬렉션 로드 완료: {collection_name}")
        return vectorstore
