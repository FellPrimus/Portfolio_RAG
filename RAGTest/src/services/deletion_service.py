"""
통합 삭제 서비스

원본 파일, 벡터 DB, 메타데이터를 일관되게 삭제하는 서비스
"""
from typing import Dict, List, Optional
from enum import Enum
import os
import glob
import json
import shutil
import logging

logger = logging.getLogger(__name__)


class DeletionScope(str, Enum):
    """삭제 범위 Enum"""
    VECTOR_ONLY = "vector_only"      # 벡터 DB만 삭제
    FILE_ONLY = "file_only"          # 원본 파일만 삭제
    ALL = "all"                      # 모두 삭제 (기본값)


class DeletionResult:
    """삭제 결과를 담는 데이터 클래스"""
    def __init__(self):
        self.success = True
        self.deleted = {
            'original_file': False,
            'vector_chunks': False,
            'file_metadata': False,
            'document_metadata': False
        }
        self.errors: List[str] = []
        self.details: Dict = {}

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'deleted': self.deleted,
            'errors': self.errors,
            'details': self.details
        }


class DeletionService:
    """
    통합 삭제 서비스

    원본 파일, 벡터 DB 청크, 메타데이터를 일관되게 삭제한다.
    """

    def __init__(
        self,
        file_service=None,
        document_service=None,
        documents_dir: str = "./documents",
        faiss_dir: str = "./data/faiss_web",
        html_dir: str = "./html",
        file_metadata_path: str = "./data/file_metadata.json"
    ):
        """
        Args:
            file_service: FileService 인스턴스 (선택적)
            document_service: DocumentService 인스턴스 (선택적)
            documents_dir: 원본 문서 디렉토리 경로
            faiss_dir: FAISS 벡터 DB 디렉토리 경로
            html_dir: HTML 파일 디렉토리 경로 (크롤링 문서)
            file_metadata_path: 파일 메타데이터 JSON 경로
        """
        self.file_service = file_service
        self.document_service = document_service
        self.documents_dir = documents_dir
        self.faiss_dir = faiss_dir
        self.html_dir = html_dir
        self.file_metadata_path = file_metadata_path

    def delete_document(
        self,
        filename: str,
        collection: Optional[str] = None,
        scope: DeletionScope = DeletionScope.ALL
    ) -> Dict:
        """
        단일 문서 삭제

        Args:
            filename: 삭제할 파일명
            collection: 벡터 DB 컬렉션명 (None이면 자동 탐색)
            scope: 삭제 범위 (DeletionScope)

        Returns:
            {
                'success': bool,
                'deleted': {
                    'original_file': bool,
                    'vector_chunks': bool,
                    'file_metadata': bool,
                    'document_metadata': bool
                },
                'errors': list,
                'details': dict
            }
        """
        result = DeletionResult()

        try:
            logger.info(f"문서 삭제 시작: {filename}, scope={scope.value}")

            # 1. 원본 파일 삭제
            if scope in [DeletionScope.FILE_ONLY, DeletionScope.ALL]:
                file_result = self._delete_original_file(filename)
                result.deleted['original_file'] = file_result['success']
                if not file_result['success'] and file_result.get('error'):
                    result.errors.append(f"원본 파일: {file_result['error']}")
                if file_result.get('path'):
                    result.details['deleted_file_path'] = file_result['path']

            # 2. 벡터 DB에서 삭제
            if scope in [DeletionScope.VECTOR_ONLY, DeletionScope.ALL]:
                vector_result = self._delete_from_vectordb(filename, collection)
                result.deleted['vector_chunks'] = vector_result['success']
                result.deleted['document_metadata'] = vector_result.get('metadata_deleted', False)
                if not vector_result['success'] and vector_result.get('error'):
                    result.errors.append(f"벡터 DB: {vector_result['error']}")
                if vector_result.get('deleted_chunks'):
                    result.details['deleted_chunks'] = vector_result['deleted_chunks']
                if vector_result.get('collection'):
                    result.details['collection'] = vector_result['collection']

            # 3. 파일 메타데이터 삭제
            if scope in [DeletionScope.FILE_ONLY, DeletionScope.ALL]:
                meta_result = self._delete_file_metadata(filename)
                result.deleted['file_metadata'] = meta_result['success']

            # 전체 성공 여부 판단
            if result.errors:
                # 부분 성공: 일부만 삭제된 경우
                if any(result.deleted.values()):
                    result.success = True  # 부분 성공도 성공으로 처리
                    logger.warning(f"문서 부분 삭제: {filename} - {result.errors}")
                else:
                    result.success = False

            logger.info(f"문서 삭제 완료: {filename} - {result.deleted}")
            return result.to_dict()

        except Exception as e:
            logger.exception(f"문서 삭제 실패: {filename}")
            result.success = False
            result.errors.append(str(e))
            return result.to_dict()

    def delete_all_documents(
        self,
        scope: DeletionScope = DeletionScope.ALL
    ) -> Dict:
        """
        모든 문서 삭제

        Args:
            scope: 삭제 범위

        Returns:
            {
                'success': bool,
                'deleted_count': {
                    'original_files': int,
                    'collections': int,
                    'html_files': int
                },
                'errors': list
            }
        """
        result = {
            'success': True,
            'deleted_count': {
                'original_files': 0,
                'collections': 0,
                'html_files': 0
            },
            'errors': []
        }

        try:
            logger.info(f"전체 문서 삭제 시작: scope={scope.value}")

            # 1. 원본 파일 삭제
            if scope in [DeletionScope.FILE_ONLY, DeletionScope.ALL]:
                files_result = self._delete_all_original_files()
                result['deleted_count']['original_files'] = files_result.get('count', 0)
                result['deleted_count']['html_files'] = files_result.get('html_count', 0)
                if files_result.get('errors'):
                    result['errors'].extend(files_result['errors'])

            # 2. 벡터 DB 전체 삭제
            if scope in [DeletionScope.VECTOR_ONLY, DeletionScope.ALL]:
                vector_result = self._delete_all_vectordb()
                result['deleted_count']['collections'] = vector_result.get('count', 0)
                if vector_result.get('error'):
                    result['errors'].append(vector_result['error'])

            # 3. 메타데이터 초기화
            if scope == DeletionScope.ALL:
                self._reset_all_metadata()

            if result['errors']:
                result['success'] = False

            logger.info(f"전체 문서 삭제 완료: {result['deleted_count']}")
            return result

        except Exception as e:
            logger.exception("전체 문서 삭제 실패")
            return {
                'success': False,
                'error': str(e),
                'deleted_count': result['deleted_count']
            }

    # ========== Private Methods ==========

    def _delete_original_file(self, filename: str) -> Dict:
        """
        원본 파일 삭제

        documents/, html/ 디렉토리에서 파일을 찾아 삭제한다.
        """
        # 1. documents/ 디렉토리에서 검색
        if os.path.exists(self.documents_dir):
            for root, dirs, files in os.walk(self.documents_dir):
                if filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        os.remove(filepath)
                        logger.info(f"원본 파일 삭제: {filepath}")
                        return {'success': True, 'path': filepath}
                    except Exception as e:
                        return {'success': False, 'error': str(e)}

        # 2. html/ 디렉토리에서 검색 (크롤링 문서)
        if os.path.exists(self.html_dir):
            html_path = os.path.join(self.html_dir, filename)
            if os.path.exists(html_path):
                try:
                    os.remove(html_path)
                    logger.info(f"HTML 파일 삭제: {html_path}")
                    return {'success': True, 'path': html_path}
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            # .html 확장자 추가하여 검색
            if not filename.endswith('.html'):
                html_path = os.path.join(self.html_dir, f"{filename}.html")
                if os.path.exists(html_path):
                    try:
                        os.remove(html_path)
                        logger.info(f"HTML 파일 삭제: {html_path}")
                        return {'success': True, 'path': html_path}
                    except Exception as e:
                        return {'success': False, 'error': str(e)}

        # 파일을 찾지 못한 경우 (에러는 아님 - 이미 삭제되었을 수 있음)
        logger.warning(f"원본 파일을 찾을 수 없음: {filename}")
        return {'success': False, 'error': '파일을 찾을 수 없습니다.'}

    def _delete_from_vectordb(
        self,
        filename: str,
        collection: Optional[str] = None
    ) -> Dict:
        """
        벡터 DB에서 문서 삭제

        모든 컬렉션을 스캔하여 해당 파일의 청크를 삭제한다.
        """
        if not os.path.exists(self.faiss_dir):
            return {'success': False, 'error': '벡터 DB 디렉토리가 없습니다.'}

        # 모든 메타데이터 파일 검색
        metadata_files = glob.glob(f"{self.faiss_dir}/*_metadata.json")

        for metadata_file in metadata_files:
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # 파일명으로 검색 (정확히 일치 또는 basename 비교)
                found_key = None
                for key in metadata.keys():
                    if key == filename or os.path.basename(key) == filename:
                        found_key = key
                        break

                if found_key:
                    target_collection = os.path.basename(metadata_file).replace('_metadata.json', '')

                    # 특정 컬렉션이 지정된 경우 확인
                    if collection and target_collection != collection:
                        continue

                    chunk_count = metadata[found_key].get('chunk_count', 0)

                    # 메타데이터에서 제거
                    del metadata[found_key]

                    # 메타데이터 파일 저장
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=2)

                    logger.info(f"벡터 DB 메타데이터 삭제: {filename} (컬렉션: {target_collection})")

                    # FAISS 인덱스에서도 실제 벡터 삭제 시도
                    # (FAISSVectorStore.delete_document_by_filename 호출)
                    vector_deleted = self._delete_vectors_from_faiss(
                        filename,
                        target_collection
                    )

                    return {
                        'success': True,
                        'metadata_deleted': True,
                        'vectors_deleted': vector_deleted,
                        'deleted_chunks': chunk_count,
                        'collection': target_collection
                    }

            except Exception as e:
                logger.error(f"메타데이터 처리 실패: {metadata_file} - {e}")
                continue

        return {'success': False, 'error': '문서를 찾을 수 없습니다.'}

    def _delete_vectors_from_faiss(self, filename: str, collection: str) -> bool:
        """
        FAISS 인덱스에서 실제 벡터 삭제

        Note: FAISS는 벡터 삭제가 비효율적이므로,
              인덱스 재구성이 필요할 수 있다.
        """
        try:
            # DocumentService가 있으면 활용
            if self.document_service:
                # active_vectorstores에서 해당 컬렉션 찾기
                if hasattr(self.document_service, 'active_vectorstores'):
                    if collection in self.document_service.active_vectorstores:
                        vectorstore = self.document_service.active_vectorstores[collection]

                        # FAISS 인덱스 재구성 (벡터 실제 삭제)
                        return self._rebuild_faiss_without_document(
                            vectorstore,
                            filename,
                            collection
                        )

            # 직접 FAISS 파일 조작은 복잡하므로
            # 메타데이터만 삭제하고 실제 벡터는 남겨둠
            # (검색 시 메타데이터 기반 필터링으로 처리)
            logger.warning(f"FAISS 벡터 직접 삭제 생략: {filename}")
            return False

        except Exception as e:
            logger.error(f"FAISS 벡터 삭제 실패: {e}")
            return False

    def _rebuild_faiss_without_document(
        self,
        vectorstore,
        filename: str,
        collection: str
    ) -> bool:
        """
        특정 문서를 제외하고 FAISS 인덱스 재구성

        Args:
            vectorstore: FAISS vectorstore 인스턴스
            filename: 제외할 파일명
            collection: 컬렉션명
        """
        try:
            from langchain_core.documents import Document
            from langchain_community.vectorstores import FAISS
            from src.utils import get_embeddings

            # 서비스 레벨 문서 ID 패턴 확인 (예: "guide:Server")
            is_service_doc = ':' in filename and not filename.startswith('http')
            service_name = None
            if is_service_doc:
                parts = filename.split(':', 1)
                if len(parts) == 2:
                    service_name = parts[1]
                    logger.info(f"서비스 문서 삭제: service_name='{service_name}'")

            # 1. 삭제할 문서의 source 경로 찾기
            target_sources = []
            for doc_id, doc in vectorstore.docstore._dict.items():
                source = doc.metadata.get('source', '')
                should_delete = False

                # 서비스 레벨 문서인 경우: service_name 메타데이터로 매칭
                if is_service_doc and service_name:
                    doc_service_name = doc.metadata.get('service_name', '')
                    if doc_service_name == service_name:
                        should_delete = True
                # 일반 파일인 경우: 기존 로직 (substring 또는 basename)
                elif filename in source or os.path.basename(source) == filename:
                    should_delete = True

                if should_delete:
                    target_sources.append(source)

            if not target_sources:
                logger.warning(f"docstore에서 {filename}을 찾을 수 없음")
                return False

            target_sources = list(set(target_sources))  # 중복 제거
            logger.info(f"삭제 대상 source: {target_sources}")

            # 2. 남길 문서들 수집
            remaining_docs = []
            for doc_id, doc in vectorstore.docstore._dict.items():
                source = doc.metadata.get('source', '')
                if source not in target_sources:
                    remaining_docs.append(doc)

            logger.info(f"남은 문서: {len(remaining_docs)}개 청크")

            # 3. 컬렉션이 비는 경우 처리
            if len(remaining_docs) == 0:
                # FAISS 파일 삭제
                faiss_files = [
                    os.path.join(self.faiss_dir, f"{collection}.faiss"),
                    os.path.join(self.faiss_dir, f"{collection}.pkl"),
                    os.path.join(self.faiss_dir, f"{collection}_metadata.json")
                ]

                for filepath in faiss_files:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"FAISS 파일 삭제: {filepath}")

                # active_vectorstores에서 제거
                if hasattr(self.document_service, 'active_vectorstores'):
                    if collection in self.document_service.active_vectorstores:
                        del self.document_service.active_vectorstores[collection]
                        logger.info(f"활성 컬렉션 제거: {collection}")

                return True

            # 4. 새 FAISS 인덱스 생성 (벡터 재사용)
            import numpy as np
            import faiss
            from langchain_community.docstore.in_memory import InMemoryDocstore

            # 남길 문서의 인덱스 ID 찾기
            remaining_doc_ids = [doc_id for doc_id, doc in vectorstore.docstore._dict.items()
                                if doc.metadata.get('source', '') not in target_sources]

            # 기존 벡터 추출
            all_vectors = []
            for i in range(vectorstore.index.ntotal):
                vector = vectorstore.index.reconstruct(i)
                all_vectors.append(vector)

            all_vectors = np.array(all_vectors)

            # 남길 벡터만 선택
            remaining_indices = []
            for idx, doc_id in enumerate(vectorstore.index_to_docstore_id.values()):
                if doc_id in remaining_doc_ids:
                    remaining_indices.append(idx)

            remaining_vectors = all_vectors[remaining_indices]

            # 새 인덱스 생성
            dimension = remaining_vectors.shape[1]
            new_index = faiss.IndexFlatL2(dimension)
            new_index.add(remaining_vectors)

            # 새 docstore 생성
            new_docstore = InMemoryDocstore({
                doc_id: doc
                for doc_id, doc in vectorstore.docstore._dict.items()
                if doc_id in remaining_doc_ids
            })

            # 새 index_to_docstore_id 매핑
            new_index_to_docstore_id = {
                i: doc_id
                for i, doc_id in enumerate(remaining_doc_ids)
            }

            # 새 FAISS vectorstore 생성
            embedding_model = get_embeddings(provider=os.getenv("EMBEDDING_PROVIDER", "qwen"))
            new_vectorstore = FAISS(
                embedding_function=embedding_model.embed_query,
                index=new_index,
                docstore=new_docstore,
                index_to_docstore_id=new_index_to_docstore_id
            )

            # 5. 저장
            new_vectorstore.save_local(
                folder_path=self.faiss_dir,
                index_name=collection
            )
            logger.info(f"FAISS 인덱스 재구성 완료: {collection}")

            # 6. active_vectorstores 업데이트
            if hasattr(self.document_service, 'active_vectorstores'):
                self.document_service.active_vectorstores[collection] = new_vectorstore
                logger.info(f"활성 컬렉션 업데이트: {collection}")

            return True

        except Exception as e:
            logger.error(f"FAISS 인덱스 재구성 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _delete_file_metadata(self, filename: str) -> Dict:
        """파일 메타데이터 삭제"""
        try:
            if not os.path.exists(self.file_metadata_path):
                return {'success': True}  # 파일이 없으면 성공

            with open(self.file_metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            if filename in metadata:
                del metadata[filename]

                with open(self.file_metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)

                logger.info(f"파일 메타데이터 삭제: {filename}")
                return {'success': True}

            return {'success': True}  # 없어도 성공

        except Exception as e:
            logger.error(f"파일 메타데이터 삭제 실패: {e}")
            return {'success': False, 'error': str(e)}

    def _delete_all_original_files(self) -> Dict:
        """모든 원본 파일 삭제"""
        count = 0
        html_count = 0
        errors = []

        # 1. documents/ 디렉토리 정리
        if os.path.exists(self.documents_dir):
            for filename in os.listdir(self.documents_dir):
                filepath = os.path.join(self.documents_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        count += 1
                        logger.debug(f"파일 삭제: {filepath}")
                except Exception as e:
                    errors.append(f"{filename}: {e}")

        # 2. html/ 디렉토리 정리
        if os.path.exists(self.html_dir):
            for filename in os.listdir(self.html_dir):
                filepath = os.path.join(self.html_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        html_count += 1
                        logger.debug(f"HTML 파일 삭제: {filepath}")
                except Exception as e:
                    errors.append(f"{filename}: {e}")

        logger.info(f"원본 파일 삭제 완료: {count}개 파일, {html_count}개 HTML")
        return {'count': count, 'html_count': html_count, 'errors': errors}

    def _delete_all_vectordb(self) -> Dict:
        """벡터 DB 전체 삭제"""
        try:
            count = 0
            if os.path.exists(self.faiss_dir):
                # 컬렉션 수 카운트
                count = len([f for f in os.listdir(self.faiss_dir) if f.endswith('.faiss')])

                # 디렉토리 삭제 후 재생성
                shutil.rmtree(self.faiss_dir)
                os.makedirs(self.faiss_dir, exist_ok=True)

                logger.info(f"벡터 DB 삭제 완료: {count}개 컬렉션")

            # DocumentService의 메모리 상태 초기화
            if self.document_service:
                # active_vectorstores 초기화
                if hasattr(self.document_service, 'active_vectorstores'):
                    for collection_name in list(self.document_service.active_vectorstores.keys()):
                        vs = self.document_service.active_vectorstores[collection_name]
                        if hasattr(vs, 'vectorstore'):
                            vs.vectorstore = None
                    self.document_service.active_vectorstores.clear()
                    logger.info("active_vectorstores 메모리 초기화 완료")

                # vectorstore 참조 해제
                if hasattr(self.document_service, 'vectorstore'):
                    self.document_service.vectorstore = None

                # current_documents 초기화
                if hasattr(self.document_service, 'current_documents'):
                    self.document_service.current_documents = []

                # RAG 참조 해제
                if hasattr(self.document_service, 'rag'):
                    self.document_service.rag = None

            return {'count': count}

        except Exception as e:
            logger.error(f"벡터 DB 삭제 실패: {e}")
            return {'count': 0, 'error': str(e)}

    def _reset_all_metadata(self):
        """모든 메타데이터 초기화"""
        try:
            # 파일 메타데이터 초기화
            if os.path.exists(self.file_metadata_path):
                with open(self.file_metadata_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                logger.info("파일 메타데이터 초기화 완료")
        except Exception as e:
            logger.error(f"메타데이터 초기화 실패: {e}")
