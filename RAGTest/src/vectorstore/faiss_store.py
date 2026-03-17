"""
FAISS 벡터 스토어

FAISS(Facebook AI Similarity Search)를 사용한 벡터 저장 및 검색

ChromaDB vs FAISS:
- ChromaDB: 간단, 메타데이터 필터링 강력, 클라이언트-서버 모드 지원
- FAISS: 빠름, 대규모 데이터, 메모리 효율적, 다양한 인덱스 알고리즘
"""

from typing import List, Optional, Dict
from langchain_core.documents import Document  # LangChain 1.0+
from langchain_community.vectorstores import FAISS
import os
import pickle
import json
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils import get_embeddings


class FAISSVectorStore:
    """
    FAISS 기반 벡터 스토어

    FAISS는 Facebook에서 개발한 고속 유사도 검색 라이브러리입니다.
    특징:
    - 매우 빠른 검색 속도
    - 메모리 효율적
    - 수백만 개 벡터도 처리 가능
    - 로컬 파일 시스템에 저장
    """

    def __init__(
        self,
        collection_name: str = "rag_documents",
        persist_directory: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        embedding_function = None  # 외부에서 로드된 임베딩 함수
    ):
        """
        FAISSVectorStore 초기화

        Args:
            collection_name (str): 컬렉션 이름 (인덱스 이름)
            persist_directory (str, optional): 저장 경로
            embedding_model (str, optional): 임베딩 모델명
            embedding_provider (str, optional): 임베딩 제공자
            embedding_function (optional): 이미 로드된 임베딩 함수
        """
        print(f"[FAISS] 초기화 시작 - collection: {collection_name}", flush=True)

        self.collection_name = collection_name
        self.index_name = collection_name  # 하위 호환성
        self.persist_directory = persist_directory or "./data/faiss"
        self.index_path = os.path.join(self.persist_directory, collection_name)

        print(f"[FAISS] persist_directory: {self.persist_directory}", flush=True)
        print(f"[FAISS] index_path: {self.index_path}", flush=True)

        # 임베딩 함수 초기화
        if embedding_function is not None:
            # 외부에서 전달된 임베딩 함수 사용
            print(f"[FAISS] 외부 임베딩 함수 사용", flush=True)
            self.embedding_function = embedding_function
        else:
            # 새로 생성
            print(f"[FAISS] 임베딩 함수 새로 생성", flush=True)
            self.embedding_function = get_embeddings(
                provider=embedding_provider,
                model=embedding_model
            )

        print(f"[FAISS] 임베딩 함수 설정 완료", flush=True)

        # 저장 디렉토리 생성
        os.makedirs(self.persist_directory, exist_ok=True)

        # 메타데이터 파일 경로
        self.metadata_file = os.path.join(self.persist_directory, f"{collection_name}_metadata.json")

        # FAISS 인스턴스
        self.vectorstore = None

        # 문서 메타데이터 로드
        self.document_metadata = self._load_metadata()

        # 기존 인덱스 로드
        print(f"[FAISS] 인덱스 파일 존재 확인: {os.path.exists(f'{self.index_path}.faiss')}", flush=True)

        if os.path.exists(f"{self.index_path}.faiss"):
            print(f"[FAISS] 기존 인덱스 로드 시도...", flush=True)
            self._load_existing_index()
            print(f"[FAISS] 기존 인덱스 로드 완료: {self.index_path}", flush=True)
        else:
            print(f"[FAISS] 새로운 인덱스 (파일 없음)", flush=True)

    def _load_existing_index(self):
        """기존 FAISS 인덱스 로드"""
        try:
            print(f"[FAISS] FAISS 인덱스 로드 중...", flush=True)
            print(f"[FAISS]   - folder_path: {self.persist_directory}", flush=True)
            print(f"[FAISS]   - index_name: {self.index_name}", flush=True)

            self.vectorstore = FAISS.load_local(
                folder_path=self.persist_directory,
                embeddings=self.embedding_function,
                index_name=self.index_name,
                allow_dangerous_deserialization=True  # pickle 로드 허용
            )

            print(f"[FAISS] 인덱스 로드 성공!", flush=True)
        except Exception as e:
            print(f"[FAISS] 경고: 기존 인덱스 로드 실패 - {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.vectorstore = None

    def add_documents(self, documents: List[Document], chunking_info: dict = None) -> List[str]:
        """
        문서를 FAISS 인덱스에 추가합니다.

        Args:
            documents (List[Document]): 추가할 문서 리스트
            chunking_info (dict): 청킹 정보 (optional)

        Returns:
            List[str]: 문서 ID 리스트

        Example:
            >>> store = FAISSVectorStore()
            >>> docs = [Document(page_content="텍스트")]
            >>> chunking_info = {'method': 'semantic', 'chunk_size': 1500}
            >>> store.add_documents(docs, chunking_info)
        """
        if not documents:
            print("추가할 문서가 없습니다.")
            return []

        try:
            if self.vectorstore is None:
                # 첫 문서 추가 시 인덱스 생성
                self.vectorstore = FAISS.from_documents(
                    documents=documents,
                    embedding=self.embedding_function
                )
                print(f"✓ {len(documents)}개 문서 추가 (새 인덱스 생성)")
            else:
                # 기존 인덱스에 추가
                self.vectorstore.add_documents(documents)
                print(f"✓ {len(documents)}개 문서 추가 (기존 인덱스)")

            # 문서 메타데이터 업데이트 (청킹 정보 포함)
            self._update_document_metadata(documents, chunking_info)

            # 디스크에 저장
            self.save()

            return [f"doc_{i}" for i in range(len(documents))]

        except Exception as e:
            raise Exception(f"문서 추가 실패: {str(e)}")

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs
    ) -> List[Document]:
        """
        쿼리와 유사한 문서를 검색합니다.

        Args:
            query (str): 검색 쿼리
            k (int): 반환할 문서 개수

        Returns:
            List[Document]: 유사한 문서 리스트
        """
        if self.vectorstore is None:
            print("인덱스가 비어있습니다. 먼저 문서를 추가하세요.")
            return []

        try:
            results = self.vectorstore.similarity_search(
                query=query,
                k=k,
                **kwargs
            )

            print(f"✓ '{query[:50]}...' 검색 완료: {len(results)}개 결과")

            return results

        except Exception as e:
            raise Exception(f"검색 실패: {str(e)}")

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4
    ) -> List[tuple[Document, float]]:
        """
        유사도 점수와 함께 문서를 검색합니다.

        Args:
            query (str): 검색 쿼리
            k (int): 반환할 문서 개수

        Returns:
            List[tuple[Document, float]]: (문서, 유사도 점수) 튜플 리스트
        """
        if self.vectorstore is None:
            return []

        try:
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=k
            )

            print(f"✓ 점수 포함 검색 완료: {len(results)}개 결과")
            for i, (doc, score) in enumerate(results):
                print(f"  {i+1}. 유사도 점수: {score:.4f}")

            return results

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[ERROR] FAISS similarity_search_with_score 실패 상세:")
            print(error_detail)
            raise Exception(f"검색 실패: {type(e).__name__}: {str(e)}")

    def as_retriever(self, search_kwargs: Optional[dict] = None):
        """
        LangChain Retriever로 변환

        Args:
            search_kwargs (dict, optional): 검색 파라미터

        Returns:
            VectorStoreRetriever: Retriever 객체
        """
        if self.vectorstore is None:
            raise ValueError("인덱스가 초기화되지 않았습니다.")

        search_kwargs = search_kwargs or {"k": 4}

        return self.vectorstore.as_retriever(
            search_kwargs=search_kwargs
        )

    def save(self):
        """
        FAISS 인덱스를 디스크에 저장합니다.

        FAISS는 두 파일을 생성합니다:
        1. .faiss 파일: 벡터 인덱스
        2. .pkl 파일: 메타데이터 및 문서
        """
        if self.vectorstore is None:
            print("저장할 인덱스가 없습니다.")
            return

        try:
            # 디렉토리 생성
            os.makedirs(self.persist_directory, exist_ok=True)

            # FAISS 인덱스 저장
            self.vectorstore.save_local(
                folder_path=self.persist_directory,
                index_name=self.index_name
            )

            print(f"✓ FAISS 인덱스 저장: {self.index_path}")

        except Exception as e:
            print(f"인덱스 저장 실패: {e}")

    def delete_index(self):
        """
        인덱스 파일을 삭제합니다.

        주의: 이 작업은 되돌릴 수 없습니다!
        """
        try:
            faiss_file = f"{self.index_path}.faiss"
            pkl_file = f"{self.index_path}.pkl"

            if os.path.exists(faiss_file):
                os.remove(faiss_file)
            if os.path.exists(pkl_file):
                os.remove(pkl_file)

            self.vectorstore = None
            print(f"✓ 인덱스 '{self.index_name}' 삭제됨")

        except Exception as e:
            print(f"인덱스 삭제 실패: {e}")

    def get_stats(self) -> dict:
        """
        인덱스 통계 정보를 반환합니다.

        Returns:
            dict: 문서 수 등의 통계
        """
        if self.vectorstore is None:
            return {"document_count": 0, "collection_name": self.collection_name}

        try:
            # FAISS 인덱스의 벡터 수
            count = self.vectorstore.index.ntotal

            return {
                "document_count": count,
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            return {"error": str(e)}

    def exists(self) -> bool:
        """
        컬렉션이 이미 존재하고 문서가 있는지 확인합니다.

        Returns:
            bool: 컬렉션이 존재하고 1개 이상의 문서가 있으면 True
        """
        if self.vectorstore is None:
            return False

        try:
            count = self.vectorstore.index.ntotal
            return count > 0
        except Exception:
            return False

    def is_empty(self) -> bool:
        """
        컬렉션이 비어있는지 확인합니다.

        Returns:
            bool: 컬렉션이 없거나 문서가 0개면 True
        """
        return not self.exists()

    def _load_metadata(self) -> Dict:
        """메타데이터 파일 로드"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[FAISS] 메타데이터 로드 실패: {e}")
                return {}
        return {}

    def _save_metadata(self):
        """메타데이터 파일 저장"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.document_metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FAISS] 메타데이터 저장 실패: {e}")

    def _update_document_metadata(self, documents: List[Document], chunking_info: dict = None):
        """
        문서 메타데이터 업데이트

        Args:
            documents: 문서 리스트
            chunking_info: 청킹 정보 딕셔너리
                {
                    'method': 'semantic' | 'fixed',
                    'chunk_size': int,
                    'chunk_overlap': int,
                    'embedding_model': str
                }
        """
        # 파일별로 청크 수, 카테고리, 제목 집계
        file_chunks = {}
        file_categories = {}  # 파일별 category_id 저장
        file_titles = {}  # 파일별 title 저장
        for doc in documents:
            source = doc.metadata.get("source", "Unknown")
            category_id = doc.metadata.get("category_id", "general")
            title = doc.metadata.get("title", "")

            if source not in file_chunks:
                file_chunks[source] = 0
                file_categories[source] = category_id  # 첫 번째 청크의 category_id 저장
                file_titles[source] = title  # 첫 번째 청크의 title 저장
            file_chunks[source] += 1

        # 메타데이터 업데이트
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for source, chunk_count in file_chunks.items():
            filename = os.path.basename(source)
            category_id = file_categories.get(source, "general")

            if filename in self.document_metadata:
                # 기존 문서 업데이트
                self.document_metadata[filename]["chunk_count"] += chunk_count
                self.document_metadata[filename]["updated_at"] = current_time
                # category_id도 업데이트 (변경될 수 있으므로)
                self.document_metadata[filename]["category_id"] = category_id

                # title 업데이트 (새로 추가되거나 기존에 없는 경우)
                title = file_titles.get(source, "")
                if title:
                    self.document_metadata[filename]["title"] = title

                # 청킹 정보 업데이트
                if chunking_info:
                    self.document_metadata[filename].update(chunking_info)
            else:
                # 새 문서 추가
                title = file_titles.get(source, "")
                self.document_metadata[filename] = {
                    "source": source,
                    "title": title,  # 서비스 전체 제목 (예: "VPC(Virtual Private Cloud)")
                    "chunk_count": chunk_count,
                    "added_at": current_time,
                    "updated_at": current_time,
                    "category_id": category_id
                }

                # 청킹 정보 추가
                if chunking_info:
                    self.document_metadata[filename].update(chunking_info)

        # 메타데이터 저장
        self._save_metadata()

    def get_document_list(self) -> List[Dict]:
        """
        청킹이 완료된 문서 목록 반환

        Returns:
            List[Dict]: 문서 정보 리스트
                [
                    {
                        "filename": "test.pdf",
                        "chunk_count": 10,
                        "added_at": "2024-01-01 12:00:00",
                        "collection": "rag_abc123"
                    }
                ]
        """
        documents = []

        # 메타데이터가 있으면 그것을 사용 (빠름)
        if self.document_metadata:
            for filename, info in self.document_metadata.items():
                documents.append({
                    "filename": filename,
                    "source": info.get("source", filename),  # 전체 경로 포함
                    "chunk_count": info.get("chunk_count", 0),
                    "added_at": info.get("added_at", "Unknown"),
                    "collection": self.collection_name
                })
        # 메타데이터가 없으면 FAISS docstore에서 추출 (오래된 컬렉션 대비)
        elif self.vectorstore is not None:
            print(f"[FAISS] 메타데이터 없음. docstore에서 문서 목록 추출 중...")
            try:
                # FAISS docstore에서 모든 문서 가져오기
                file_chunks = {}
                for doc_id, doc in self.vectorstore.docstore._dict.items():
                    source = doc.metadata.get("source", "Unknown")
                    filename = os.path.basename(source)
                    if filename not in file_chunks:
                        file_chunks[filename] = {"source": source, "count": 0}
                    file_chunks[filename]["count"] += 1

                # 문서 목록 생성
                for filename, info in file_chunks.items():
                    documents.append({
                        "filename": filename,
                        "source": info["source"],
                        "chunk_count": info["count"],
                        "added_at": "Unknown (Legacy)",
                        "collection": self.collection_name
                    })

                print(f"[FAISS] docstore에서 {len(documents)}개 파일 정보 추출 완료")

                # 추출한 정보로 메타데이터 생성 및 저장 (다음번에는 빠르게)
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for doc in documents:
                    self.document_metadata[doc["filename"]] = {
                        "source": doc["source"],
                        "chunk_count": doc["chunk_count"],
                        "added_at": current_time,
                        "updated_at": current_time
                    }
                self._save_metadata()
                print(f"[FAISS] 메타데이터 파일 생성 완료: {self.metadata_file}")

            except Exception as e:
                print(f"[FAISS] docstore에서 문서 추출 실패: {e}")
                import traceback
                traceback.print_exc()

        return documents

    def delete_collection_data(self):
        """
        전체 컬렉션 데이터 삭제

        주의: 되돌릴 수 없습니다!
        """
        try:
            # 메모리에서 제거
            self.vectorstore = None

            # 파일 삭제
            if os.path.exists(f"{self.index_path}.faiss"):
                os.remove(f"{self.index_path}.faiss")
                print(f"[FAISS] {self.index_path}.faiss 삭제")

            if os.path.exists(f"{self.index_path}.pkl"):
                os.remove(f"{self.index_path}.pkl")
                print(f"[FAISS] {self.index_path}.pkl 삭제")

            if os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
                print(f"[FAISS] {self.metadata_file} 삭제")

            # 메타데이터 초기화
            self.document_metadata = {}

            print(f"✓ 컬렉션 '{self.collection_name}' 전체 삭제 완료")
            return True

        except Exception as e:
            print(f"컬렉션 삭제 실패: {e}")
            return False

    def delete_document_by_filename(self, filename: str):
        """
        특정 파일명의 문서를 벡터 스토어에서 삭제

        Args:
            filename: 삭제할 파일명 (예: "example.html" 또는 "guide:Server")

        Returns:
            bool: 성공 여부
        """
        try:
            if self.vectorstore is None:
                print("벡터 스토어가 비어있습니다.")
                return False

            # 서비스 레벨 문서 ID 패턴 확인 (예: "guide:Server")
            is_service_doc = ':' in filename and not filename.startswith('http')
            service_name = None
            if is_service_doc:
                parts = filename.split(':', 1)
                if len(parts) == 2:
                    service_name = parts[1]
                    print(f"[DEBUG] 서비스 문서 삭제: service_name='{service_name}'")

            # docstore에서 해당 파일명을 포함하는 문서 ID 찾기
            docstore = self.vectorstore.docstore
            index_to_docstore_id = self.vectorstore.index_to_docstore_id

            # 삭제할 인덱스 찾기
            indices_to_keep = []
            docs_to_keep = []

            for idx, doc_id in index_to_docstore_id.items():
                doc = docstore._dict.get(doc_id)
                if doc and hasattr(doc, 'metadata'):
                    source = doc.metadata.get('source', '')
                    should_keep = True

                    # 서비스 레벨 문서인 경우: service_name 메타데이터로 매칭
                    if is_service_doc and service_name:
                        doc_service_name = doc.metadata.get('service_name', '')
                        if doc_service_name == service_name:
                            should_keep = False
                    # 일반 파일인 경우: basename으로 매칭
                    elif os.path.basename(source) == filename:
                        should_keep = False

                    if should_keep:
                        indices_to_keep.append(idx)
                        docs_to_keep.append(doc)

            if len(docs_to_keep) == len(index_to_docstore_id):
                print(f"파일 '{filename}'을(를) 찾을 수 없습니다.")
                return False

            # 메타데이터에서 제거
            if filename in self.document_metadata:
                del self.document_metadata[filename]
                self._save_metadata()

            if len(docs_to_keep) == 0:
                # 모든 문서가 삭제되는 경우 - 인덱스 파일도 삭제
                print(f"모든 문서가 삭제되어 인덱스 파일을 삭제합니다.")
                self.vectorstore = None

                # 디스크에서 FAISS 파일 삭제
                faiss_file = f"{self.index_path}.faiss"
                pkl_file = f"{self.index_path}.pkl"

                if os.path.exists(faiss_file):
                    os.remove(faiss_file)
                    print(f"  - 삭제됨: {faiss_file}")
                if os.path.exists(pkl_file):
                    os.remove(pkl_file)
                    print(f"  - 삭제됨: {pkl_file}")

                return True
            else:
                # 유지할 문서들로 새 인덱스 생성
                print(f"파일 '{filename}' 삭제 중... (남은 문서: {len(docs_to_keep)}개)")
                self.vectorstore = FAISS.from_documents(
                    documents=docs_to_keep,
                    embedding=self.embedding_function
                )

            # 디스크에 저장
            self.save()

            print(f"✓ 파일 '{filename}' 삭제 완료")
            return True

        except Exception as e:
            print(f"문서 삭제 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_chunks_by_filename(self, filename: str, limit: Optional[int] = None) -> List[Dict]:
        """
        특정 파일명의 청크들을 조회

        Args:
            filename: 조회할 파일명 (예: "example.pdf" 또는 "guide:Server")
            limit: 반환할 최대 청크 개수 (None이면 전체)

        Returns:
            List[Dict]: 청크 정보 리스트
                [
                    {
                        "chunk_index": 0,
                        "content": "청크 내용...",
                        "length": 512,
                        "metadata": {...}
                    },
                    ...
                ]
        """
        try:
            if self.vectorstore is None:
                print(f"벡터 스토어가 비어있습니다.")
                return []

            chunks = []
            docstore = self.vectorstore.docstore

            # 문서 ID 패턴 분류
            # 1. text:XXXX - 텍스트 직접 입력 문서 (source 또는 filename으로 매칭)
            # 2. guide:Server - 서비스 레벨 문서 (service_name으로 매칭)
            # 3. 일반 파일 - basename으로 매칭
            is_text_doc = filename.startswith('text:')
            is_service_doc = ':' in filename and not filename.startswith('http') and not is_text_doc
            service_name = None

            if is_text_doc:
                print(f"[DEBUG] 텍스트 입력 문서 검색: filename='{filename}'")
            elif is_service_doc:
                parts = filename.split(':', 1)
                if len(parts) == 2:
                    service_name = parts[1]  # "Server"
                    print(f"[DEBUG] 서비스 문서 검색: service_name='{service_name}'")

            # docstore에서 해당 파일명의 모든 청크 찾기
            for doc_id, doc in docstore._dict.items():
                if hasattr(doc, 'metadata'):
                    source = doc.metadata.get('source', '')
                    doc_filename = doc.metadata.get('filename', '')

                    matched = False

                    # 1. 텍스트 입력 문서: source 또는 filename 메타데이터로 매칭
                    if is_text_doc:
                        if source == filename or doc_filename == filename:
                            matched = True
                    # 2. 서비스 레벨 문서: service_name 메타데이터로 매칭
                    elif is_service_doc and service_name:
                        doc_service_name = doc.metadata.get('service_name', '')
                        if doc_service_name == service_name:
                            matched = True
                    # 3. 일반 파일: basename으로 매칭
                    elif os.path.basename(source) == filename:
                        matched = True

                    if matched:
                        chunks.append({
                            "chunk_index": len(chunks),
                            "content": doc.page_content,
                            "length": len(doc.page_content),
                            "metadata": doc.metadata
                        })

            # limit 적용
            if limit is not None and limit > 0:
                chunks = chunks[:limit]

            print(f"✓ 파일 '{filename}'의 청크 {len(chunks)}개 조회 완료")
            return chunks

        except Exception as e:
            print(f"청크 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return []


# 사용 예제
if __name__ == "__main__":
    print("=== FAISS 벡터 스토어 예제 ===\n")

    from dotenv import load_dotenv
    load_dotenv()

    # 샘플 문서
    sample_docs = [
        Document(
            page_content="FAISS는 Facebook AI Research에서 개발한 벡터 검색 라이브러리입니다.",
            metadata={"source": "intro"}
        ),
        Document(
            page_content="FAISS는 수백만 개의 벡터를 빠르게 검색할 수 있습니다.",
            metadata={"source": "features"}
        ),
    ]

    try:
        # 벡터 스토어 생성
        store = FAISSVectorStore(
            index_name="test_index",
            persist_directory="./data/faiss_test"
        )

        # 문서 추가
        print("문서 추가 중...")
        store.add_documents(sample_docs)

        # 통계 확인
        stats = store.get_stats()
        print(f"\n통계: {stats}")

        # 검색
        print("\n검색 테스트:")
        results = store.similarity_search("FAISS란?", k=2)

        for i, doc in enumerate(results):
            print(f"\n결과 {i+1}:")
            print(f"  내용: {doc.page_content}")

    except Exception as e:
        print(f"에러: {e}")
