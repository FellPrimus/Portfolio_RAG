"""
문서 메타데이터 관리 서비스

문서 목록 조회, 카테고리 변경 등 메타데이터 관련 작업을 담당합니다.
"""

import os
import json
from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .session_state import DocumentSessionState


class MetadataService:
    """문서 메타데이터 관리 서비스"""

    def __init__(self, state: 'DocumentSessionState'):
        self.state = state
        self._web_metadata_cache: Dict[str, Dict] = {}

    def get_loaded_documents(self) -> Dict:
        """
        현재 세션에 로드된 문서 목록 반환 (카테고리 정보 포함)

        Returns:
            {'success': bool, 'documents': list}
        """
        try:
            documents_info = []
            seen_files = set()

            # 다중 컬렉션 모드
            if self.state.active_vectorstores:
                documents_info = self._get_documents_from_active_vectorstores(seen_files)
            # 단일 컬렉션 모드 (하위 호환성)
            elif self.state.current_documents:
                documents_info = self._get_documents_from_current(seen_files)

            print(f"[LOG] 총 {len(documents_info)}개 문서 정보 반환")
            return {'success': True, 'documents': documents_info}

        except Exception as e:
            import traceback
            print(f"[ERROR] get_loaded_documents 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e), 'documents': []}

    def _get_documents_from_active_vectorstores(self, seen_files: set) -> List[Dict]:
        """활성 벡터스토어에서 문서 정보 추출"""
        documents_info = []
        print(f"[LOG] active_vectorstores에서 문서 정보 추출: {len(self.state.active_vectorstores)}개 컬렉션")

        # active_filenames가 있으면 직접 사용
        if self.state.active_filenames:
            print(f"[LOG] active_filenames 사용: {len(self.state.active_filenames)}개 파일")
            for filename in self.state.active_filenames:
                if filename not in seen_files:
                    seen_files.add(filename)
                    category_info = self._get_category_info_from_filename(filename)
                    documents_info.append({
                        'filename': filename,
                        'category': category_info
                    })
        else:
            # active_filenames가 없으면 전체 문서 조회
            for collection_name, vectorstore in self.state.active_vectorstores.items():
                try:
                    web_meta = self._load_web_metadata(collection_name)
                    docs = self._extract_documents_from_vectorstore(
                        vectorstore, collection_name, web_meta, seen_files
                    )
                    documents_info.extend(docs)
                except Exception as e:
                    print(f"[WARN] 컬렉션 {collection_name}에서 문서 정보 추출 실패: {e}")
                    continue

        return documents_info

    def _get_documents_from_current(self, seen_files: set) -> List[Dict]:
        """current_documents에서 문서 정보 추출 (하위 호환성)"""
        documents_info = []
        print(f"[LOG] current_documents에서 문서 정보 추출: {len(self.state.current_documents)}개")

        for doc in self.state.current_documents:
            if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                filename = os.path.basename(doc.metadata['source'])
                if filename not in seen_files:
                    seen_files.add(filename)
                    category_id = doc.metadata.get('category_id', 'general')
                    category_info = self._build_category_info(category_id)
                    documents_info.append({
                        'filename': filename,
                        'category': category_info
                    })

        return documents_info

    def _extract_documents_from_vectorstore(
        self, vectorstore, collection_name: str, web_meta: Dict, seen_files: set
    ) -> List[Dict]:
        """벡터스토어에서 문서 정보 추출"""
        documents = []

        if hasattr(vectorstore, 'vectorstore') and vectorstore.vectorstore:
            docstore = vectorstore.vectorstore.docstore
            for doc_id, doc in docstore._dict.items():
                if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                    filename = os.path.basename(doc.metadata['source'])
                    if filename not in seen_files:
                        seen_files.add(filename)

                        category_id = doc.metadata.get('category_id', 'general')
                        if filename in web_meta and 'category_id' in web_meta[filename]:
                            category_id = web_meta[filename]['category_id']

                        category_info = self._build_category_info(category_id)
                        documents.append({
                            'filename': filename,
                            'category': category_info
                        })

        return documents

    def _load_web_metadata(self, collection_name: str) -> Dict:
        """웹 크롤링 메타데이터 파일 로드 (캐싱)"""
        if collection_name in self._web_metadata_cache:
            return self._web_metadata_cache[collection_name]

        metadata_path = f"./data/faiss_web/{collection_name}_metadata.json"
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self._web_metadata_cache[collection_name] = json.load(f)
            except Exception:
                self._web_metadata_cache[collection_name] = {}
        else:
            self._web_metadata_cache[collection_name] = {}

        return self._web_metadata_cache[collection_name]

    def _get_category_info_from_filename(self, filename: str) -> Dict:
        """파일명에서 카테고리 정보 추출"""
        if ':' in filename:
            category_id = filename.split(':')[0]
        else:
            category_id = 'general'
        return self._build_category_info(category_id)

    def _build_category_info(self, category_id: str) -> Dict:
        """카테고리 정보 구성"""
        default_info = {'id': 'general', 'name': '일반', 'color': '#6366f1', 'icon': '📄'}

        if self.state.category_manager:
            category = self.state.category_manager.get_category(category_id)
            if category:
                return {
                    'id': category_id,
                    'name': category['name'],
                    'color': category['color'],
                    'icon': category['icon']
                }
        return default_info

    def get_all_documents_from_vectordb(self) -> Dict:
        """
        벡터DB에 저장된 모든 문서 목록 조회
        file_metadata.json을 주 데이터 소스로 사용

        Returns:
            {'success': bool, 'documents': list}
        """
        try:
            all_documents = []

            # 1. file_metadata.json 읽기
            file_metadata_path = "./data/file_metadata.json"
            if not os.path.exists(file_metadata_path):
                return {'success': True, 'documents': []}

            with open(file_metadata_path, 'r', encoding='utf-8') as f:
                file_metadata = json.load(f)

            # 2. folders.json에서 document_folder_map 읽기
            folders_path = "./data/folders.json"
            document_folder_map = {}
            if os.path.exists(folders_path):
                with open(folders_path, 'r', encoding='utf-8') as f:
                    folders_data = json.load(f)
                    document_folder_map = folders_data.get('document_folder_map', {})

            # 3. 각 문서 정보 구성
            for doc_id, info in file_metadata.items():
                doc_info = self._build_document_info(doc_id, info, document_folder_map)
                all_documents.append(doc_info)

            return {'success': True, 'documents': all_documents}

        except Exception as e:
            import traceback
            print(f"[ERROR] 문서 목록 조회 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e), 'documents': []}

    def _build_document_info(self, doc_id: str, info: Dict, folder_map: Dict) -> Dict:
        """단일 문서 정보 구성"""
        category_id = info.get("category_id", "general")
        category_info = self._build_category_info(category_id)
        folder_id = folder_map.get(doc_id)

        # 날짜 포맷팅
        added_at = info.get('uploaded_at') or info.get('upload_time')
        if isinstance(added_at, (int, float)):
            added_at = datetime.fromtimestamp(added_at).strftime('%Y-%m-%d %H:%M:%S')
        updated_at = info.get('updated_at') or added_at

        # 표시 이름
        display_name = info.get('display_name') or info.get('filename') or doc_id

        # 청크 수 결정
        doc_type = info.get("doc_type", "")
        if doc_type == "file_upload":
            chunk_count = info.get("chunk_count", 0)
        else:
            chunk_count = info.get("chunk_count") or info.get("file_size", 0)

        return {
            "filename": doc_id,
            "display_name": display_name,
            "title": info.get("title", ""),
            "chunk_count": chunk_count,
            "page_count": info.get("page_count", 1),
            "added_at": added_at or "Unknown",
            "updated_at": updated_at or "Unknown",
            "collection": "documents",
            "category": category_info,
            "folder_id": folder_id,
            "doc_type": info.get("doc_type", "uploaded"),
            "service_name": info.get("service_name", "")
        }

    def update_document_category(
        self, filename: str, collection: str, category_id: str
    ) -> Dict:
        """
        벡터DB에 저장된 문서의 카테고리 변경

        Args:
            filename: 파일명
            collection: 컬렉션 이름
            category_id: 새 카테고리 ID

        Returns:
            {'success': bool, 'message': str}
        """
        try:
            if not filename or not collection or not category_id:
                return {'success': False, 'error': '파일명, 컬렉션, 카테고리 ID가 필요합니다.'}

            persist_directory = "./data/faiss_web"
            metadata_file = os.path.join(persist_directory, f"{collection}_metadata.json")

            if not os.path.exists(metadata_file):
                return {'success': False, 'error': '컬렉션을 찾을 수 없습니다.'}

            # 메타데이터 업데이트
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            if filename not in metadata:
                return {'success': False, 'error': '문서를 찾을 수 없습니다.'}

            metadata[filename]['category_id'] = category_id

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # FAISS docstore 메타데이터 업데이트
            updated_count = self._update_faiss_category(
                filename, collection, category_id, persist_directory
            )

            return {
                'success': True,
                'message': f'문서 "{filename}"의 카테고리가 변경되었습니다. ({updated_count}개 청크 업데이트)'
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 카테고리 변경 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _update_faiss_category(
        self, filename: str, collection: str, category_id: str, persist_directory: str
    ) -> int:
        """FAISS docstore의 카테고리 메타데이터 업데이트"""
        from src.vectorstore.faiss_store import FAISSVectorStore

        print(f"[LOG] FAISS docstore 메타데이터 업데이트 중: {filename} -> {category_id}")

        # 임베딩 모델 가져오기
        emb_model = self.state.embedding_model
        if emb_model is None:
            print(f"[WARN] 임베딩 모델이 없습니다. 메타데이터 JSON만 업데이트되었습니다.")
            return 0

        temp_vectorstore = FAISSVectorStore(
            collection_name=collection,
            persist_directory=persist_directory,
            embedding_function=emb_model
        )

        if temp_vectorstore.vectorstore is None or not temp_vectorstore.exists():
            print(f"[WARN] FAISS 인덱스를 찾을 수 없습니다.")
            return 0

        # 서비스 레벨 문서 확인
        is_service_doc = ':' in filename and not filename.startswith('http')
        service_name = None
        if is_service_doc:
            parts = filename.split(':', 1)
            if len(parts) == 2:
                service_name = parts[1]

        # docstore 업데이트
        updated_count = 0
        for doc_id, doc in temp_vectorstore.vectorstore.docstore._dict.items():
            if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                should_update = self._should_update_doc(
                    doc, filename, is_service_doc, service_name
                )
                if should_update:
                    doc.metadata['category_id'] = category_id
                    updated_count += 1

        if updated_count > 0:
            temp_vectorstore.save()
            print(f"[LOG] FAISS docstore 업데이트 완료: {updated_count}개 청크")

            # 활성 vectorstore도 업데이트
            self._update_active_vectorstore_category(
                filename, collection, category_id, is_service_doc, service_name
            )

        return updated_count

    def _should_update_doc(
        self, doc, filename: str, is_service_doc: bool, service_name: Optional[str]
    ) -> bool:
        """문서 업데이트 여부 판단"""
        source = doc.metadata.get('source', '')

        if is_service_doc and service_name:
            return doc.metadata.get('service_name', '') == service_name
        else:
            return os.path.basename(source) == filename

    def _update_active_vectorstore_category(
        self, filename: str, collection: str, category_id: str,
        is_service_doc: bool, service_name: Optional[str]
    ) -> None:
        """현재 활성화된 vectorstore 메타데이터도 업데이트"""
        if self.state.vectorstore and self.state.vectorstore.collection_name == collection:
            print(f"[LOG] 현재 활성화된 vectorstore 메타데이터도 업데이트 중...")

            for doc_id, doc in self.state.vectorstore.vectorstore.docstore._dict.items():
                if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                    should_update = self._should_update_doc(
                        doc, filename, is_service_doc, service_name
                    )
                    if should_update:
                        doc.metadata['category_id'] = category_id

            print(f"[LOG] 활성화된 vectorstore 메타데이터 업데이트 완료")
