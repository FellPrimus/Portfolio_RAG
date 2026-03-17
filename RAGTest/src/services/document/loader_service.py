"""
문서 로드 서비스

파일 로드, 청킹, 벡터 스토어 저장을 담당합니다.
"""

import os
import json
import time
import hashlib
from typing import Dict, List, Optional, Callable, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .session_state import DocumentSessionState


class LoaderService:
    """문서 로드 서비스"""

    def __init__(
        self,
        state: 'DocumentSessionState',
        rag_initializer: Optional[Callable] = None
    ):
        """
        Args:
            state: 공유 상태 객체
            rag_initializer: RAG 초기화 콜백
        """
        self.state = state
        self.rag_initializer = rag_initializer

    def set_rag_initializer(self, initializer: Callable) -> None:
        """RAG 초기화 콜백 설정"""
        self.rag_initializer = initializer

    def load_documents(
        self, file_paths: List[str], chunk_config: Optional[Dict] = None
    ) -> Dict:
        """
        문서 로드 및 메인 벡터 스토어(documents)에 저장

        Args:
            file_paths: 로드할 파일 경로 리스트
            chunk_config: 청킹 설정 {'size': int, 'overlap': int}

        Returns:
            {'success': bool, 'stats': dict, 'error': str}
        """
        try:
            from src.loaders import UniversalDocumentLoader
            from src.chunkers import TextChunker
            from src.vectorstore.faiss_store import FAISSVectorStore

            print("[LOG] 문서 로드 시작", flush=True)

            emb_model = self.state.embedding_model
            if emb_model is None:
                return {'success': False, 'error': '임베딩 모델이 초기화되지 않았습니다.'}

            # 청킹 설정
            if chunk_config is None:
                chunk_config = {
                    'size': int(os.getenv('CHUNK_SIZE', 1000)),
                    'overlap': int(os.getenv('CHUNK_OVERLAP', 200))
                }

            persist_directory = "./data/faiss_web"
            collection_name = "documents"
            total_chunks = 0
            processed_files = []

            # file_metadata.json 로드
            file_metadata = self._load_file_metadata()

            # 벡터 스토어 초기화
            vectorstore = FAISSVectorStore(
                collection_name=collection_name,
                persist_directory=persist_directory,
                embedding_function=emb_model
            )

            # 각 파일 처리
            for file_path in file_paths:
                result = self._process_single_file(
                    file_path, vectorstore, file_metadata, chunk_config
                )
                if result['success']:
                    total_chunks += result['chunk_count']
                    processed_files.append(result['filename'])

            # file_metadata.json 저장
            self._save_file_metadata(file_metadata)

            print(f"\n[LOG] 총 {len(processed_files)}개 파일 처리 완료")
            print(f"[LOG] 총 {total_chunks}개 청크 생성")

            # 상태 업데이트
            self.state.vectorstore = vectorstore

            # RAG 초기화
            if self.rag_initializer:
                self.rag_initializer(vectorstore, use_multi_collection=False)
            print("[LOG] RAG 시스템 초기화 완료")

            return {
                'success': True,
                'stats': {
                    'files': len(file_paths),
                    'chunks': total_chunks,
                    'documents': len(processed_files),
                    'processed_files': processed_files
                }
            }

        except Exception as e:
            import traceback
            print(f"\n[ERROR] 문서 로드 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _process_single_file(
        self, file_path: str, vectorstore, file_metadata: Dict, chunk_config: Dict
    ) -> Dict:
        """단일 파일 처리"""
        from src.loaders import UniversalDocumentLoader
        from src.chunkers import TextChunker

        filename = os.path.basename(file_path)
        print(f"\n[LOG] 파일 처리 시작: {filename}")

        # 중복 확인
        if filename in file_metadata and file_metadata[filename].get('chunk_count', 0) > 0:
            print(f"[LOG] 이미 임베딩된 파일: {filename}")
            return {
                'success': True,
                'filename': filename,
                'chunk_count': file_metadata[filename].get('chunk_count', 0)
            }

        # 문서 로드
        loader = UniversalDocumentLoader()
        docs = loader.load(file_path)

        if not docs:
            print(f"[WARN] 파일에서 문서를 로드할 수 없음: {filename}")
            return {'success': False, 'filename': filename, 'chunk_count': 0}

        # 메타데이터 추가
        category_id = file_metadata.get(filename, {}).get('category_id', 'general')
        for doc in docs:
            doc.metadata['category_id'] = category_id
            doc.metadata['filename'] = filename

        # 청킹
        chunker = TextChunker(
            chunk_size=chunk_config['size'],
            chunk_overlap=chunk_config['overlap']
        )
        chunks = chunker.chunk_documents(docs)
        print(f"[LOG] {filename}: {len(chunks)}개 청크 생성")

        if len(chunks) == 0:
            print(f"[WARN] 청크가 생성되지 않음: {filename}")
            return {'success': False, 'filename': filename, 'chunk_count': 0}

        # 벡터 스토어에 저장
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "huggingface")
        chunking_info = {
            'method': 'fixed',
            'chunk_size': chunk_config['size'],
            'chunk_overlap': chunk_config['overlap'],
            'embedding_model': embedding_provider
        }
        vectorstore.add_documents(chunks, chunking_info)
        print(f"[LOG] 벡터 스토어 저장 완료: {filename}")

        # 메타데이터 업데이트
        file_metadata[filename] = {
            'filename': filename,
            'filepath': file_path,
            'display_name': filename,
            'category_id': category_id,
            'upload_time': time.time(),
            'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'chunk_count': len(chunks),
            'collection': "documents",
            'doc_type': 'file_upload'
        }

        return {'success': True, 'filename': filename, 'chunk_count': len(chunks)}

    def load_text(self, title: str, content: str, category_id: str = 'general') -> Dict:
        """
        텍스트 직접 입력 및 벡터DB 저장 (의미 기준 청킹)

        Args:
            title: 문서 제목
            content: 텍스트 내용
            category_id: 카테고리 ID

        Returns:
            {'success': bool, 'chunk_count': int, 'doc_id': str}
        """
        try:
            from langchain_core.documents import Document
            from src.chunkers.semantic_chunker import SemanticChunker
            from src.vectorstore.faiss_store import FAISSVectorStore

            print(f"\n[LOG] 텍스트 직접 입력 처리 시작: {title}")

            emb_model = self.state.embedding_model
            if emb_model is None:
                return {'success': False, 'error': '임베딩 모델이 초기화되지 않았습니다.'}

            # 문서 ID 생성
            hash_input = f"{title}_{datetime.now().isoformat()}"
            doc_id = f"text:{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"
            print(f"[LOG] 문서 ID: {doc_id}")

            # Document 생성
            doc = Document(
                page_content=content,
                metadata={
                    'source': doc_id,
                    'title': title,
                    'category_id': category_id,
                    'doc_type': 'direct_text',
                    'filename': doc_id
                }
            )

            # 의미 기준 청킹
            chunker = SemanticChunker(embedding_function=emb_model)
            chunks = chunker.chunk_documents([doc])
            print(f"[LOG] 의미 기준 청킹 완료: {len(chunks)}개 청크")

            # 벡터스토어에 저장
            persist_directory = "./data/faiss_web"
            vectorstore = FAISSVectorStore(
                collection_name="documents",
                persist_directory=persist_directory,
                embedding_function=emb_model
            )

            embedding_provider = os.getenv("EMBEDDING_PROVIDER", "huggingface")
            chunking_info = {
                'method': 'semantic',
                'embedding_model': embedding_provider
            }
            vectorstore.add_documents(chunks, chunking_info=chunking_info)
            print(f"[LOG] 벡터 스토어 저장 완료")

            # file_metadata.json 등록
            file_metadata = self._load_file_metadata()
            file_metadata[doc_id] = {
                'filename': doc_id,
                'filepath': f"text_input:{title}",
                'display_name': f"[텍스트] {title}",
                'category_id': category_id,
                'upload_time': time.time(),
                'file_size': len(chunks),
                'doc_type': 'direct_text',
                'title': title
            }
            self._save_file_metadata(file_metadata)
            print(f"[LOG] file_metadata.json 등록 완료")

            # 카테고리 문서 수 증가
            if self.state.category_manager and category_id:
                self.state.category_manager.increment_document_count(category_id)

            return {
                'success': True,
                'doc_id': doc_id,
                'chunk_count': len(chunks),
                'title': title
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 텍스트 저장 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _load_file_metadata(self) -> Dict:
        """file_metadata.json 로드"""
        file_metadata_path = "./data/file_metadata.json"
        if os.path.exists(file_metadata_path):
            try:
                with open(file_metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] file_metadata.json 로드 실패: {e}")
        return {}

    def _save_file_metadata(self, metadata: Dict) -> None:
        """file_metadata.json 저장"""
        file_metadata_path = "./data/file_metadata.json"
        with open(file_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print("[LOG] file_metadata.json 업데이트 완료")
