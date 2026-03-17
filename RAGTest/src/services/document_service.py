"""
문서 관리 서비스 (파사드)

문서 로드, 벡터 스토어 관리, RAG 시스템 등의 비즈니스 로직을 담당합니다.
하위 서비스들에 위임하여 단일 책임 원칙을 준수합니다.

리팩토링 버전: 2026-01-12
"""

import os
from typing import Dict, List, Optional

# 하위 서비스 모듈
from src.services.document.session_state import DocumentSessionState
from src.services.document.metadata_service import MetadataService
from src.services.document.chunk_service import ChunkService
from src.services.document.search_service import SearchService
from src.services.document.vectorstore_manager import VectorStoreManager
from src.services.document.loader_service import LoaderService

# 외부 의존성
from src.vectorstore.faiss_store import FAISSVectorStore
from src.graph.quality_rag_graph import QualityRAGGraph


class DocumentService:
    """
    문서 처리 및 RAG 시스템 관리 서비스 (파사드)

    기존 API를 100% 유지하면서 내부적으로 분리된 서비스들에 위임합니다.
    """

    def __init__(self, category_manager=None):
        """
        Args:
            category_manager: CategoryManager 인스턴스
        """
        # 공유 상태 객체 생성
        self._state = DocumentSessionState()
        self._state.category_manager = category_manager

        # 하위 서비스 초기화
        self._metadata_service = MetadataService(self._state)
        self._chunk_service = ChunkService(self._state)
        self._search_service = SearchService(self._state)
        self._vectorstore_manager = VectorStoreManager(self._state)
        self._loader_service = LoaderService(self._state)

        # RAG 초기화 콜백 설정
        self._vectorstore_manager.set_rag_initializer(self._create_rag)
        self._loader_service.set_rag_initializer(self._create_rag)

    # ========================================
    # 하위 호환성을 위한 속성 접근자
    # ========================================

    @property
    def vectorstore(self):
        return self._state.vectorstore

    @vectorstore.setter
    def vectorstore(self, value):
        self._state.vectorstore = value

    @property
    def current_vectorstore(self):
        return self._state.current_vectorstore

    @current_vectorstore.setter
    def current_vectorstore(self, value):
        self._state.current_vectorstore = value

    @property
    def active_vectorstores(self):
        return self._state.active_vectorstores

    @property
    def active_filenames(self):
        return self._state.active_filenames

    @active_filenames.setter
    def active_filenames(self, value):
        self._state.active_filenames = value

    @property
    def rag(self):
        return self._state.rag

    @rag.setter
    def rag(self, value):
        self._state.rag = value

    @property
    def current_documents(self):
        return self._state.current_documents

    @current_documents.setter
    def current_documents(self, value):
        self._state.current_documents = value

    @property
    def embedding_model(self):
        return self._state.embedding_model

    @embedding_model.setter
    def embedding_model(self, value):
        self._state.embedding_model = value

    @property
    def category_manager(self):
        return self._state.category_manager

    @property
    def max_loaded_collections(self):
        return self._state.max_loaded_collections

    # ========================================
    # 임베딩 모델 초기화
    # ========================================

    def init_embedding_model(self):
        """임베딩 모델 사전 로드"""
        if self._state.embedding_model is None:
            print("\n[LOG] Embedding model loading...")
            from src.utils import get_embeddings
            embedding_provider = os.getenv("EMBEDDING_PROVIDER", "huggingface")
            self._state.embedding_model = get_embeddings(provider=embedding_provider)
            print("[LOG] Embedding model ready\n")
        return self._state.embedding_model

    # ========================================
    # RAG 초기화 (내부 사용)
    # ========================================

    def _create_rag(self, vectorstore, use_multi_collection: bool = False):
        """RAG 시스템 초기화 (통일된 방식)"""
        llm_provider = os.getenv("LLM_PROVIDER", "clovax")
        self._state.rag = QualityRAGGraph(
            vectorstore=vectorstore,
            retrieval_k=5,
            max_retries=2,
            min_quality_score=0.6,
            llm_provider=llm_provider,
            category_manager=self._state.category_manager,
            doc_service=self if use_multi_collection else None
        )

    # ========================================
    # 문서 로드 API (LoaderService에 위임)
    # ========================================

    def load_documents(self, file_paths: List[str], chunk_config: Optional[Dict] = None) -> Dict:
        """문서 로드 및 메인 벡터 스토어에 저장"""
        self.init_embedding_model()
        return self._loader_service.load_documents(file_paths, chunk_config)

    def load_text(self, title: str, content: str, category_id: str = 'general') -> Dict:
        """텍스트 직접 입력 및 벡터DB 저장"""
        self.init_embedding_model()
        return self._loader_service.load_text(title, content, category_id)

    # ========================================
    # 컬렉션 관리 API (VectorStoreManager에 위임)
    # ========================================

    def load_collection(self, collection_name: str) -> Dict:
        """저장된 컬렉션 활성화"""
        self.init_embedding_model()
        return self._vectorstore_manager.load_collection(collection_name)

    def load_multiple_collections(
        self, collection_names: List[str], filenames: List[str] = None
    ) -> Dict:
        """여러 컬렉션을 동시에 로드"""
        self.init_embedding_model()
        return self._vectorstore_manager.load_multiple_collections(collection_names, filenames)

    # ========================================
    # 검색 API (SearchService에 위임)
    # ========================================

    def multi_collection_search(self, query: str, k: int = 5) -> List:
        """모든 활성화된 컬렉션에서 검색"""
        return self._search_service.multi_collection_search(query, k)

    # ========================================
    # 메타데이터 API (MetadataService에 위임)
    # ========================================

    def get_loaded_documents(self) -> Dict:
        """현재 세션에 로드된 문서 목록 반환"""
        return self._metadata_service.get_loaded_documents()

    def get_all_documents_from_vectordb(self) -> Dict:
        """벡터DB에 저장된 모든 문서 목록 조회"""
        return self._metadata_service.get_all_documents_from_vectordb()

    def update_document_category(
        self, filename: str, collection: str, category_id: str
    ) -> Dict:
        """벡터DB에 저장된 문서의 카테고리 변경"""
        self.init_embedding_model()
        return self._metadata_service.update_document_category(filename, collection, category_id)

    # ========================================
    # 청크 조회 API (ChunkService에 위임)
    # ========================================

    def get_document_chunks_preview(
        self, filename: str, collection: str, limit: int = 3
    ) -> Dict:
        """특정 문서의 청크 미리보기 조회"""
        self.init_embedding_model()
        return self._chunk_service.get_document_chunks_preview(filename, collection, limit)

    def get_document_chunks_all(
        self, filename: str, collection: str, page: int = 1, per_page: int = 10
    ) -> Dict:
        """특정 문서의 전체 청크 조회 (페이지네이션)"""
        self.init_embedding_model()
        return self._chunk_service.get_document_chunks_all(filename, collection, page, per_page)

    # ========================================
    # RAG 질의 API
    # ========================================

    def query(self, question: str) -> Dict:
        """RAG 질의응답"""
        try:
            if self._state.rag is None:
                return {'success': False, 'error': '먼저 문서를 로드해주세요.'}

            if not question.strip():
                return {'success': False, 'error': '질문을 입력해주세요.'}

            result = self._state.rag.query(question)

            sources = []
            for doc in result.get('retrieved_docs', []):
                sources.append({
                    'content': doc.page_content[:200] + '...',
                    'source': os.path.basename(doc.metadata.get('source', 'N/A'))
                })

            return {
                'success': True,
                'answer': result.get('answer', ''),
                'sources': sources,
                'quality_score': result.get('quality_score', 0),
                'confidence': result.get('confidence', 'unknown'),
                'retry_count': result.get('retry_count', 0),
                'steps': result.get('steps', []),
                'warnings': result.get('warnings', []),
                'session_id': result.get('session_id', ''),
                'processing_time': result.get('processing_time', 0),
                'used_model': result.get('used_model', 'N/A'),
                'model_selection_reason': result.get('model_selection_reason', ''),
                'original_question': result.get('original_question', question),
                'search_queries': result.get('search_queries', [question]),
                'query_type': result.get('query_type', ''),
                'retrieval_config': result.get('retrieval_config', {}),
                'hybrid_search_used': result.get('hybrid_search_used', False),
                'semantic_chunking_used': result.get('semantic_chunking_used', False),
                'self_rag_verification': result.get('self_rag_verification', {}),
                'hallucination_detected': result.get('hallucination_detected', False),
                'rerank_scores': result.get('rerank_scores', None)
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 질의 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    # ========================================
    # 상태 조회 API
    # ========================================

    def get_status(self) -> Dict:
        """현재 시스템 상태 조회"""
        is_ready = self._state.rag is not None and self._state.vectorstore is not None

        stats = {}
        if is_ready:
            stats = self._state.vectorstore.get_stats()

        documents_loaded = 0
        if self._state.active_vectorstores:
            seen_files = set()
            for collection_name, vectorstore in self._state.active_vectorstores.items():
                if hasattr(vectorstore, 'vectorstore') and vectorstore.vectorstore:
                    for doc_id, doc in vectorstore.vectorstore.docstore._dict.items():
                        if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                            filename = os.path.basename(doc.metadata['source'])
                            seen_files.add(filename)
            documents_loaded = len(seen_files)
        elif self._state.current_documents:
            documents_loaded = len(self._state.current_documents)

        return {
            'ready': is_ready,
            'documents_loaded': documents_loaded,
            'llm_provider': os.getenv("LLM_PROVIDER", "clovax"),
            'stats': stats
        }

    # ========================================
    # 삭제 API (기존 로직 유지)
    # ========================================

    def delete_all_documents(self) -> Dict:
        """모든 문서 데이터 삭제"""
        try:
            import shutil
            import gc

            persist_directory = "./data/faiss_web"

            # 메모리 참조 해제
            print("[LOG] 벡터스토어 메모리 참조 해제 중...")

            if self._state.vectorstore is not None:
                if hasattr(self._state.vectorstore, 'vectorstore'):
                    self._state.vectorstore.vectorstore = None
                self._state.vectorstore = None

            if self._state.current_vectorstore is not None:
                if hasattr(self._state.current_vectorstore, 'vectorstore'):
                    self._state.current_vectorstore.vectorstore = None
                self._state.current_vectorstore = None

            if self._state.active_vectorstores:
                for collection_name in list(self._state.active_vectorstores.keys()):
                    vs = self._state.active_vectorstores[collection_name]
                    if hasattr(vs, 'vectorstore'):
                        vs.vectorstore = None
                self._state.active_vectorstores.clear()

            self._state.rag = None
            self._state.current_documents = []
            gc.collect()

            if not os.path.exists(persist_directory):
                return {'success': True, 'message': '삭제할 데이터가 없습니다.'}

            # 디렉토리 삭제
            deleted_collections = []
            for filename in os.listdir(persist_directory):
                file_path = os.path.join(persist_directory, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        deleted_collections.append(filename)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        deleted_collections.append(filename)
                except Exception as e:
                    print(f"[WARN] 파일 삭제 실패: {filename} - {e}")

            return {
                'success': True,
                'message': f'{len(deleted_collections)}개 항목이 삭제되었습니다.'
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 문서 삭제 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def delete_document(self, filename: str, is_crawled: bool = False) -> Dict:
        """벡터DB에서 특정 문서 삭제"""
        try:
            import json

            persist_directory = "./data/faiss_web"
            collection_name = "web_crawled" if is_crawled else "documents"

            # 메타데이터 파일 경로
            metadata_file = os.path.join(persist_directory, f"{collection_name}_metadata.json")

            if not os.path.exists(metadata_file):
                return {'success': False, 'error': '컬렉션을 찾을 수 없습니다.'}

            # 메타데이터에서 삭제
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            if filename not in metadata:
                return {'success': False, 'error': '문서를 찾을 수 없습니다.'}

            del metadata[filename]

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # file_metadata.json에서도 삭제
            file_metadata_path = "./data/file_metadata.json"
            if os.path.exists(file_metadata_path):
                with open(file_metadata_path, 'r', encoding='utf-8') as f:
                    file_metadata = json.load(f)

                if filename in file_metadata:
                    del file_metadata[filename]
                    with open(file_metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(file_metadata, f, ensure_ascii=False, indent=2)

            return {
                'success': True,
                'message': f'문서 "{filename}"이(가) 삭제되었습니다.'
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 문서 삭제 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}
